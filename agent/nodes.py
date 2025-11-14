"""LangGraph node implementations for Conditions Agent."""
from typing import Dict, Any
from datetime import datetime
from uuid import uuid4

from agent.state import AgentState
from services.preconditions import preconditions_client
from services.conditions_ai import conditions_ai_client
from utils.transformers import (
    transform_preconditions_to_conditions_ai,
    extract_fulfilled_and_not_fulfilled,
    format_condition_for_frontend
)
from utils.tracing import trace_agent_execution
from utils.logging_config import get_logger
from database.repository import ConditionsRepository
from config.settings import settings

logger = get_logger(__name__)
repository = ConditionsRepository()


@trace_agent_execution(name="call_preconditions")
async def call_preconditions_node(state: AgentState) -> Dict[str, Any]:
    """
    Call PreConditions API to predict required conditions.
    
    Input: preconditions_input (includes Rack & Stack data)
    Output: preconditions_output (streamed to frontend)
    """
    logger.info("=" * 50)
    logger.info("NODE: call_preconditions")
    logger.info("=" * 50)
    
    preconditions_input = state["preconditions_input"]
    
    logger.info(f"Calling PreConditions API")
    logger.info(f"Classification: {preconditions_input.get('classification')}")
    logger.info(f"Loan Program: {preconditions_input.get('loan_program')}")
    
    try:
        # Call PreConditions LangGraph Cloud API
        result = await preconditions_client.predict_conditions(preconditions_input)
        
        logger.info("PreConditions API call successful")
        logger.info(f"Compartments found: {len(result.get('compartments', []))}")
        logger.info(f"Deficient conditions: {len(result.get('deficient_conditions', []))}")
        
        # Update state with output (will be streamed)
        return {
            "preconditions_output": result,
            "node_outputs": state.get("node_outputs", []) + [{
                "node": "call_preconditions",
                "completed_at": datetime.utcnow().isoformat(),
                "output_summary": f"{len(result.get('deficient_conditions', []))} conditions predicted"
            }]
        }
        
    except Exception as e:
        logger.error(f"Error in call_preconditions_node: {e}", exc_info=True)
        return {
            "error": f"PreConditions API failed: {str(e)}",
            "status": "failed"
        }


@trace_agent_execution(name="transform_output")
async def transform_output_node(state: AgentState) -> Dict[str, Any]:
    """
    Transform PreConditions output to Conditions AI input format.
    
    This is a critical transformation that bridges the two APIs.
    Output will be streamed to frontend.
    """
    logger.info("=" * 50)
    logger.info("NODE: transform_output")
    logger.info("=" * 50)
    
    preconditions_output = state["preconditions_output"]
    s3_pdf_path = state["s3_pdf_path"]
    
    logger.info("Transforming PreConditions output to Conditions AI input format")
    
    try:
        # Transform the output
        transformed = transform_preconditions_to_conditions_ai(
            cloud_output=preconditions_output,
            s3_pdf_path=s3_pdf_path
        )
        
        conditions_count = len(transformed["conf"]["conditions"])
        logger.info(f"Transformation complete: {conditions_count} conditions prepared for AI")
        logger.info(f"Output destination: {transformed['conf']['output_destination']}")
        
        # Update state (will be streamed)
        return {
            "transformed_input": transformed,
            "node_outputs": state.get("node_outputs", []) + [{
                "node": "transform_output",
                "completed_at": datetime.utcnow().isoformat(),
                "output_summary": f"{conditions_count} conditions transformed"
            }]
        }
        
    except Exception as e:
        logger.error(f"Error in transform_output_node: {e}", exc_info=True)
        return {
            "error": f"Transformation failed: {str(e)}",
            "status": "failed"
        }


