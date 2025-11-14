#!/usr/bin/env python3
"""
Lightweight smoke test for the hosted LangGraph Cloud deployment using langgraph-sdk.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langgraph_sdk import get_client

load_dotenv()

DEPLOYMENT_URL = (
    os.getenv("LG_DEPLOYMENT_URL") or os.getenv("PRECONDITIONS_DEPLOYMENT_URL")
)
API_KEY = (
    os.getenv("LG_API_KEY") or os.getenv("PRECONDITIONS_LANGSMITH_API_KEY")
)
ASSISTANT_ID = (
    os.getenv("LG_ASSISTANT_ID") or os.getenv("PRECONDITIONS_ASSISTANT_ID")
)

PAYLOAD = {
    "metadata": {
        "conditions": [
            {
                "condition_id": 2,
                "condition_name": "Property: Title Company Documents",
                "description": "Wiring instructions from Title Company",
                "category": "Property",
            }
        ]
    },
    "s3_pdf_paths": [
        "s3://quick-quote-demo/mock/Wiring Instructions - demo.pdf"
    ],
    "instructions": "Validate this condition against the uploaded PDF.",
    "output_destination": "quick-quote-demo/mock/conditions_1.json",
}


async def main():
    if not DEPLOYMENT_URL or not API_KEY or not ASSISTANT_ID:
        raise SystemExit(
            "Missing LG_DEPLOYMENT_URL / LG_API_KEY / LG_ASSISTANT_ID env vars."
        )

    client = get_client(url=DEPLOYMENT_URL, api_key=API_KEY)

    thread = await client.threads.create()
    run = await client.runs.create(
        thread["thread_id"],
        assistant_id=ASSISTANT_ID,
        input=PAYLOAD,
    )
    await client.runs.join(thread["thread_id"], run["run_id"])
    state = await client.threads.get_state(thread["thread_id"])
    print(json.dumps(state["values"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())