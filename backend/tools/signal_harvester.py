import os
import time

import requests

SIGNAL_QUERIES = {
    "S1": {
        "label": "Hiring signals",
        "query": '"{company}" (hiring OR careers OR jobs OR expansion OR headcount)',
        "news": False,
    },
    "S2": {
        "label": "Funding signals",
        "query": '"{company}" (funding OR investment OR investors OR series A OR series B OR raised)',
        "news": True,
    },
    "S3": {
        "label": "Leadership/People signals",
        "query": '"{company}" (leadership OR appointed OR joined as OR chief executive OR executive team)',
        "news": True,
    },
    "S4": {
        "label": "Product launch signals",
        "query": '"{company}" (launch OR launched OR release OR product update OR new feature)',
        "news": True,
    },
    "S5": {
        "label": "Tech stack signals",
        "query": '"{company}" ("tech stack" OR infrastructure OR platform OR engineering OR developer tools)',
        "news": False,
    },
    "S6": {
        "label": "Market reputation signals",
        "query": '"{company}" (reviews OR partnership OR customers OR reputation OR social mentions)',
        "news": False,
    },
}


def _extract_signal_result(data: dict) -> dict:
    for collection in ("news", "organic"):
        for item in data.get(collection, []):
            title = str(item.get("title", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            source = item.get("link") or item.get("displayed_link") or ""

            if not source:
                source_info = item.get("source")
                if isinstance(source_info, dict):
                    source = source_info.get("name", "")
                elif isinstance(source_info, str):
                    source = source_info

            content = ". ".join(part for part in [title, snippet] if part).strip()
            if len(content) > 20:
                return {
                    "content": content,
                    "source": source,
                }

    return {
        "content": "",
        "source": "",
    }


def _run_serp_query(params: dict, retries: int = 2, timeout_seconds: int = 30) -> dict:
    last_error = None
    endpoint = params["endpoint"]
    headers = params["headers"]
    payload = {
        "q": params["q"],
        "num": params["num"],
    }

    for attempt in range(retries + 1):
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))

    raise last_error


def tool_signal_harvester(company_name: str, website: str = "") -> dict:
    """
    Collects real company signals from Serper.dev and maps them into S1-S6 categories.
    """
    print(f"Executing tool_signal_harvester for {company_name}")

    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key or serper_api_key == "your_serper_api_key_here":
        raise ValueError("SERPER_API_KEY is not configured. FireReach requires live signal harvesting.")

    signals = {}

    for signal_code, config in SIGNAL_QUERIES.items():
        params = {
            "q": config["query"].format(company=company_name),
            "num": 5,
            "headers": {
                "X-API-KEY": serper_api_key,
                "Content-Type": "application/json",
            },
            "endpoint": "https://google.serper.dev/news" if config["news"] else "https://google.serper.dev/search",
        }

        try:
            raw_payload = _run_serp_query(params)
            result = _extract_signal_result(raw_payload)
        except requests.RequestException as exc:
            # Keep workflow alive on network/timeouts without inventing synthetic signal text.
            result = {
                "content": "",
                "source": "",
                "error": str(exc),
            }

        result["label"] = config["label"]
        result["website"] = website
        signals[signal_code] = result

    return signals
