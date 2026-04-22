import asyncio
import json
import os
from dotenv import load_dotenv

# Load env variables for local testing
load_dotenv()

from agent import run_agent_workflow

async def main():
    print("Testing FireReach agent workflow...")
    icp = "We sell high-end cybersecurity training to Series B startups."
    result = await run_agent_workflow(icp)
    
    print("\n--- Test Results ---")
    print(f"Status: {result.get('status')}")
    print(f"\nSummary: {json.dumps(result.get('summary'), indent=2)}")
    print(f"\nCompanies: {json.dumps(result.get('companies'), indent=2)}")
    print("--------------------")
    
    if result.get('status') in ['completed', 'partial']:
        print("Integration test passed.")
    else:
        print("Integration test failed: Unexpected status")

if __name__ == "__main__":
    asyncio.run(main())
