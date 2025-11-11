"""LangGraph assembly for the ReWOO Conditions Agent."""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

from langgraph.graph import StateGraph, END

from agent.rewoo_agent import (
    initialise_rewoo_state,
    planner_node,
    solver_node,
    store_results_node,
    worker_node,
)
from agent.rewoo_state import ReWOOState
from utils.logging_config import get_logger

logger = get_logger(__name__)


def create_rewoo_agent_graph() -> StateGraph[ReWOOState]:
    """Create and compile the ReWOO state graph."""
    workflow = StateGraph(ReWOOState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("solver", solver_node)
    workflow.add_node("store_results", store_results_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "worker")
    workflow.add_edge("worker", "solver")
    workflow.add_edge("solver", "store_results")
    workflow.add_edge("store_results", END)

    return workflow.compile()


async def run_rewoo_agent(
    metadata: Dict[str, Any],
    s3_pdf_paths: List[str],
    instructions: Optional[str] = None,
    output_destination: Optional[str] = None,
) -> ReWOOState:
    """Run the ReWOO agent synchronously and return the final state."""
    logger.info("Starting ReWOO agent run.")
    initial_state = initialise_rewoo_state(
        metadata=metadata,
        s3_pdf_paths=s3_pdf_paths,
        instructions=instructions,
        output_destination=output_destination,
    )

    workflow = create_rewoo_agent_graph()
    final_state = await workflow.ainvoke(initial_state)
    logger.info("ReWOO agent completed with status %s.", final_state.get("status"))
    return final_state


async def run_rewoo_agent_streaming(
    metadata: Dict[str, Any],
    s3_pdf_paths: List[str],
    instructions: Optional[str] = None,
    output_destination: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Run the ReWOO agent and stream intermediate events."""
    initial_state = initialise_rewoo_state(
        metadata=metadata,
        s3_pdf_paths=s3_pdf_paths,
        instructions=instructions,
        output_destination=output_destination,
    )
    workflow = create_rewoo_agent_graph()

    async for event in workflow.astream(initial_state):
        node_name = next(iter(event))
        node_state: Dict[str, Any] = event[node_name]
        stage = node_state.get("stage", "")

        logger.info("Streaming ReWOO event from node %s with stage %s.", node_name, stage)

        yield {
            "node": node_name,
            "stage": stage,
            "status": node_state.get("status"),
            "timestamp": node_state.get("execution_metadata", {}).get("completed_at"),
            "state": node_state,
        }


