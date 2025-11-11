# ReWOO Agent Upgrade Summary

## Overview

We converted the original deterministic LangGraph orchestrator into a ReWOO-style agent that can plan, execute, and synthesize results. The new flow still relies on the existing PreConditions and Conditions AI services, but it now makes an LLM-guided decision on how to invoke them and returns richer evidence for downstream consumers.

```
Metadata + Instructions
        │
        ▼
  Planner (LLM)
        │ plan
        ▼
  Worker (Tools)
        │ evidence
        ▼
  Solver (LLM)
        │ summary
        ▼
  Store (Final Payload)
```

## Key Additions

- **State & Graph**
  - `agent/rewoo_state.py` – ReWOO-specific state schema.
  - `agent/rewoo_agent.py` – planner / worker / solver / store nodes plus helpers.
  - `agent/rewoo_graph.py` – LangGraph assembly with streaming + synchronous runners.
  - `agent/tools.py` – tool wrappers for PreConditions, Conditions AI, placeholders for S3 / DB.

- **Configuration**
  - `config/llm.py` – LangChain `ChatOpenAI` wrappers for planner and solver LLMs.
  - `config/settings.py` – new fields for OpenAI/Anthropic models, temperatures, etc.
  - `requirements.txt` – now includes `langchain-openai`.

- **API**
  - `/api/v1/evaluate-conditions` ⇒ ReWOO streaming endpoint.
  - `/api/v1/evaluate-conditions/run` ⇒ ReWOO non-streaming endpoint.
  - `/api/v1/evaluate-conditions/legacy` ⇒ legacy orchestrator (returns 410 to indicate the new path).
  - `/api/v1/evaluate-loan-conditions` remains unchanged for backward compatibility.

- **Testing & Scripts**
  - `tests/test_rewoo_agent.py` – unit test mocking both services.
  - `scripts/run_rewoo_plan_worker.py` – local harness to show planner/worker outputs (supports `--mock`).

## Planner Behaviour

- Planner prompt guides the LLM to output a JSON plan.
- If the planner LLM fails or returns invalid JSON, we fall back to the deterministic two-step plan (PreConditions → Conditions AI).

Example planner step (mock):
```json
{
  "id": "step_preconditions",
  "tool": "call_preconditions_api",
  "description": "Predict deficient conditions based on borrower metadata.",
  "input": {
    "metadata": { ... }
  }
}
```

## Worker Behaviour

- Executes each planned step in order.
- Attaches outputs to `evidence` using the step ID.
- Reuses existing service clients:
  - `call_preconditions_api` → LangGraph Cloud PreConditions client.
  - `call_conditions_ai_api` → Airflow v5 DAG.
  - Optional placeholders (`retrieve_s3_document`, `query_database`).
- Automatically passes PreConditions output into Conditions AI if the planner references it.
- No database writes yet; `store_results` just prepares the final payload.

## Solver & Store

- Solver LLM (or fallback) summarizes the evidence and provides counts for fulfilled / not-fulfilled conditions.
- Store node computes latencies, packages the final payload, and returns it to the API caller.

## Testing

```
/opt/homebrew/bin/python3.11 -m pytest tests/test_rewoo_agent.py
```

The test uses mocked PreConditions/Conditions AI responses to keep runs fast and predictable.

For ad-hoc testing:

- Mocked local harness: `scripts/run_rewoo_plan_worker.py --mock`
- Live services (will hit Airflow + LangGraph): `scripts/run_rewoo_plan_worker.py`

## Deployment Impact

- Legacy orchestrator endpoint still available via `/api/v1/evaluate-loan-conditions`.
- New ReWOO endpoints require OpenAI (planner/solver) and optional Anthropic (if you want to keep the routing fallback).
- No database schema changes yet—final results still live in memory.
- Airflow timeout remains 10 minutes; long-running DAGs will raise `TimeoutError`.

Use this document to communicate the new agent flow, files, and testing strategy to the team. Update it if additional tools or planner logic are added.

