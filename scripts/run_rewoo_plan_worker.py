#!/usr/bin/env python3
"""
Run the ReWOO agent with real inputs and display planner/worker outputs.

This script does not persist anything to the database; it only prints the
planner's plan and the worker's evidence in memory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

from agent.rewoo_agent import initialise_rewoo_state, planner_node, worker_node


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


async def run_rewoo(
    metadata_path: Path,
    documents: list[str],
    instructions: str | None,
    announce_live_calls: bool,
    use_mock: bool,
):
    metadata = _load_json(metadata_path)

    initial_state = initialise_rewoo_state(
        metadata=metadata,
        s3_pdf_paths=documents,
        instructions=instructions,
    )

    if use_mock:
        print("\n[Info] Using mocked PreConditions and Conditions AI responses (no live calls).")
        fake_preconditions = {
            "deficient_conditions": [
                {
                    "condition_id": "cond_001",
                    "condition_name": "Provide proof of income",
                    "compartment": "Income",
                    "actionable_instruction": "Upload W-2 documents.",
                }
            ],
            "compartments": [],
        }
        fake_conditions_ai = {
            "processed_conditions": [
                {
                    "condition_id": "cond_001",
                    "title": "Provide proof of income",
                    "description": "Proof of income for primary borrower.",
                    "category": "Income",
                    "document_status": "fulfilled",
                    "analysis_metadata": {
                        "result_confidence": 0.95,
                        "model_used": "mock-model",
                        "tokens_used": {},
                        "cost_usd": 0.0,
                        "latency_ms": 100,
                    },
                }
            ],
            "api_usage_summary": {
                "condition_analysis": {
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "total_latency_ms": 100,
                }
            },
        }
        with patch(
            "agent.tools.preconditions_client.predict_conditions",
            AsyncMock(return_value=fake_preconditions),
        ), patch(
            "agent.tools.conditions_ai_client.evaluate",
            AsyncMock(return_value=fake_conditions_ai),
        ):
            await _run_plan_and_worker(initial_state)
        return

    if announce_live_calls:
        print(
            "\n[Info] Running with live PreConditions and Conditions AI services."
            " This may take a while depending on network and Airflow queue time."
        )

    await _run_plan_and_worker(initial_state)


async def _run_plan_and_worker(initial_state):
    planner_result = await planner_node(initial_state)
    worker_input = dict(initial_state)
    worker_input.update(planner_result)
    worker_result = await worker_node(worker_input)

    plan = planner_result.get("plan", {})
    evidence = worker_result.get("evidence", {})

    print("\n=== PLANNER OUTPUT ===")
    print("Summary:", plan.get("summary"))
    for step in plan.get("steps", []):
        print(f"{step.get('id')}: {step.get('tool')} -> {step.get('description')}")

    step_ids = {step.get("tool") for step in plan.get("steps", [])}
    print("\nSelected tools:", ", ".join(sorted(t for t in step_ids if t)))

    print("\n=== WORKER EVIDENCE ===")
    for step_id, output in evidence.items():
        print(f"{step_id}: keys={list(output.keys())}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ReWOO planner + worker with real inputs.")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("preconditions_input.json"),
        help="Path to JSON file containing metadata (default: preconditions_input.json)",
    )
    parser.add_argument(
        "--documents",
        nargs="*",
        default=["s3://demo-bucket/sample.pdf"],
        help="List of S3 PDF paths (default: dummy sample path).",
    )
    parser.add_argument(
        "--instructions",
        type=str,
        default=None,
        help="Optional natural language instructions.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Mock PreConditions and Conditions AI calls for faster local runs.",
    )
    parser.add_argument(
        "--no-warning",
        action="store_true",
        help="Suppress the live service warning message.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    asyncio.run(
        run_rewoo(
            metadata_path=args.metadata,
            documents=args.documents,
            instructions=args.instructions,
            announce_live_calls=not args.no_warning,
            use_mock=args.mock,
        )
    )


if __name__ == "__main__":
    main()

