"""
LLM prompts used by the FireReach agent and its tools.
"""
import json

def get_company_discovery_prompt(icp: str) -> str:
    """
    Generates the prompt for finding companies that match an ICP.

    Args:
        icp: The Ideal Customer Profile string.

    Returns:
        The formatted prompt string.
    """
    return f"""
You are FireReach's company discovery agent.
Analyze the Ideal Customer Profile below and return exactly 5 real companies that best match it.

Ideal Customer Profile:
{icp}

Requirements:
- Output exactly 5 companies.
- Use real, valid company names and official websites.
- Keep reasons professional, specific, and original.
- Return only a JSON array.
- Every object must include: company_name, industry, reason, website.
- Do not include markdown or commentary.
"""

def get_icp_scoring_prompt(icp: str, payload: list) -> str:
    """
    Generates the prompt for scoring a list of companies against an ICP.

    Args:
        icp: The Ideal Customer Profile string.
        payload: A list of company dictionaries to score.

    Returns:
        The formatted prompt string.
    """
    return f"""
You are FireReach's ICP scoring agent.
Score each company against the ICP on a 0-100 scale.

ICP:
{icp}

Companies:
{json.dumps(payload, ensure_ascii=True)}

Return ONLY a JSON array with exactly these fields per object:
- company_name
- icp_score (number 0-100)
- reason (short, specific)

Rules:
- Keep one object for each company.
- Base score on ICP fit using verified signals + research brief.
- No markdown.
"""
