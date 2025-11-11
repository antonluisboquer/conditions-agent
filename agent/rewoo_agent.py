"""Planner, worker, solver, and store nodes for the ReWOO agent."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agent.rewoo_state import ReWOOEvidence, ReWOOPlan, ReWOOPlanStep, ReWOOState
from agent.tools import ConditionsAgentTools
from config.llm import planner_llm, solver_llm
from utils.logging_config import get_logger
from utils.transformers import extract_fulfilled_and_not_fulfilled, format_condition_for_frontend
from utils.tracing import trace_agent_execution

logger = get_logger(__name__)

DEFAULT_PLAN_STEPS: List[ReWOOPlanStep] = [
    {
        "id": "step_preconditions",
        "description": "Predict deficient conditions using PreConditions.",
        "tool": "call_preconditions_api",
        "input": {"metadata": {}},
    },
    {
        "id": "step_conditions_ai",
        "description": "Evaluate predicted conditions against uploaded documents.",
        "tool": "call_conditions_ai_api",
        "input": {"from_step": "step_preconditions"},
    },
]


def _build_default_plan(metadata: Dict[str, Any], s3_pdf_paths: List[str]) -> ReWOOPlan:
    steps = []
    for step in DEFAULT_PLAN_STEPS:
        step_copy = dict(step)
        step_input = dict(step_copy.get("input", {}))
        if step_copy["tool"] == "call_preconditions_api":
            step_input["metadata"] = metadata
        elif step_copy["tool"] == "call_conditions_ai_api":
            step_input["documents"] = s3_pdf_paths
        step_copy["input"] = step_input
        steps.append(step_copy)
    return {
        "summary": "Predict conditions using PreConditions then evaluate with Conditions AI.",
        "steps": steps,
    }


def _stringify_llm_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text") or "")
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def _parse_plan_from_llm(raw_text: str, metadata: Dict[str, Any], s3_pdf_paths: List[str]) -> Optional[ReWOOPlan]:
    if not raw_text:
        return None

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        newline_idx = cleaned.find("\n")
        if newline_idx != -1:
            cleaned = cleaned[newline_idx + 1 :].strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Planner LLM did not return JSON. Falling back to default plan.")
        return None

    steps = parsed.get("steps")
    if not isinstance(steps, list):
        logger.warning("Planner result missing steps array. Falling back to default plan.")
        return None

    normalized_steps: List[ReWOOPlanStep] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        tool = step.get("tool")
        if not tool:
            continue
        step_id = step.get("id") or f"step_{index}"
        step_input = step.get("input", {})
        if tool == "call_preconditions_api":
            step_input = step_input or {}
            step_input.setdefault("metadata", metadata)
        elif tool == "call_conditions_ai_api":
            step_input = step_input or {}
            step_input.setdefault("documents", s3_pdf_paths)
            step_input.setdefault("from_step", "step_preconditions")
        normalized_steps.append(
            {
                "id": step_id,
                "description": step.get("description", ""),
                "tool": tool,
                "input": step_input,
            }
        )

    if not normalized_steps:
        return None

    return {
        "summary": parsed.get("summary"),
        "steps": normalized_steps,
    }


@trace_agent_execution(name="rewoo_planner")
async def planner_node(state: ReWOOState) -> Dict[str, Any]:
    """Use an LLM planner to create a tool execution plan."""
    metadata = state.get("metadata", {})
    instructions = state.get("instructions") or "Evaluate loan conditions."
    s3_pdf_paths = state.get("s3_pdf_paths", [])

    plan: Optional[ReWOOPlan] = None
    reasoning: Optional[str] = None

    if planner_llm:
        prompt = (
            "You are orchestrating a loan conditions evaluation workflow.\n"
            "Available tools:\n"
            "1. call_preconditions_api(metadata) -> Predict deficient conditions.\n"
            "2. call_conditions_ai_api(preconditions_output, documents) -> Evaluate documents.\n"
            "3. retrieve_s3_document(path) -> Fetch additional documents (optional).\n"
            "4. query_database(query) -> Retrieve historical context (optional).\n\n"
            "Always produce a JSON object with keys 'summary' and 'steps'. Each step must include "
            "'id', 'tool', 'description', and 'input'. Ensure the workflow includes the PreConditions "
            "prediction before evaluating with Conditions AI.\n\n"
            f"Metadata: {json.dumps(metadata, default=str)}\n"
            f"Instructions: {instructions}\n"
            f"Documents: {json.dumps(s3_pdf_paths, default=str)}\n\n"
            "Respond with JSON only."
        )
        try:
            response = await planner_llm.ainvoke(prompt)
            raw_text = _stringify_llm_content(response.content)
            plan = _parse_plan_from_llm(raw_text, metadata, s3_pdf_paths)
            reasoning = raw_text
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Planner LLM failed, using fallback plan. Error: %s", exc)

    if plan is None:
        plan = _build_default_plan(metadata, s3_pdf_paths)
        reasoning = "Used deterministic fallback plan."

    logger.info("Planner produced %d steps.", len(plan.get("steps", [])))

    return {
        "plan": plan,
        "planning_reasoning": reasoning,
        "stage": "planning_complete",
        "status": state.get("status", "running"),
    }


@trace_agent_execution(name="rewoo_worker")
async def worker_node(state: ReWOOState) -> Dict[str, Any]:
    """Execute the previously planned steps sequentially."""
    metadata = state.get("metadata", {})
    s3_pdf_paths = state.get("s3_pdf_paths", [])

    plan = state.get("plan") or _build_default_plan(metadata, s3_pdf_paths)
    steps = plan.get("steps", [])

    tools = ConditionsAgentTools(default_documents=s3_pdf_paths)
    evidence: Dict[str, Any] = state.get("evidence", {})
    evidence_log: List[ReWOOEvidence] = state.get("evidence_log", [])

    for step in steps:
        step_id = step.get("id", "step")
        tool_name = step.get("tool")
        payload = dict(step.get("input") or {})

        logger.info("Executing ReWOO step %s using tool %s", step_id, tool_name)

        try:
            if tool_name == "call_preconditions_api":
                payload.setdefault("metadata", metadata)
                result = await tools.call_preconditions_api(payload)
            elif tool_name == "call_conditions_ai_api":
                existing_output = payload.get("preconditions_output")
                if isinstance(existing_output, str):
                    payload.pop("preconditions_output")
                if "preconditions_output" not in payload:
                    from_step = payload.get("from_step")
                    if isinstance(from_step, int):
                        from_step = str(from_step)
                    if from_step and from_step in evidence:
                        payload["preconditions_output"] = evidence[from_step]
                    elif from_step and f"step_{from_step}" in evidence:
                        payload["preconditions_output"] = evidence[f"step_{from_step}"]
                    elif evidence:
                        latest_key = list(evidence.keys())[-1]
                        payload["preconditions_output"] = evidence[latest_key]
                    else:
                        payload["preconditions_output"] = {}
                payload.setdefault("documents", s3_pdf_paths)
                result = await tools.call_conditions_ai_api(payload)
            elif tool_name == "retrieve_s3_document":
                result = await tools.retrieve_s3_document(payload)
            elif tool_name == "query_database":
                result = await tools.query_database(payload)
            else:
                result = {
                    "status": "skipped",
                    "reason": f"Unknown tool '{tool_name}'.",
                }
        except Exception as exc:
            logger.error("Error executing tool %s: %s", tool_name, exc, exc_info=True)
            return {
                "evidence": evidence,
                "evidence_log": evidence_log,
                "error": str(exc),
                "status": "failed",
                "stage": "failed",
            }

        evidence[step_id] = result
        evidence_log.append(
            {
                "step_id": step_id,
                "tool": tool_name or "unknown",
                "output": result,
                "completed_at": datetime.utcnow().isoformat(),
            }
        )

    return {
        "evidence": evidence,
        "evidence_log": evidence_log,
        "stage": "worker_complete",
        "status": state.get("status", "running"),
    }


def _build_solver_prompt(state: ReWOOState) -> str:
    metadata = state.get("metadata", {})
    instructions = state.get("instructions") or "Evaluate the loan conditions."
    plan = state.get("plan", {})
    evidence = state.get("evidence", {})

    return (
        "You are the solver for a loan-conditions evaluation agent. Using the plan and evidence, "
        "summarise the outcome of the evaluation. Provide:\n"
        "1. A concise summary.\n"
        "2. Key findings (fulfilled vs not fulfilled conditions).\n"
        "3. Any missing information or follow-up actions.\n\n"
        f"Metadata: {json.dumps(metadata, default=str)}\n"
        f"Instructions: {instructions}\n"
        f"Plan: {json.dumps(plan, default=str)}\n"
        f"Evidence: {json.dumps(evidence, default=str)}\n"
    )


@trace_agent_execution(name="rewoo_solver")
async def solver_node(state: ReWOOState) -> Dict[str, Any]:
    """Use the solver LLM to synthesise evidence into a final response."""
    evidence = state.get("evidence", {})
    plan = state.get("plan", {})

    solver_summary: Optional[str] = None

    if solver_llm:
        prompt = _build_solver_prompt(state)
        try:
            response = await solver_llm.ainvoke(prompt)
            solver_summary = _stringify_llm_content(response.content).strip()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Solver LLM failed: %s", exc)

    if not solver_summary:
        solver_summary = "Conditions evaluation completed using collected evidence."

    conditions_ai_result: Optional[Dict[str, Any]] = None
    for step in plan.get("steps", []):
        if step.get("tool") == "call_conditions_ai_api":
            step_id = step.get("id")
            if step_id and step_id in evidence:
                conditions_ai_result = evidence[step_id]
                break

    fulfilled: List[Dict[str, Any]] = []
    not_fulfilled: List[Dict[str, Any]] = []
    formatted_conditions: List[Dict[str, Any]] = []

    if isinstance(conditions_ai_result, dict):
        fulfilled, not_fulfilled = extract_fulfilled_and_not_fulfilled(conditions_ai_result)
        for cond in fulfilled:
            formatted_conditions.append(format_condition_for_frontend(cond, is_fulfilled=True))
        for cond in not_fulfilled:
            formatted_conditions.append(format_condition_for_frontend(cond, is_fulfilled=False))

    solver_payload = {
        "summary": solver_summary,
        "fulfilled_count": len(fulfilled),
        "not_fulfilled_count": len(not_fulfilled),
        "conditions": formatted_conditions,
    }

    return {
        "solver_response": solver_payload,
        "stage": "solver_complete",
        "status": state.get("status", "running"),
    }


@trace_agent_execution(name="rewoo_store_results")
async def store_results_node(state: ReWOOState) -> Dict[str, Any]:
    """Prepare final response payload."""
    solver_response = state.get("solver_response", {})
    plan = state.get("plan", {})
    evidence = state.get("evidence", {})

    execution_metadata = state.get("execution_metadata", {})
    started_at = execution_metadata.get("started_at") or datetime.utcnow()
    completed_at = datetime.utcnow()
    execution_metadata = dict(execution_metadata)
    execution_metadata["completed_at"] = completed_at
    execution_metadata["latency_ms"] = int((completed_at - started_at).total_seconds() * 1000)

    final_results = {
        "execution_id": execution_metadata.get("execution_id"),
        "status": "completed",
        "summary": solver_response.get("summary"),
        "fulfilled_count": solver_response.get("fulfilled_count"),
        "not_fulfilled_count": solver_response.get("not_fulfilled_count"),
        "conditions": solver_response.get("conditions"),
        "plan": plan,
        "evidence": evidence,
    }

    return {
        "final_results": final_results,
        "execution_metadata": execution_metadata,
        "stage": "completed",
        "status": "completed",
    }


def initialise_rewoo_state(
    metadata: Dict[str, Any],
    s3_pdf_paths: List[str],
    instructions: Optional[str] = None,
    output_destination: Optional[str] = None,
) -> ReWOOState:
    """Build initial state with execution metadata populated."""
    execution_id = str(uuid4())
    return {
        "metadata": metadata,
        "instructions": instructions,
        "s3_pdf_paths": s3_pdf_paths,
        "output_destination": output_destination,
        "stage": "planning",
        "status": "running",
        "execution_metadata": {
            "execution_id": execution_id,
            "started_at": datetime.utcnow(),
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "model_breakdown": {},
        },
    }


