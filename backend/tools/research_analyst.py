import json
from services.openai_client import generate_completion

def tool_research_analyst(icp: str, signals: dict, company_name: str = "") -> str:
    """
    Analyzes signals against the ICP to build a contextual account brief.
    """
    print("Executing tool_research_analyst.")
    
    signals_str = json.dumps(signals, indent=2)
    
    prompt = f"""
    You are an expert account research analyst for FireReach.
    Analyze the following verified company signals against the given Ideal Customer Profile (ICP).
    Create a detailed account brief that explains why this company fits the ICP based on the verified signals.

    Company:
    {company_name or 'Target company'}

    ICP:
    {icp}

    Verified Signals:
    {signals_str}

    Requirements:
    - Write 2 concise paragraphs.
    - Reference the strongest verified signals directly.
    - Explain why the company is a fit for the ICP.
    - Keep the tone professional and specific.
    - Output only the brief.
    """
    
    brief = generate_completion(
        prompt=prompt,
        system_prompt="You are a precise, analytical sales intelligence assistant.",
        temperature=0.7,
        max_tokens=300
    )
    
    return brief