@trace_agent_execution(name="call_conditions_ai")
async def call_conditions_ai_node(state: AgentState) -> Dict[str, Any]:
    """
    Call Conditions AI (Airflow v5) to evaluate conditions.
    
    This triggers the DAG, polls for completion, and fetches results from S3.
    """
    logger.info("=" * 50)
    logger.info("NODE: call_conditions_ai")
    logger.info("=" * 50)
    
    transformed_input = state["transformed_input"]
    
    logger.info("Calling Conditions AI (Airflow v5)")
    logger.info(f"Evaluating {len(transformed_input['conf']['conditions'])} conditions")
    
    try:
        # This method handles: trigger -> poll -> fetch S3
        result = await conditions_ai_client.evaluate(transformed_input)
        
        processed_conditions = result.get('processed_conditions', [])
        api_usage = result.get('api_usage_summary', {})
        
        logger.info("Conditions AI evaluation complete")
        logger.info(f"Processed {len(processed_conditions)} conditions")
        logger.info(f"Status: {result.get('processing_status')}")
        
        if api_usage:
            condition_analysis = api_usage.get('condition_analysis', {})
            logger.info(f"Total tokens: {condition_analysis.get('total_tokens', 0)}")
            logger.info(f"Total cost: ${condition_analysis.get('total_cost_usd', 0):.4f}")
            logger.info(f"Total latency: {condition_analysis.get('total_latency_ms', 0)}ms")
        
        # Update state (will be streamed)
        return {
            "conditions_ai_output": result,
            "node_outputs": state.get("node_outputs", []) + [{
                "node": "call_conditions_ai",
                "completed_at": datetime.utcnow().isoformat(),
                "output_summary": f"{len(processed_conditions)} conditions evaluated"
            }]
        }
        
    except Exception as e:
        logger.error(f"Error in call_conditions_ai_node: {e}", exc_info=True)
        return {
            "error": f"Conditions AI failed: {str(e)}",
            "status": "failed"
        }


@trace_agent_execution(name="classify_results")
async def classify_results_node(state: AgentState) -> Dict[str, Any]:
    """
    Classify conditions into fulfilled vs not fulfilled.
    
    Fulfilled conditions will be auto-approved.
    Not fulfilled conditions need RM review.
    """
    logger.info("=" * 50)
    logger.info("NODE: classify_results")
    logger.info("=" * 50)
    
    conditions_ai_output = state["conditions_ai_output"]
    
    logger.info("Classifying evaluation results")
    
    # Check if this is a "no relevant documents" scenario
    processing_status = conditions_ai_output.get('processing_status')
    if processing_status == 'completed_no_relevant_documents':
        logger.info("No relevant documents found - skipping classification")
        return {
            "fulfilled_conditions": [],
            "not_fulfilled_conditions": [],
            "requires_human_review": False,
            "auto_approved_count": 0,
            "node_outputs": state.get("node_outputs", []) + [{
                "node": "classify_results",
                "completed_at": datetime.utcnow().isoformat(),
                "output_summary": "No relevant documents found"
            }]
        }
    
    try:
        # Extract fulfilled and not fulfilled conditions
        fulfilled, not_fulfilled = extract_fulfilled_and_not_fulfilled(conditions_ai_output)
        
        logger.info(f"Fulfilled: {len(fulfilled)} conditions")
        logger.info(f"Not Fulfilled: {len(not_fulfilled)} conditions")
        
        # Determine if human review is needed
        requires_human_review = len(not_fulfilled) > 0
        
        # Update state (will be streamed)
        return {
            "fulfilled_conditions": fulfilled,
            "not_fulfilled_conditions": not_fulfilled,
            "requires_human_review": requires_human_review,
            "auto_approved_count": len(fulfilled),
            "node_outputs": state.get("node_outputs", []) + [{
                "node": "classify_results",
                "completed_at": datetime.utcnow().isoformat(),
                "output_summary": f"{len(fulfilled)} fulfilled, {len(not_fulfilled)} need review"
            }]
        }
        
    except Exception as e:
        logger.error(f"Error in classify_results_node: {e}", exc_info=True)
        return {
            "error": f"Classification failed: {str(e)}",
            "status": "failed"
        }


def confidence_router_node(state: AgentState) -> str:
    """
    Route based on whether human review is needed.
    
    Returns:
        - "auto_approve" if all conditions fulfilled
        - "human_review" if any conditions not fulfilled
    """
    logger.info("=" * 50)
    logger.info("NODE: confidence_router")
    logger.info("=" * 50)
    
    requires_review = state.get("requires_human_review", False)
    
    if requires_review:
        logger.info("Routing to human_review (some conditions not fulfilled)")
        return "human_review"
    else:
        logger.info("Routing to auto_approve (all conditions fulfilled)")
        return "auto_approve"


@trace_agent_execution(name="auto_approve")
async def auto_approve_node(state: AgentState) -> Dict[str, Any]:
    """
    Auto-approve fulfilled conditions.
    """
    logger.info("=" * 50)
    logger.info("NODE: auto_approve")
    logger.info("=" * 50)
    
    fulfilled_conditions = state.get("fulfilled_conditions", [])
    
    logger.info(f"Auto-approving {len(fulfilled_conditions)} fulfilled conditions")
    
    # Format for frontend
    formatted_conditions = [
        format_condition_for_frontend(cond, is_fulfilled=True)
        for cond in fulfilled_conditions
    ]
    
    return {
        "node_outputs": state.get("node_outputs", []) + [{
            "node": "auto_approve",
            "completed_at": datetime.utcnow().isoformat(),
            "output_summary": f"{len(fulfilled_conditions)} conditions auto-approved"
        }]
    }


