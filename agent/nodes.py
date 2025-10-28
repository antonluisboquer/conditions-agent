"""Node implementations for Conditions Agent LangGraph."""
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4

from agent.state import AgentState
from services.predicted_conditions import predicted_conditions_client
from services.rack_and_stack import rack_and_stack_client
from services.conditions_ai import conditions_ai_client
from services.airflow_client import airflow_client
from utils.guardrails import guardrails_validator
from utils.logging_config import get_logger
from utils.tracing import trace_agent_execution
from database.repository import db_repository
from config.settings import settings

logger = get_logger(__name__)


@trace_agent_execution(name="load_conditions")
async def load_conditions_node(state: AgentState) -> Dict[str, Any]:
    """
    Load predicted conditions for the loan.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with loaded conditions
    """
    logger.info(f"Loading predicted conditions for loan {state['loan_guid']}")
    
    try:
        conditions = await predicted_conditions_client.get_conditions(state["loan_guid"])
        logger.info(f"Loaded {len(conditions)} predicted conditions")
        
        return {
            "conditions": conditions,
            "status": "loading_documents"
        }
    except Exception as e:
        logger.error(f"Error loading conditions: {e}", exc_info=True)
        return {
            "error": f"Failed to load conditions: {str(e)}",
            "status": "failed"
        }


@trace_agent_execution(name="load_documents")
async def load_documents_node(state: AgentState) -> Dict[str, Any]:
    """
    Load rack and stack results for uploaded documents.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with loaded documents
    """
    logger.info(f"Loading documents: {state['condition_doc_ids']}")
    
    try:
        documents = await rack_and_stack_client.get_document_data(state["condition_doc_ids"])
        logger.info(f"Loaded {len(documents)} documents")
        
        return {
            "uploaded_docs": documents,
            "status": "evaluating"
        }
    except Exception as e:
        logger.error(f"Error loading documents: {e}", exc_info=True)
        return {
            "error": f"Failed to load documents: {str(e)}",
            "status": "failed"
        }


@trace_agent_execution(name="call_conditions_ai")
async def call_conditions_ai_node(state: AgentState) -> Dict[str, Any]:
    """
    Call external Conditions AI API to evaluate conditions.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with evaluation results
    """
    logger.info(f"Calling Conditions AI for {len(state['conditions'])} conditions")
    
    try:
        # Call Conditions AI API
        response = await conditions_ai_client.evaluate(
            conditions=state["conditions"],
            documents=state["uploaded_docs"]
        )
        
        logger.info(
            f"Conditions AI completed: {len(response.evaluations)} evaluations, "
            f"{response.total_tokens} tokens, ${response.cost_usd:.4f}"
        )
        
        # Extract confidence scores
        confidence_scores = {
            eval_result.condition_id: eval_result.confidence
            for eval_result in response.evaluations
        }
        
        # Update execution metadata
        metadata = state.get("execution_metadata", {})
        metadata.update({
            "total_tokens": response.total_tokens,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
            "model_breakdown": response.model_breakdown
        })
        
        return {
            "conditions_ai_response": response,
            "evaluations": response.evaluations,
            "confidence_scores": confidence_scores,
            "execution_metadata": metadata,
            "status": "applying_guardrails"
        }
    except Exception as e:
        logger.error(f"Error calling Conditions AI: {e}", exc_info=True)
        return {
            "error": f"Failed to evaluate conditions: {str(e)}",
            "status": "failed"
        }


@trace_agent_execution(name="apply_guardrails")
async def apply_guardrails_node(state: AgentState) -> Dict[str, Any]:
    """
    Apply guardrails and validation to evaluation results.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with validation results
    """
    logger.info("Applying guardrails and validation")
    
    try:
        # Validate evaluations
        validated_evaluations, requires_review, issues = guardrails_validator.validate_evaluations(
            evaluations=state["evaluations"],
            documents=state["uploaded_docs"],
            cost_usd=state["execution_metadata"].get("cost_usd", 0.0)
        )
        
        logger.info(
            f"Guardrails validation complete: requires_review={requires_review}, "
            f"issues={len(issues)}"
        )
        
        return {
            "evaluations": validated_evaluations,
            "requires_human_review": requires_review,
            "validation_issues": issues,
            "status": "routing"
        }
    except Exception as e:
        logger.error(f"Error applying guardrails: {e}", exc_info=True)
        return {
            "error": f"Failed to apply guardrails: {str(e)}",
            "status": "failed"
        }


