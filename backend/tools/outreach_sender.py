import json
import os
import re
import time

from services.email_service import send_email
from services.openai_client import generate_completion


def _extract_company_signal(signals: dict) -> str:
    """
    Pick the most relevant signal text available from classified signals.
    """
    if not isinstance(signals, dict):
        return "recent growth initiatives"

    for _, items in signals.items():
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("content"):
                    return str(item["content"])
                if isinstance(item, str) and item.strip():
                    return item.strip()
        elif isinstance(items, dict) and items.get("content"):
            return str(items.get("content"))
        elif isinstance(items, str) and items.strip():
            return items.strip()

    return "recent growth initiatives"


def _extract_email_payload(response_text: str, company_name: str, recipient_name: str) -> dict:
    cleaned = str(response_text or "").strip()
    without_fence = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    without_fence = re.sub(r"\s*```$", "", without_fence, flags=re.IGNORECASE).strip()

    def _try_parse_candidate(candidate: str):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, str):
                nested = parsed.strip()
                if nested.startswith("{") and nested.endswith("}"):
                    return json.loads(nested)
            return parsed
        except json.JSONDecodeError:
            return None

    parsed_full = _try_parse_candidate(without_fence)
    if isinstance(parsed_full, dict):
        return parsed_full

    start = without_fence.find("{")
    end = without_fence.rfind("}")
    if start != -1 and end != -1 and end > start:
        parsed_slice = _try_parse_candidate(without_fence[start:end + 1])
        if isinstance(parsed_slice, dict):
            return parsed_slice

    # Fallback for malformed JSON-like output where body string has raw newlines.
    subject_match = re.search(r'"subject"\s*:\s*"([\s\S]*?)"\s*,', without_fence)
    body_match = re.search(r'"body"\s*:\s*"([\s\S]*?)"\s*}\s*$', without_fence)
    if body_match:
        extracted_body = body_match.group(1)
        extracted_body = extracted_body.replace('\\n', '\n').replace('\\"', '"').strip()
        extracted_subject = (
            subject_match.group(1).replace('\\"', '"').strip()
            if subject_match else f"FireReach AI Outreach - {company_name}"
        )
        return {
            "subject": extracted_subject,
            "body": extracted_body,
        }

    return {
        "subject": f"FireReach AI Outreach - {company_name}",
        "body": cleaned or f"Hello {recipient_name},",
    }


def _parse_plain_email(response_text: str, company_name: str, recipient_name: str) -> dict:
    raw = str(response_text or "").strip()
    subject = f"FireReach AI Outreach - {company_name}"
    body = raw

    lines = raw.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower().startswith("subject:"):
            subject = stripped[len("subject:"):].strip()
            body = "\n".join(lines[i + 1:]).strip()
            break

    return {"subject": subject, "body": body}


def _extract_body_from_json_like(content: str) -> str:
    raw = str(content or "").strip()
    if not raw:
        return ""

    without_fence = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    without_fence = re.sub(r"\s*```$", "", without_fence, flags=re.IGNORECASE).strip()

    try:
        direct_parsed = json.loads(without_fence)
        if isinstance(direct_parsed, str):
            nested = direct_parsed.strip()
            if nested.startswith("{") and nested.endswith("}"):
                direct_parsed = json.loads(nested)
        if isinstance(direct_parsed, dict):
            body = direct_parsed.get("body") or direct_parsed.get("email_content")
            if isinstance(body, str) and body.strip():
                return body.strip()
    except json.JSONDecodeError:
        pass

    body_match = re.search(r'"body"\s*:\s*"([\s\S]*?)"\s*}\s*$', without_fence)
    if body_match:
        extracted_body = body_match.group(1)
        return extracted_body.replace('\\n', '\n').replace('\\"', '"').strip()

    start = without_fence.find("{")
    end = without_fence.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return raw

    candidate = without_fence[start:end + 1]
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, str):
            nested = parsed.strip()
            if nested.startswith("{") and nested.endswith("}"):
                parsed = json.loads(nested)
    except json.JSONDecodeError:
        return raw

    if isinstance(parsed, dict):
        body = parsed.get("body") or parsed.get("email_content")
        if isinstance(body, str) and body.strip():
            return body.strip()

    return raw


