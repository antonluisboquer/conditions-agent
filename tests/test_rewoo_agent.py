import asyncio
from typing import Any, Dict

import pytest

from agent.rewoo_graph import run_rewoo_agent


@pytest.mark.asyncio
async def test_run_rewoo_agent_fallback(monkeypatch):
    sample_metadata: Dict[str, Any] = {
        "loan_program": "Flex Supreme",
        "classification": "1120 Corporate Tax Return",
        "borrower_info": {"first_name": "Test", "last_name": "Borrower"},
    }

    preconditions_output = {
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

    conditions_ai_output = {
        "processed_conditions": [
            {
                "condition_id": "cond_001",
                "title": "Provide proof of income",
                "description": "Proof of income for primary borrower.",
                "category": "Income",
                "document_status": "fulfilled",
                "analysis_metadata": {
                    "result_confidence": 0.95,
                    "model_used": "test-model",
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

    async def fake_predict_conditions(_: Dict[str, Any]) -> Dict[str, Any]:
        return preconditions_output

    async def fake_conditions_ai_evaluate(_: Dict[str, Any]) -> Dict[str, Any]:
        return conditions_ai_output

    monkeypatch.setattr("agent.rewoo_agent.planner_llm", None)
    monkeypatch.setattr("agent.rewoo_agent.solver_llm", None)
    monkeypatch.setattr(
        "agent.tools.preconditions_client.predict_conditions",
        fake_predict_conditions,
    )
    monkeypatch.setattr(
        "agent.tools.conditions_ai_client.evaluate",
        fake_conditions_ai_evaluate,
    )

    final_state = await run_rewoo_agent(
        metadata=sample_metadata,
        s3_pdf_paths=["s3://demo-bucket/sample.pdf"],
        instructions="Evaluate the loan conditions.",
    )

    assert final_state["status"] == "completed"

    plan = final_state.get("plan", {})
    evidence = final_state.get("evidence", {})

    print("\n--- Planner Output ---")
    print("Summary:", plan.get("summary"))
    for step in plan.get("steps", []):
        print(f"{step['id']}: {step['tool']} -> {step['description']}")

    print("\n--- Worker Evidence ---")
    for step_id, output in evidence.items():
        print(f"{step_id}: keys={list(output.keys())}")

    results = final_state.get("final_results", {})
    assert results.get("fulfilled_count") == 1
    assert results.get("not_fulfilled_count") == 0
    assert isinstance(results.get("conditions"), list)

