"""LangGraph definition for Conditions Agent."""
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import (
    load_conditions_node,
    load_documents_node,
    call_conditions_ai_node,
    apply_guardrails_node,
    confidence_router_node,
    human_review_node,
    store_results_node
)
from utils.logging_config import get_logger
from utils.tracing import tracing_manager
from database.repository import db_repository

logger = get_logger(__name__)


def create_conditions_agent_graph():
    """
    Create the Conditions Agent LangGraph.
    
    Returns:
        Compiled LangGraph ready for execution
    """
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("load_conditions", load_conditions_node)
    workflow.add_node("load_documents", load_documents_node)
    workflow.add_node("call_conditions_ai", call_conditions_ai_node)
    workflow.add_node("apply_guardrails", apply_guardrails_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("store_results", store_results_node)
    
    # Set entry point
    workflow.set_entry_point("load_conditions")
    
    # Add edges
    workflow.add_edge("load_conditions", "load_documents")
    workflow.add_edge("load_documents", "call_conditions_ai")
    workflow.add_edge("call_conditions_ai", "apply_guardrails")
    
    # Add conditional edge for routing
    workflow.add_conditional_edges(
        "apply_guardrails",
        confidence_router_node,
        {
            "human_review": "human_review",
            "store_results": "store_results"
        }
    )
    
    # Both paths lead to store_results, then END
    workflow.add_edge("human_review", "store_results")
    workflow.add_edge("store_results", END)
    
    # Compile graph
    app = workflow.compile()
    
    logger.info("Conditions Agent graph created successfully")
    return app


async def run_conditions_agent(
    loan_guid: str,
    condition_doc_ids: list[str]
) -> Dict[str, Any]:
    """
    Run the Conditions Agent for a loan.
    
    Args:
        loan_guid: Unique loan identifier
        condition_doc_ids: List of condition document IDs
        
    Returns:
        Final agent state with results
    """
    logger.info(f"Starting Conditions Agent for loan {loan_guid}")
    
    # Create execution record in database
    execution = db_repository.create_execution(loan_guid=loan_guid)
    execution_id = str(execution.execution_id)
    
    # Initialize state
    initial_state: AgentState = {
        "loan_guid": loan_guid,
        "condition_doc_ids": condition_doc_ids,
        "requires_human_review": False,
        "validation_issues": [],
        "status": "running",
        "execution_metadata": {
            "execution_id": execution_id,
            "started_at": datetime.utcnow(),
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "model_breakdown": {}
        }
    }
    
    # Add tracing tags
    tracing_manager.add_tags({
        "loan_guid": loan_guid,
        "execution_id": execution_id
    })
    
    try:
        # Create and run graph
        app = create_conditions_agent_graph()
        
        # Run the graph
        final_state = await app.ainvoke(initial_state)
        
        # Update execution metadata
        final_state["execution_metadata"]["completed_at"] = datetime.utcnow()
        
        # Calculate total latency
        started_at = final_state["execution_metadata"]["started_at"]
        completed_at = final_state["execution_metadata"]["completed_at"]
        total_latency_ms = int((completed_at - started_at).total_seconds() * 1000)
        final_state["execution_metadata"]["latency_ms"] = total_latency_ms
        
        # Log completion metrics
        tracing_manager.log_metrics({
            "total_tokens": final_state["execution_metadata"]["total_tokens"],
            "cost_usd": final_state["execution_metadata"]["cost_usd"],
            "latency_ms": total_latency_ms,
            "status": final_state["status"],
            "requires_review": final_state.get("requires_human_review", False)
        })
        
        logger.info(
            f"Conditions Agent completed for loan {loan_guid}: "
            f"status={final_state['status']}, "
            f"evaluations={len(final_state.get('evaluations', []))}, "
            f"cost=${final_state['execution_metadata']['cost_usd']:.4f}"
        )
        
        return final_state
        
    except Exception as e:
        logger.error(f"Error running Conditions Agent: {e}", exc_info=True)
        
        # Update execution status to failed
        db_repository.update_execution_status(
            execution_id=execution_id,
            status="failed",
            error_message=str(e)
        )
        
        raise


# Create global graph instance
conditions_agent_graph = create_conditions_agent_graph()