def _normalize_individual_voice(content: str) -> str:
    text = str(content or "")
    if not text.strip():
        return ""

    text = re.sub(
        r"\bour\s+team\s+is\s+currently\s+working\s+on\s+the\s+firereach\s+platform\b",
        "I am currently leading the FireReach platform",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bour\s+team\s+is\s+working\s+on\s+the\s+firereach\s+platform\b",
        "I am leading work on the FireReach platform",
        text,
        flags=re.IGNORECASE,
    )

    replacements = [
        (r"\bwe\s+are\b", "I am"),
        (r"\bwe're\b", "I'm"),
        (r"\bour\b", "my"),
        (r"\bwe\b", "I"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


def _one_line(text: str, limit: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3].rstrip()}..."


def _build_fallback_email(
    company_name: str,
    recipient_name: str,
    signal_line: str,
    icp: str,
    research_brief: str,
    recipient_role: str,
) -> dict:
    fallback_subject = f"FireReach AI Outreach - {company_name}"
    role_line = _one_line(recipient_role) or "your team"
    context_line = _one_line(research_brief, 260)
    icp_line = _one_line(icp, 220)
    fallback_body = f"""Hello {recipient_name},

I noticed {signal_line} at {company_name}, and that stood out as a strong timing signal.

I am building FireReach to help teams identify high-fit accounts, choose the right decision-makers, and send context-aware outreach at the right moment.

For {role_line}, this may be relevant because {icp_line or 'your team is likely navigating priorities where targeted AI-driven outreach can improve conversion and speed.'}

{context_line or 'From what I reviewed, your current momentum suggests this could be a useful time to compare approaches.'}

Would you be open to a short 15-minute conversation next week?

Best regards,
The FireReach Team
Outreach Automation Platform"""

    return {
        "subject": fallback_subject,
        "body": fallback_body,
    }


def _try_generate_email_payload(
    prompt: str,
    company_name: str,
    recipient_name: str,
    signal_line: str,
    icp: str,
    research_brief: str,
    recipient_role: str,
) -> tuple[dict, str | None]:
    """
    Generates outreach payload via OpenAI; retries briefly on rate-limit and falls back to deterministic template.
    """
    max_attempts = 2
    last_error = None

    for attempt in range(max_attempts):
        try:
            payload = _parse_plain_email(
                generate_completion(
                    prompt=prompt,
                    system_prompt="You are a precise B2B outreach email writer. You write in plain text only. Never use JSON, markdown, or code blocks.",
                    temperature=0.6,
                    max_tokens=800,
                ),
                company_name,
                recipient_name,
            )
            return payload, None
        except Exception as exc:
            last_error = exc
            error_text = str(exc)

            if "rate_limit_exceeded" in error_text.lower() and attempt < (max_attempts - 1):
                retry_after_match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)s", error_text, re.IGNORECASE)
                wait_seconds = float(retry_after_match.group(1)) if retry_after_match else 6.0
                time.sleep(min(max(wait_seconds, 1.0), 12.0))
                continue

            break

    fallback_payload = _build_fallback_email(
        company_name,
        recipient_name,
        signal_line,
        icp,
        research_brief,
        recipient_role,
    )
    return fallback_payload, str(last_error) if last_error else "Unknown OpenAI error"


def _resolve_pitch_path(pdf_filename: str) -> str:
    filename = str(pdf_filename or "").strip()
    if not filename:
        return ""

    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "pitches", filename)


def _select_best_pdf(role: str, icp: str = "") -> str:
    role_text = str(role or "").lower()
    icp_text = str(icp or "").lower()
    merged = f"{role_text} {icp_text}".strip()

    role_mapping = [
        # Prioritize specific function roles before broad leadership titles.
        (["cto", "vp engineering", "head of engineering", "engineering", "tech"], "pitch_cto.pdf"),
        (["cpo", "vp product", "head of product", "product manager", "product"], "pitch_product.pdf"),
        (["hr", "talent", "people", "recruiter", "human resources"], "pitch_hr.pdf"),
        (["cfo", "finance", "investor", "financial"], "pitch_investor.pdf"),
        (["ceo", "founder", "co-founder", "managing director", "md"], "pitch_founder.pdf"),
    ]

    icp_bias = [
        (["hr", "talent", "recruit", "hiring"], "pitch_hr.pdf"),
        (["product", "roadmap", "pmf"], "pitch_product.pdf"),
        (["finance", "fund", "invest", "cfo"], "pitch_investor.pdf"),
        (["cto", "engineering", "developer", "tech", "ai"], "pitch_cto.pdf"),
        (["founder", "ceo", "growth", "strategy"], "pitch_founder.pdf"),
    ]

    for keywords, filename in role_mapping:
        if any(keyword in role_text for keyword in keywords):
            return filename

    for keywords, filename in icp_bias:
        if any(keyword in merged for keyword in keywords):
            return filename

    return "pitch_general.pdf"