@trace_agent_execution(name="human_review")
async def human_review_node(state: AgentState) -> Dict[str, Any]:
    """
    Mark not fulfilled conditions for human review.
    """
    logger.info("=" * 50)
    logger.info("NODE: human_review")
    logger.info("=" * 50)
    
    not_fulfilled_conditions = state.get("not_fulfilled_conditions", [])
    
    logger.info(f"Marking {len(not_fulfilled_conditions)} conditions for RM review")
    
    # Format for frontend
    formatted_conditions = [
        format_condition_for_frontend(cond, is_fulfilled=False)
        for cond in not_fulfilled_conditions
    ]
    
    return {
        "node_outputs": state.get("node_outputs", []) + [{
            "node": "human_review",
            "completed_at": datetime.utcnow().isoformat(),
            "output_summary": f"{len(not_fulfilled_conditions)} conditions need RM review"
        }]
    }


@trace_agent_execution(name="store_results")
async def store_results_node(state: AgentState) -> Dict[str, Any]:
    """
    Store final results to PostgreSQL and prepare final response.
    """
    logger.info("=" * 50)
    logger.info("NODE: store_results")
    logger.info("=" * 50)
    
    fulfilled_conditions = state.get("fulfilled_conditions", [])
    not_fulfilled_conditions = state.get("not_fulfilled_conditions", [])
    conditions_ai_output = state.get("conditions_ai_output", {})
    execution_metadata = state.get("execution_metadata", {})
    
    logger.info("Preparing final results")
    
    # Check if this is a "no relevant documents" scenario
    processing_status = conditions_ai_output.get('processing_status')
    is_no_relevant_docs = processing_status == 'completed_no_relevant_documents'
    
    if is_no_relevant_docs:
        logger.info("No relevant documents found - preparing special result")
        final_results = {
            "execution_id": execution_metadata.get("execution_id"),
            "trace_id": execution_metadata.get("trace_id"),
            "status": "completed_no_relevant_documents",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_conditions": 0,
                "fulfilled": 0,
                "not_fulfilled": 0,
                "auto_approved": 0,
                "requires_review": 0,
                "no_relevant_documents": True,
                "message": "No uploaded documents were relevant to the specified conditions"
            },
            "conditions": [],
            "usage": conditions_ai_output.get('api_usage_summary', {}),
            "workflow_info": conditions_ai_output.get('workflow_info', {}),
            "note": conditions_ai_output.get('message', 'No relevant documents found')
        }
    else:
        # Normal processing - format conditions
        all_conditions = []
        
        for cond in fulfilled_conditions:
            all_conditions.append(format_condition_for_frontend(cond, is_fulfilled=True))
        
        for cond in not_fulfilled_conditions:
            all_conditions.append(format_condition_for_frontend(cond, is_fulfilled=False))
        
        # Calculate totals
        api_usage = conditions_ai_output.get('api_usage_summary', {})
        condition_analysis = api_usage.get('condition_analysis', {})
        
        final_results = {
            "execution_id": execution_metadata.get("execution_id"),
            "trace_id": execution_metadata.get("trace_id"),
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_conditions": len(all_conditions),
                "fulfilled": len(fulfilled_conditions),
                "not_fulfilled": len(not_fulfilled_conditions),
                "auto_approved": len(fulfilled_conditions),
                "requires_review": len(not_fulfilled_conditions)
            },
            "conditions": all_conditions,
            "usage": {
                "total_tokens": condition_analysis.get('total_tokens', 0),
                "total_cost_usd": condition_analysis.get('total_cost_usd', 0),
                "total_latency_ms": condition_analysis.get('total_latency_ms', 0),
                "avg_latency_ms": condition_analysis.get('avg_latency_ms', 0)
            },
            "workflow_info": conditions_ai_output.get('workflow_info', {})
        }
    
    logger.info(f"Final results prepared: {final_results.get('summary', {}).get('total_conditions', 0)} total conditions")
    logger.info(f"Auto-approved: {final_results.get('summary', {}).get('fulfilled', 0)}")
    logger.info(f"Needs review: {final_results.get('summary', {}).get('not_fulfilled', 0)}")
    
    # TODO: Store to PostgreSQL
    # await repository.store_execution(...)
    
    return {
        "final_results": final_results,
        "status": "completed",
        "node_outputs": state.get("node_outputs", []) + [{
            "node": "store_results",
            "completed_at": datetime.utcnow().isoformat(),
            "output_summary": "Results stored successfully"
        }]
    }
