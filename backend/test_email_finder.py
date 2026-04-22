import asyncio
from tools.email_finder import tool_email_finder
import json
from dotenv import load_dotenv

load_dotenv()


async def main():
    print("Testing Hunter.io email finder with REAL API KEYS...")
    company = "Google"
    website = "https://www.google.com"
    icp = "Cybersecurity training for enterprise teams"

    result = await asyncio.to_thread(tool_email_finder, company, website, icp)
    print("\n--- FINAL RAW OUTPUT FROM AI ---")
    print(type(result))
    if isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
