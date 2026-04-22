import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


DEFAULT_SMTP_TIMEOUT_SECONDS = 25


def send_email(to_email: str, subject: str, content: str, pdf_path: str = "") -> bool:
    """
    Sends an email using SMTP with optional PDF attachment.
    If credentials are missing or it fails, it prints to console for prototype purposes.
    """
    # Extract body text if content is JSON-formatted
    clean_content = str(content or "").strip()
    if clean_content.startswith("json{") or clean_content.startswith("{"):
        try:
            import json
            # Remove "json" prefix if present
            json_str = clean_content.replace("json{", "{", 1) if clean_content.startswith("json{") else clean_content
            parsed = json.loads(json_str)
            if isinstance(parsed, dict) and "body" in parsed:
                clean_content = str(parsed.get("body", "")).strip()
        except:
            pass  # Use original content if parsing fails
    
    smtp_server = os.getenv("EMAIL_SMTP_SERVER")
    smtp_port = os.getenv("EMAIL_SMTP_PORT", 587)
    from_email = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    try:
        smtp_timeout_seconds = int(os.getenv("EMAIL_SMTP_TIMEOUT_SECONDS", str(DEFAULT_SMTP_TIMEOUT_SECONDS)))
    except ValueError:
        smtp_timeout_seconds = DEFAULT_SMTP_TIMEOUT_SECONDS

    resolved_pdf_path = str(pdf_path or "").strip()
    has_valid_pdf = bool(resolved_pdf_path) and os.path.exists(resolved_pdf_path)

    # If any required credential is missing or set to placeholder
    if not all([smtp_server, from_email, password]) or smtp_server == "smtp.example.com":
        print("------------- EMAIL MOCK -------------")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Content:\n{clean_content}")
        if resolved_pdf_path:
            if has_valid_pdf:
                print(f"Attachment (mock): {os.path.basename(resolved_pdf_path)}")
            else:
                print(f"Attachment skipped, file not found (mock): {resolved_pdf_path}")
        print("--------------------------------------")
        return True

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(clean_content, "plain"))

    if has_valid_pdf:
        try:
            with open(resolved_pdf_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(resolved_pdf_path)}"',
            )
            msg.attach(part)
        except Exception as attach_error:
            print(f"Attachment skipped due to error: {attach_error}")

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port), timeout=smtp_timeout_seconds) as server:
            server.starttls()
            server.login(from_email, password)
            server.send_message(msg)
        print(f"Email successfully sent to {to_email} via SMTP")
        return True
    except Exception as error:
        print(f"Failed to send email to {to_email} via SMTP: {error}")
        return False