def confidence_router_node(state: AgentState) -> str:
    """
    Route based on confidence and validation results.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node name: 'store_results' or 'human_review'
    """
    if state.get("requires_human_review", False):
        logger.info("Routing to human review")
        return "human_review"
    else:
        logger.info("Routing to store results (auto-approved)")
        return "store_results"


@trace_agent_execution(name="human_review")
async def human_review_node(state: AgentState) -> Dict[str, Any]:
    """
    Flag evaluations for human review.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with review flag
    """
    logger.info("Marking for human review")
    
    # Log which conditions need review
    low_confidence = [
        eval_result.condition_id
        for eval_result in state["evaluations"]
        if eval_result.confidence < guardrails_validator.confidence_threshold
    ]
    
    logger.info(f"Conditions requiring review: {low_confidence}")
    
    return {
        "status": "needs_review"
    }


@trace_agent_execution(name="store_results")
async def store_results_node(state: AgentState) -> Dict[str, Any]:
    """
    Store results in PostgreSQL with full audit trail.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with storage confirmation
    """
    logger.info("Storing results in PostgreSQL")
    
    try:
        # Get execution ID from metadata
        execution_id = state["execution_metadata"].get("execution_id")
        
        if not execution_id:
            logger.error("No execution_id in metadata")
            return {
                "error": "Missing execution_id",
                "status": "failed"
            }
        
        # Store evaluations
        evaluation_records = []
        for eval_result in state["evaluations"]:
            evaluation_records.append({
                "condition_id": eval_result.condition_id,
                "condition_text": next(
                    (c.condition_text for c in state["conditions"] if c.condition_id == eval_result.condition_id),
                    ""
                ),
                "result": eval_result.result,
                "confidence": float(eval_result.confidence),
                "model_used": eval_result.model_used,
                "reasoning": eval_result.reasoning,
                "citations": eval_result.citations
            })
        
        db_repository.create_evaluations(execution_id, evaluation_records)
        
        # Update execution status
        metadata = state["execution_metadata"]
        db_repository.update_execution_status(
            execution_id=execution_id,
            status="completed",
            total_tokens=metadata.get("total_tokens"),
            cost_usd=metadata.get("cost_usd"),
            latency_ms=metadata.get("latency_ms")
        )
        
        # Update loan state
        result_counts = {"satisfied": 0, "unsatisfied": 0, "uncertain": 0}
        for eval_result in state["evaluations"]:
            result_counts[eval_result.result] = result_counts.get(eval_result.result, 0) + 1
        
        final_status = "needs_review" if state.get("requires_human_review") else "approved"
        
        db_repository.upsert_loan_state(
            loan_guid=state["loan_guid"],
            current_status=final_status,
            last_execution_id=execution_id,
            conditions_count=len(state["evaluations"]),
            satisfied_count=result_counts["satisfied"],
            unsatisfied_count=result_counts["unsatisfied"],
            uncertain_count=result_counts["uncertain"]
        )
        
        logger.info(f"Successfully stored results for execution {execution_id}")
        
        return {
            "status": "triggering_airflow"
        }
    except Exception as e:
        logger.error(f"Error storing results: {e}", exc_info=True)
        return {
            "error": f"Failed to store results: {str(e)}",
            "status": "failed"
        }