def tool_outreach_automated_sender(
    candidate,
    company_name: str,
    research_brief: str,
    signals: dict,
    icp: str,
    send_now: bool = True,
) -> dict:
    """
    Generates a personalized outreach email based on research and signals, then sends it via SMTP.
    """
    if isinstance(candidate, dict):
        candidate_email = str(candidate.get("email", "")).strip()
        recipient_name = str(candidate.get("person_name", "")).strip() or "there"
        recipient_role = str(candidate.get("role", "")).strip()
    else:
        candidate_email = str(candidate or "").strip()
        recipient_name = "there"
        recipient_role = ""

    print(f"Executing tool_outreach_automated_sender to {candidate_email}")

    if not candidate_email:
        return {
            "status": "failed",
            "recipient": "",
            "subject": f"FireReach AI Outreach - {company_name}",
            "email_content": "",
            "message": "No recipient email was available.",
            "pdf_filename": "",
        }

    signal_line = _extract_company_signal(signals)
    pdf_filename = _select_best_pdf(recipient_role, icp)
    pdf_path = _resolve_pitch_path(pdf_filename)

    prompt = f"""
You are an expert B2B sales development representative writing a cold outreach email on behalf of the FireReach team.

Write a polished, professional, and highly personalized cold outreach email using the information below.

---
RECIPIENT DETAILS:
- Name: {recipient_name}
- Role: {recipient_role}
- Company: {company_name}

RESEARCH BRIEF (use this to understand the company):
{research_brief}

STRONGEST BUYING SIGNAL (reference this naturally in the opening):
{signal_line}

ICP CONTEXT (what FireReach is offering):
{icp}
---

STRICT RULES:
1. Write the email in plain text — NO JSON, NO markdown, NO code blocks, NO backticks.
2. Start directly with: Subject: <your subject line>
3. Then a blank line, then the full email body.
4. Opening line must naturally reference the buying signal above — make it specific, not generic.
5. Build the message organically from ICP + recipient role + company context from the research brief; do not follow a rigid paragraph template.
6. Include a concise explanation of what FireReach does and why it matters for this recipient.
7. Close with a warm, low-friction invitation for a short conversation.
8. Do NOT change the signature block below — copy it exactly as written.
9. Do NOT fabricate any facts not present in the research brief or signal.
10. Tone: professional, warm, confident, concise — NOT salesy or robotic.
11. Total length: 150-200 words maximum (excluding subject and signature).
12. Write from the FireReach team's perspective. Use professional and engaging language.

SIGNATURE BLOCK (copy exactly, do not modify):
Best regards,
The FireReach Team
https://firereach.ai
"""

    email_payload, generation_error = _try_generate_email_payload(
        prompt=prompt,
        company_name=company_name,
        recipient_name=recipient_name,
        signal_line=signal_line,
        icp=icp,
        research_brief=research_brief,
        recipient_role=recipient_role,
    )
    subject = str(email_payload.get("subject", f"FireReach AI Outreach - {company_name}")).strip()
    email_content = _normalize_individual_voice(_extract_body_from_json_like(email_payload.get("body", "")))

    if not send_now:
        return {
            "status": "manual_pending",
            "recipient": candidate_email,
            "subject": subject,
            "email_content": email_content,
            "message": "Email generated. Click Send Email to deliver it manually.",
            "generation_warning": generation_error,
            "pdf_filename": pdf_filename,
        }

    success = send_email(to_email=candidate_email, subject=subject, content=email_content, pdf_path=pdf_path)

    return {
        "status": "sent" if success else "failed",
        "recipient": candidate_email,
        "subject": subject,
        "email_content": email_content,
        "message": "Email sent successfully." if success else "SMTP delivery failed.",
        "generation_warning": generation_error,
        "pdf_filename": pdf_filename,
    }


def send_prepared_email(recipient: str, subject: str, email_content: str, pdf_filename: str = "") -> dict:
    """
    Sends a pre-generated outreach email body without re-generating content.
    """
    recipient_email = str(recipient or "").strip()
    final_subject = str(subject or "").strip()
    final_content = _extract_body_from_json_like(email_content)
    selected_pdf = str(pdf_filename or "").strip() or "pitch_general.pdf"
    pdf_path = _resolve_pitch_path(selected_pdf)

    if not recipient_email:
        return {
            "status": "failed",
            "recipient": "",
            "subject": final_subject,
            "email_content": final_content,
            "message": "Recipient email is required.",
            "pdf_filename": selected_pdf,
        }

    if not final_subject:
        return {
            "status": "failed",
            "recipient": recipient_email,
            "subject": "",
            "email_content": final_content,
            "message": "Email subject is required.",
            "pdf_filename": selected_pdf,
        }

    if not final_content:
        return {
            "status": "failed",
            "recipient": recipient_email,
            "subject": final_subject,
            "email_content": "",
            "message": "Email content is required.",
            "pdf_filename": selected_pdf,
        }

    success = send_email(to_email=recipient_email, subject=final_subject, content=final_content, pdf_path=pdf_path)
    return {
        "status": "sent" if success else "failed",
        "recipient": recipient_email,
        "subject": final_subject,
        "email_content": final_content,
        "message": "Email sent successfully." if success else "SMTP delivery failed.",
        "pdf_filename": selected_pdf,
    }
