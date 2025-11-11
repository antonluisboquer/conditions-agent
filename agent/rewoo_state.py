"""State schema for the ReWOO-based Conditions Agent."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from agent.state import ExecutionMetadata


class ReWOOPlanStep(TypedDict, total=False):
    """Single step inside the planner output."""

    id: str
    description: str
    tool: str
    input: Dict[str, Any]


class ReWOOPlan(TypedDict, total=False):
    """Planner output containing ordered steps."""

    steps: List[ReWOOPlanStep]
    summary: Optional[str]


class ReWOOEvidence(TypedDict, total=False):
    """Evidence collected by the worker."""

    step_id: str
    tool: str
    output: Dict[str, Any]
    completed_at: str


class ReWOOState(TypedDict, total=False):
    """State passed between ReWOO planner, worker, solver, and store nodes."""

    # ====== Input ======
    metadata: Dict[str, Any]
    instructions: Optional[str]
    s3_pdf_paths: List[str]
    output_destination: Optional[str]

    # ====== Planner output ======
    plan: ReWOOPlan
    planning_reasoning: Optional[str]

    # ====== Worker output ======
    evidence: Dict[str, Any]
    evidence_log: List[ReWOOEvidence]

    # ====== Solver output ======
    solver_response: Dict[str, Any]
    final_results: Dict[str, Any]

    # ====== Execution tracking ======
    stage: str  # planning, working, solving, completed, failed
    execution_metadata: ExecutionMetadata

    # ====== Error handling ======
    error: Optional[str]
    status: str


