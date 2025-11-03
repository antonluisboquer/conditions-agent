"""LangGraph definition for Conditions Agent with streaming support."""
from datetime import datetime
from typing import Dict, Any, AsyncIterator
from uuid import uuid4
from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes import (
    call_preconditions_node,
    transform_output_node,
    call_conditions_ai_node,
    classify_results_node,
    confidence_router_node,
    auto_approve_node,
    human_review_node,
    store_results_node
)
from utils.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


def create_conditions_agent_graph():
    """
    Create the Conditions Agent LangGraph with streaming support.
    
    Workflow:
    1. call_preconditions -> Predict conditions from PreConditions API
    2. transform_output -> Transform to Conditions AI format
    3. call_conditions_ai -> Evaluate via Airflow v5 + fetch S3
    4. classify_results -> Split fulfilled vs not fulfilled
    5. confidence_router -> Route based on classification
       - auto_approve -> All conditions fulfilled
       - human_review -> Some conditions need RM review
    6. store_results -> Save to database and return final results
    
    Returns:
        Compiled LangGraph ready for execution
    """
    logger.info("Creating Conditions Agent graph")
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("call_preconditions", call_preconditions_node)
    workflow.add_node("transform_output", transform_output_node)
    workflow.add_node("call_conditions_ai", call_conditions_ai_node)
    workflow.add_node("classify_results", classify_results_node)
    workflow.add_node("auto_approve", auto_approve_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("store_results", store_results_node)
    
    # Set entry point
    workflow.set_entry_point("call_preconditions")
    
    # Linear flow through first 4 nodes
    workflow.add_edge("call_preconditions", "transform_output")
    workflow.add_edge("transform_output", "call_conditions_ai")
    workflow.add_edge("call_conditions_ai", "classify_results")
    
    # Conditional routing based on classification
    workflow.add_conditional_edges(
        "classify_results",
        confidence_router_node,
        {
            "auto_approve": "auto_approve",
            "human_review": "human_review"
        }
    )
    
    # Both paths converge to store_results
    workflow.add_edge("auto_approve", "store_results")
    workflow.add_edge("human_review", "store_results")
    
    # Final edge to END
    workflow.add_edge("store_results", END)
    
    # Compile graph
    app = workflow.compile()
    
    logger.info("Conditions Agent graph created successfully")
    logger.info("Graph nodes: call_preconditions -> transform_output -> call_conditions_ai -> classify_results -> (auto_approve|human_review) -> store_results")
    
    return app


async def run_conditions_agent(
    preconditions_input: Dict[str, Any],
    s3_pdf_path: str
) -> Dict[str, Any]:
    """
    Run the Conditions Agent (non-streaming).
    
    Args:
        preconditions_input: Input containing borrower info, classification, 
                           extracted entities (from Rack & Stack)
        s3_pdf_path: S3 path to uploaded PDF
        
    Returns:
        Final agent state with results
    """
    execution_id = str(uuid4())
    
    logger.info("=" * 70)
    logger.info(f"STARTING CONDITIONS AGENT - Execution ID: {execution_id}")
    logger.info("=" * 70)
    logger.info(f"Classification: {preconditions_input.get('classification')}")
    logger.info(f"Loan Program: {preconditions_input.get('loan_program')}")
    logger.info(f"S3 PDF Path: {s3_pdf_path}")
    
    # Initialize state
    initial_state: AgentState = {
        "preconditions_input": preconditions_input,
        "s3_pdf_path": s3_pdf_path,
        "requires_human_review": False,
        "auto_approved_count": 0,
        "node_outputs": [],
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
    
    try:
        # Create and run graph
        app = create_conditions_agent_graph()
        
        # Run the graph (non-streaming)
        final_state = await app.ainvoke(initial_state)
        
        # Update execution metadata
        final_state["execution_metadata"]["completed_at"] = datetime.utcnow()
        
        # Calculate total latency
        started_at = final_state["execution_metadata"]["started_at"]
        completed_at = final_state["execution_metadata"]["completed_at"]
        total_latency_ms = int((completed_at - started_at).total_seconds() * 1000)
        final_state["execution_metadata"]["latency_ms"] = total_latency_ms
        
        logger.info("=" * 70)
        logger.info(f"CONDITIONS AGENT COMPLETED - Execution ID: {execution_id}")
        logger.info("=" * 70)
        logger.info(f"Status: {final_state.get('status')}")
        logger.info(f"Auto-approved: {final_state.get('auto_approved_count', 0)}")
        logger.info(f"Requires review: {final_state.get('requires_human_review', False)}")
        logger.info(f"Total latency: {total_latency_ms}ms")
        
        return final_state
        
    except Exception as e:
        logger.error(f"Error running Conditions Agent: {e}", exc_info=True)
        raise


async def run_conditions_agent_streaming(
    preconditions_input: Dict[str, Any],
    s3_pdf_path: str
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run the Conditions Agent with streaming output.
    
    This yields updates after each node completes, allowing the frontend
    to display real-time progress.
    
    Args:
        preconditions_input: Input containing borrower info, classification, 
                           extracted entities (from Rack & Stack)
        s3_pdf_path: S3 path to uploaded PDF
        
    Yields:
        Dict with node name, status, timestamp, and output after each node
    """
    execution_id = str(uuid4())
    
    logger.info("=" * 70)
    logger.info(f"STARTING CONDITIONS AGENT (STREAMING) - Execution ID: {execution_id}")
    logger.info("=" * 70)
    
    # Initialize state
    initial_state: AgentState = {
        "preconditions_input": preconditions_input,
        "s3_pdf_path": s3_pdf_path,
        "requires_human_review": False,
        "auto_approved_count": 0,
        "node_outputs": [],
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
    
    try:
        # Create graph
        app = create_conditions_agent_graph()
        
        # Stream events using astream
        async for event in app.astream(initial_state):
            # Each event is a dict with node name as key
            node_name = list(event.keys())[0]
            node_state = event[node_name]
            
            logger.info(f"Streaming update from node: {node_name}")
            
            # Yield the update to frontend
            yield {
                "node": node_name,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "execution_id": execution_id,
                "state": {
                    # Include relevant fields for frontend
                    "preconditions_output": node_state.get("preconditions_output"),
                    "transformed_input": node_state.get("transformed_input"),
                    "conditions_ai_output": node_state.get("conditions_ai_output"),
                    "fulfilled_conditions": node_state.get("fulfilled_conditions"),
                    "not_fulfilled_conditions": node_state.get("not_fulfilled_conditions"),
                    "final_results": node_state.get("final_results"),
                    "status": node_state.get("status"),
                    "error": node_state.get("error")
                }
            }
        
        logger.info("=" * 70)
        logger.info(f"CONDITIONS AGENT STREAMING COMPLETE - Execution ID: {execution_id}")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Error in streaming execution: {e}", exc_info=True)
        
        # Yield error event
        yield {
            "node": "error",
            "status": "failed",
            "timestamp": datetime.utcnow().isoformat(),
            "execution_id": execution_id,
            "error": str(e)
        }


# Create global graph instance
conditions_agent_graph = create_conditions_agent_graph()
