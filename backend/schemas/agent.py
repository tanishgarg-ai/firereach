"""
Pydantic schemas for the FireReach agent and related endpoints.
"""

from pydantic import BaseModel


class AgentRequest(BaseModel):
    """
    Request model for triggering the automated agent workflow.
    """
    icp: str
    send_mode: str = "auto"
    target_company: str = ""
    test_recipient_email: str = ""


class SelectCompanyRequest(BaseModel):
    """
    Request model for manually continuing the workflow with a selected company.
    """
    icp: str
    send_mode: str = "manual"
    selected_company: dict


class ManualSendRequest(BaseModel):
    """
    Request model for manually sending an outreach email.
    """
    recipient: str
    subject: str
    email_content: str
    pdf_filename: str = ""