@trace_agent_execution(name="trigger_airflow")
async def trigger_airflow_node(state: AgentState) -> Dict[str, Any]:
    """
    Trigger Airflow DAG for downstream processing.
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state with Airflow DAG run information
    """
    logger.info("Triggering Airflow DAG for downstream processing")
    
    try:
        execution_id = state["execution_metadata"].get("execution_id")
        loan_guid = state["loan_guid"]
        
        # Format conditions for Airflow DAG
        conditions_list = []
        for condition in state.get("conditions", []):
            condition_obj = {
                "condition": {
                    "id": getattr(condition, "condition_id", condition.get("condition_id")),
                    "name": getattr(condition, "condition_text", condition.get("condition_text", "")),
                    "data": {
                        "Title": getattr(condition, "condition_text", condition.get("condition_text", "")),
                        "Category": getattr(condition, "category", condition.get("category", "General")),
                        "Description": getattr(condition, "description", condition.get("description", ""))
                    }
                }
            }
            conditions_list.append(condition_obj)
        
        # Format S3 PDF paths from uploaded documents
        s3_pdf_paths = []
        for doc in state.get("uploaded_docs", []):
            # Extract S3 path from document metadata
            s3_path = {
                "bucket": getattr(doc, "s3_bucket", doc.get("s3_bucket", settings.s3_input_bucket)),
                "key": getattr(doc, "s3_key", doc.get("s3_key", f"docs/{loan_guid}/{doc.get('doc_id', 'unknown')}.pdf"))
            }
            s3_pdf_paths.append(s3_path)
        
        # Validate we have data to send
        if not conditions_list:
            logger.warning(f"No conditions found for loan {loan_guid}")
            return {
                "status": "completed",
                "airflow_error": "No conditions to process"
            }
        
        if not s3_pdf_paths:
            logger.warning(f"No documents found for loan {loan_guid}")
            # Continue anyway - DAG might have default behavior for missing docs
        
        # Define output destination in rm-conditions bucket
        # Note: This is just a path string - Airflow DAG handles the actual S3 write
        output_destination = f"{settings.s3_output_bucket}/{loan_guid}/conditions_{execution_id}.json"
        
        # Build the configuration for Airflow DAG
        dag_config = {
            "conditions": conditions_list,
            "s3_pdf_paths": s3_pdf_paths,
            "output_destination": output_destination
        }
        
        logger.info(f"Sending to Airflow: {len(conditions_list)} conditions, {len(s3_pdf_paths)} documents")
        
        if not s3_pdf_paths:
            logger.warning("No documents provided - DAG will run with empty document list")
        
        # Log the full payload for debugging
        import json
        logger.info("=" * 60)
        logger.info("AIRFLOW DAG PAYLOAD:")
        logger.info(json.dumps(dag_config, indent=2))
        logger.info("=" * 60)
        
        # Trigger the Airflow DAG with formatted configuration
        dag_run_result = await airflow_client.trigger_dag_with_config(
            dag_config=dag_config,
            execution_id=execution_id
        )
        
        logger.info("=" * 60)
        logger.info("✅ AIRFLOW DAG TRIGGERED SUCCESSFULLY!")
        logger.info(f"DAG Run ID: {dag_run_result.get('dag_run_id')}")
        logger.info(f"State: {dag_run_result.get('state')}")
        logger.info(f"Output Location: s3://{output_destination}")
        logger.info("=" * 60)
        
        # Store DAG run info in execution metadata
        metadata = state.get("execution_metadata", {})
        metadata["airflow_dag_run_id"] = dag_run_result.get("dag_run_id")
        metadata["airflow_dag_state"] = dag_run_result.get("state")
        metadata["airflow_execution_date"] = dag_run_result.get("execution_date")
        metadata["output_destination"] = output_destination
        
        return {
            "execution_metadata": metadata,
            "airflow_dag_run": dag_run_result,
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"Error triggering Airflow DAG: {e}", exc_info=True)
        # Don't fail the entire workflow if Airflow trigger fails
        # Just log the error and mark as completed
        logger.warning("Continuing workflow despite Airflow trigger failure")
        return {
            "status": "completed",
            "airflow_error": str(e)
        }

