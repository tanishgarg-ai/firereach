import json
import requests
import streamlit as st
import os

# --- Configuration ---
st.set_page_config(page_title="FireReach Agent", page_icon="🔥", layout="wide")

DEFAULT_BACKEND_URL = "http://localhost:8000"

if "backend_url" not in st.session_state:
    st.session_state.backend_url = DEFAULT_BACKEND_URL

if "workflow_result" not in st.session_state:
    st.session_state.workflow_result = None

if "manual_state" not in st.session_state:
    st.session_state.manual_state = None


# --- Sidebar ---
with st.sidebar:
    st.title("🔥 FireReach Settings")
    st.session_state.backend_url = st.text_input("Backend API URL", value=st.session_state.backend_url)
    test_email = st.text_input("Test Recipient Email (Optional)", help="Forces outreach to go to this email instead of the found contact.")
    st.markdown("---")
    st.info("FireReach Autonomous Outreach Engine\n\n1. Input ICP\n2. Agent harvests signals\n3. Agent researches accounts\n4. Agent generates personalized email")


# --- Main Application ---
st.title("Targeting & Outreach Workflow")

# Input Form
with st.form("agent_form"):
    icp_input = st.text_area(
        "Ideal Customer Profile (ICP)",
        value="We sell high-end cybersecurity training to Series B startups.",
        height=100
    )
    
    col1, col2 = st.columns(2)
    with col1:
        send_mode = st.radio("Send Mode", options=["auto", "manual"], index=1, help="Auto selects top company and sends immediately. Manual lets you pick and review.")
    with col2:
        target_company = st.text_input("Target Company (Optional)", help="Skip discovery and target a specific company.")
        
    submitted = st.form_submit_button("Launch Agent 🚀")

# Action Handlers
if submitted:
    st.session_state.workflow_result = None
    st.session_state.manual_state = None
    
    payload = {
        "icp": icp_input,
        "send_mode": send_mode,
        "target_company": target_company,
        "test_recipient_email": test_email
    }
    
    # UI Placeholders for streaming
    status_container = st.status("Agent initialized. Connecting to backend...", expanded=True)
    
    try:
        url = f"{st.session_state.backend_url}/run-agent?stream=true"
        with requests.post(url, json=payload, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line:
                    event = json.loads(line.decode('utf-8'))
                    
                    if event.get("type") == "step":
                        step = event.get("step", "")
                        status = event.get("status", "")
                        msg = event.get("message", "")
                        
                        if status == "in-progress":
                            status_container.update(label=f"⏳ **{step.upper()}**: {msg}", state="running")
                        elif status == "completed":
                            status_container.write(f"✅ **{step.upper()}**: {msg}")
                        elif status == "failed":
                            status_container.write(f"❌ **{step.upper()}**: {msg}")
                            
                    elif event.get("type") == "result":
                        st.session_state.workflow_result = event.get("data")
                        
                    elif event.get("type") == "error":
                        status_container.update(label="Workflow Error", state="error")
                        st.error(event.get("message"))
                        
        status_container.update(label="Workflow processing complete.", state="complete")
    except requests.exceptions.RequestException as e:
        status_container.update(label="Connection Error", state="error")
        st.error(f"Failed to connect to backend: {e}")


# --- Results Rendering ---
if st.session_state.workflow_result:
    result = st.session_state.workflow_result
    st.markdown("---")
    st.header("Results")
    
    if result.get("status") == "awaiting_company_selection":
        st.subheader("Manual Mode: Select a Company")
        rankings = result.get("rankings", [])
        
        if not rankings:
            st.warning("No companies found.")
        else:
            # Display Rankings Table
            import pandas as pd
            df = pd.DataFrame(rankings)
            display_df = df[["rank", "company_name", "signal_score", "icp_score", "final_score", "score_reason"]]
            st.dataframe(display_df, hide_index=True, use_container_width=True)
            
            st.markdown("### Choose Target")
            company_names = [c["company_name"] for c in rankings]
            selected_name = st.selectbox("Company to target", options=company_names)
            
            if st.button("Continue with Selected Company"):
                selected_company = next(c for c in result["companies"] if c["company_name"] == selected_name)
                
                with st.spinner("Finding contacts and generating email draft..."):
                    payload = {
                        "icp": result["icp"],
                        "send_mode": "manual",
                        "selected_company": selected_company
                    }
                    try:
                        res = requests.post(f"{st.session_state.backend_url}/select-company", json=payload)
                        res.raise_for_status()
                        st.session_state.manual_state = res.json()
                        st.rerun()
                    except requests.exceptions.RequestException as e:
                        st.error(f"Error fetching company details: {e}")

    elif result.get("status") in ("completed", "partial"):
        st.success("Automated workflow completed!")
        st.json(result.get("summary"))
        # Display the processed company
        for comp in result.get("companies", []):
            if comp.get("company_name") == result.get("selected_company_name"):
                st.subheader(f"Outreach for {comp.get('company_name')}")
                outreach = comp.get("outreach", {})
                st.write(f"**Status:** {outreach.get('status')}")
                st.write(f"**Recipient:** {outreach.get('recipient')}")
                st.write(f"**Subject:** {outreach.get('subject')}")
                st.text_area("Email Content", value=outreach.get("email_content", ""), height=300, disabled=True)

# --- Manual Send Rendering ---
if st.session_state.manual_state:
    st.markdown("---")
    state = st.session_state.manual_state
    
    st.header(f"Draft for {state.get('selected_company', {}).get('company_name', 'Unknown')}")
    
    # Contact info
    suggested_contact = state.get("suggested_contact", {})
    st.info(f"**Suggested Contact:** {suggested_contact.get('email', 'None found')} (Confidence: {suggested_contact.get('confidence', 'N/A')})")
    
    outreach = state.get("outreach", {})
    
    with st.form("manual_send_form"):
        st.subheader("Review and Edit")
        recipient = st.text_input("Recipient Email", value=suggested_contact.get("email", ""))
        subject = st.text_input("Subject", value=outreach.get("subject", ""))
        email_content = st.text_area("Email Body", value=outreach.get("email_content", ""), height=300)
        
        if st.form_submit_button("Send Email ✉️"):
            with st.spinner("Sending..."):
                payload = {
                    "recipient": recipient,
                    "subject": subject,
                    "email_content": email_content,
                    "pdf_filename": outreach.get("pdf_filename", "")
                }
                try:
                    res = requests.post(f"{st.session_state.backend_url}/send-email", json=payload)
                    res.raise_for_status()
                    send_result = res.json()
                    if send_result.get("status") == "sent":
                        st.success("Email sent successfully!")
                    else:
                        st.error(f"Failed to send: {send_result.get('message', 'Unknown error')}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Send request failed: {e}")
