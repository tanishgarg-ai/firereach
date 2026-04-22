import json
import os
import requests
import re
from urllib.parse import urlparse

GENERIC_INBOX_PREFIXES = {
    "info",
    "contact",
    "hello",
    "hi",
    "sales",
    "support",
    "team",
    "office",
    "admin",
    "careers",
    "jobs",
    "hr",
    "help",
    "enquiries",
    "inquiries",
    "marketing",
}


def _is_org_inbox_email(email: str) -> bool:
    if not email or "@" not in email:
        return True
    local_part = email.split("@", 1)[0].strip().lower()
    return local_part in GENERIC_INBOX_PREFIXES


def _clean_text(value) -> str:
    text = str(value or "").strip()
    return "" if text.lower() in {"none", "null", "n/a", "na"} else text


def _prioritize_personal_emails(leads: list) -> list:
    """
    Enforce strict ordering: personal decision-maker emails first, org inbox emails last.
    """
    if not isinstance(leads, list):
        return []

    cleaned = []
    seen_emails = set()

    for lead in leads:
        if not isinstance(lead, dict):
            continue
        email = str(lead.get("email", "")).strip()
        if not email:
            continue

        key = email.lower()
        if key in seen_emails:
            continue
        seen_emails.add(key)
        cleaned.append(lead)

    personal = [lead for lead in cleaned if not _is_org_inbox_email(str(lead.get("email", "")))]
    org_fallback = [lead for lead in cleaned if _is_org_inbox_email(str(lead.get("email", "")))]

    return (personal + org_fallback)[:5]

def _extract_domain(website: str) -> str:
    normalized = str(website or "").strip()
    if not normalized:
        return ""
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)
    domain = parsed.netloc.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _derive_name_from_email(email: str) -> str:
    value = str(email or "").strip().lower()
    if "@" not in value:
        return "Team"

    local_part = value.split("@", 1)[0]
    if local_part in GENERIC_INBOX_PREFIXES:
        return "Team"

    tokens = [token for token in re.split(r"[._\-]", local_part) if token and token.isalpha()]
    if not tokens:
        return "Team"
    return " ".join(token.capitalize() for token in tokens[:2])


def _derive_name_from_sources(lead: dict) -> str:
    sources = lead.get("sources", [])
    if not isinstance(sources, list):
        return ""

    for source in sources:
        if not isinstance(source, dict):
            continue

        uri = _clean_text(source.get("uri"))
        if not uri:
            continue

        match = re.search(r"/in/([a-zA-Z0-9-]+)", uri)
        if not match:
            continue

        slug = match.group(1)
        parts = [part for part in slug.split("-") if part and not part.isdigit()]
        if len(parts) >= 2:
            return " ".join(part.capitalize() for part in parts[:3])

    return ""


def _extract_linkedin_url_from_sources(lead: dict) -> str:
    sources = lead.get("sources", [])
    if not isinstance(sources, list):
        return ""

    for source in sources:
        if not isinstance(source, dict):
            continue

        uri = _clean_text(source.get("uri"))
        if not uri:
            continue

        lowered = uri.lower()
        if "linkedin.com/in/" in lowered:
            return uri

    return ""


def _derive_avatar_url(lead: dict) -> str:
    linkedin_url = _extract_linkedin_url_from_sources(lead)
    if linkedin_url:
        return f"https://unavatar.io/linkedin/{linkedin_url}"
    return ""


def _derive_role_from_hunter(lead: dict) -> str:
    position = _clean_text(lead.get("position"))
    if position:
        return position

    department = _clean_text(lead.get("department"))
    seniority = _clean_text(lead.get("seniority"))
    if seniority and department:
        return f"{seniority.title()} - {department.title()}"
    if department:
        return f"{department.title()} Team"

    role_type = _clean_text(lead.get("type"))
    if role_type:
        return role_type.capitalize()

    return "Professional Contact"


def _format_hunter_lead(lead: dict) -> dict:
    email = str(lead.get("value", "")).strip()
    first_name = _clean_text(lead.get("first_name"))
    last_name = _clean_text(lead.get("last_name"))
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()

    # Hunter sometimes returns initials (e.g. "N") for last name; try to recover full names from source URLs.
    if len(last_name) <= 1:
        source_name = _derive_name_from_sources(lead)
        if source_name:
            full_name = source_name

    if not full_name:
        full_name = _derive_name_from_email(email)

    linkedin_url = _extract_linkedin_url_from_sources(lead)

    return {
        "person_name": full_name,
        "role": _derive_role_from_hunter(lead),
        "email": email,
        "confidence": str(lead.get("confidence", "low")).strip() or "low",
        "source": "hunter.io",
        "linkedin_url": linkedin_url,
        "avatar_url": _derive_avatar_url(lead),
    }


def tool_email_finder(company_name: str, website: str, icp: str = "") -> list:
    """
    Finds relevant professional email addresses using Hunter.io domain search.
    """
    print(f"Executing tool_email_finder for {company_name} with ICP: {icp}")

    hunter_api_key = os.getenv("HUNTER_API_KEY")
    if not hunter_api_key or hunter_api_key == "your_hunter_api_key":
        raise ValueError("HUNTER_API_KEY is not configured.")

    domain = _extract_domain(website)
    if not domain:
        return []

    response = requests.get(
        "https://api.hunter.io/v2/domain-search",
        params={"domain": domain, "api_key": hunter_api_key},
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json().get("data", {})
    emails = payload.get("emails", [])

    formatted_leads = []
    for lead in emails:
        email = str(lead.get("value", "")).strip()
        if not email:
            continue

        formatted = _format_hunter_lead(lead)
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", formatted["email"]):
            continue

        verification_status = str(lead.get("verification", {}).get("status", "")).strip().lower()
        if verification_status in {"invalid", "disposable", "reject_all"}:
            continue

        formatted_leads.append(formatted)

    def _confidence_rank(item: dict) -> int:
        raw = str(item.get("confidence", "")).strip().lower()
        if raw.isdigit():
            return int(raw)
        return {"high": 90, "medium": 70, "low": 40}.get(raw, 0)

    formatted_leads.sort(key=lambda item: _confidence_rank(item), reverse=True)

    prioritized = _prioritize_personal_emails(formatted_leads)
    if prioritized:
        return prioritized[:5]

    # Minimal fallback only when Hunter returns no usable emails.
    return [
        {
            "person_name": "Team",
            "role": "General inquiry",
            "email": f"info@{domain}",
            "confidence": "low",
            "source": "domain fallback",
            "linkedin_url": "",
            "avatar_url": "",
        }
    ]
