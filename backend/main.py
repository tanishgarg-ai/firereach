"""
Main entry point for the FireReach FastAPI application.
Configures CORS, global exception handlers, startup/shutdown lifespan, and routes.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, JSONResponse, StreamingResponse

import models  # noqa: F401
from agent import run_agent_workflow, run_selected_company_workflow, send_generated_email
from database import Base, engine
from routes import auth, credits, history, payments
from schemas.agent import AgentRequest, ManualSendRequest, SelectCompanyRequest


SEND_EMAIL_TIMEOUT_SECONDS = 45

# Load environment variables from .env file
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to handle startup and shutdown events.
    """
    # Startup logic
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown logic (if any)


app = FastAPI(
    title="FireReach Autonomous Outreach Engine",
    description="Backend API for the FireReach platform.",
    lifespan=lifespan,
)

# Configure CORS
default_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://firereach-rabbitt.vercel.app",
]
extra_origins = [
    item.strip() for item in str(os.getenv("CORS_ORIGINS", "")).split(",") if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys([*default_origins, *extra_origins])),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    """
    Global handler for HTTPExceptions, ensuring a consistent JSON structure.
    """
    detail = exc.detail
    if isinstance(detail, dict):
        payload = detail.copy()
        if "message" not in payload:
            payload["message"] = "Request failed."
        return JSONResponse(status_code=exc.status_code, content=payload)

    return JSONResponse(status_code=exc.status_code, content={"message": str(detail)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    """
    Global handler for Pydantic validation errors.
    """
    first_error = "Invalid request payload."
    errors = exc.errors()
    if errors:
        first_error = str(errors[0].get("msg") or first_error)
    return JSONResponse(status_code=422, content={"message": first_error})


@app.post("/run-agent")
async def run_agent(request: AgentRequest, stream: bool = True):
    """
    Trigger the FireReach autonomous agent workflow.

    Args:
        request: The initial agent request containing ICP and preferences.
        stream: Whether to stream the progress via server-sent events (NDJSON).

    Returns:
        A StreamingResponse if `stream` is True, otherwise the final JSON result.
    """
    if not stream:
        return await run_agent_workflow(
            icp=request.icp,
            send_mode=request.send_mode,
            target_company=request.target_company,
            test_recipient_email=request.test_recipient_email,
        )

    async def event_stream():
        queue = asyncio.Queue()

        async def progress_callback(event: dict):
            await queue.put({"type": "step", **event})

        async def runner():
            try:
                result = await run_agent_workflow(
                    icp=request.icp,
                    send_mode=request.send_mode,
                    target_company=request.target_company,
                    test_recipient_email=request.test_recipient_email,
                    progress_callback=progress_callback,
                )
                await queue.put({"type": "result", "data": result})
            except Exception as exc:
                await queue.put({"type": "error", "message": str(exc)})
            finally:
                await queue.put({"type": "done"})

        task = asyncio.create_task(runner())

        try:
            while True:
                event = await queue.get()
                if event["type"] == "done":
                    break
                yield json.dumps(event) + "\n"
        finally:
            await task

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.post("/select-company")
async def select_company(request: SelectCompanyRequest):
    """
    Manual mode continuation endpoint.
    Runs contact discovery and email generation for the selected company.
    
    Args:
        request: Payload containing the selected company details.
    
    Returns:
        The workflow result with generated email content.
    """
    if str(request.send_mode).strip().lower() != "manual":
        raise HTTPException(status_code=400, detail="/select-company is only valid for manual mode.")

    return await run_selected_company_workflow(
        icp=request.icp,
        selected_company=request.selected_company,
    )


@app.post("/send-email")
async def send_email(request: ManualSendRequest):
    """
    Sends a pre-generated outreach email upon explicit user action.

    Args:
        request: Contains recipient email, subject, body, and optionally a PDF filename.
    
    Returns:
        A status dictionary indicating success or timeout failure.
    """
    try:
        return await asyncio.wait_for(
            send_generated_email(
                recipient=request.recipient,
                subject=request.subject,
                email_content=request.email_content,
                pdf_filename=request.pdf_filename,
            ),
            timeout=SEND_EMAIL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        return {
            "status": "failed",
            "recipient": request.recipient,
            "subject": request.subject,
            "email_content": request.email_content,
            "message": f"Email send timed out after {SEND_EMAIL_TIMEOUT_SECONDS}s. Please retry.",
            "pdf_filename": request.pdf_filename,
        }


@app.get("/ping")
async def ping():
    """
    Simple health check endpoint.
    """
    return {"status": "alive"}


@app.get("/pitches/{filename}")
def get_pitch_file(filename: str, download: bool = False):
    """
    Serves generated pitch PDFs.

    Args:
        filename: The name of the PDF file to retrieve.
        download: If True, serves as an attachment instead of inline.
    """
    safe_filename = os.path.basename(str(filename or "").strip())
    if not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=404, detail="Pitch PDF not found.")

    pitches_dir = os.path.join(os.path.dirname(__file__), "pitches")
    file_path = os.path.join(pitches_dir, safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Pitch PDF not found.")

    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{safe_filename}"'},
    )


@app.get("/")
def read_root():
    """
    Root endpoint verifying the API is up.
    """
    return {"message": "FireReach API is running. Direct requests to POST /run-agent"}


# Include domain-specific routers
app.include_router(auth.router, prefix="/api")
app.include_router(credits.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(history.router, prefix="/api")
