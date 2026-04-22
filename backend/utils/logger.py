"""
Logging utilities for the FireReach backend.
"""

# ANSI Escape Codes for colored terminal output
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_BLUE = "\033[94m"
ANSI_GREEN = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_RED = "\033[91m"
ANSI_MAGENTA = "\033[95m"


def log_pipeline_step(step: str, status: str, message: str):
    """
    Prints a formatted, colored log message for a pipeline step to the terminal.

    Args:
        step: The name of the step (e.g., 'step1', 'START', 'DONE').
        status: The current status of the step (e.g., 'completed', 'in-progress', 'failed').
        message: The detailed log message.
    """
    color = ANSI_BLUE
    if status == "completed":
        color = ANSI_GREEN
    elif status == "failed":
        color = ANSI_RED
    elif status in ("in-progress", "partial"):
        color = ANSI_YELLOW

    step_label = step.upper() if step else "WORKFLOW"
    print(
        f"{ANSI_DIM}[pipeline]{ANSI_RESET} "
        f"{color}{ANSI_BOLD}{step_label:<7}{ANSI_RESET} "
        f"{ANSI_MAGENTA}{status:<11}{ANSI_RESET} {message}"
    )


async def notify_progress(progress_callback, step: str, status: str, message: str, data: dict = None):
    """
    Logs a pipeline step and sends the progress update to the client via the callback.

    Args:
        progress_callback: An async callable that takes a dictionary event payload.
        step: The name of the pipeline step.
        status: The current status.
        message: The detailed message.
        data: Optional dictionary containing additional data for the client.
    """
    log_pipeline_step(step, status, message)

    if not progress_callback:
        return

    payload = {
        "step": step,
        "status": status,
        "message": message,
    }
    if data is not None:
        payload["data"] = data

    await progress_callback(payload)
