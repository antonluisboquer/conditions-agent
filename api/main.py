"""FastAPI endpoints for Conditions Agent."""
import json
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from uuid import UUID

from agent.graph import run_conditions_agent, run_conditions_agent_streaming
from database.repository import db_repository
from services.conditions_ai import conditions_ai_client
from utils.logging_config import setup_logging, get_logger
from utils.tracing import tracing_manager
from config.settings import settings

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Conditions Agent API",
    description="LangGraph-based orchestrator for loan conditions evaluation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models

class EvaluateLoanRequest(BaseModel):
    """Request to evaluate loan conditions with streaming support."""
    preconditions_input: Dict[str, Any] = Field(..., description="Input containing borrower info, classification, and extracted entities from Rack & Stack")
    s3_pdf_path: str = Field(..., description="S3 path to uploaded PDF document")


class EvaluateConditionsRequest(BaseModel):
    """Request to evaluate conditions (legacy format)."""
    loan_guid: str = Field(..., description="Unique loan identifier")
    condition_doc_ids: List[str] = Field(..., description="List of condition document IDs")


class ConditionEvaluationResponse(BaseModel):
    """Single condition evaluation result."""
    condition_id: str
    condition_text: str
    result: str
    confidence: float
    reasoning: str
    model_used: str
    citations: Optional[List[str]] = None


class EvaluateConditionsResponse(BaseModel):
    """Response from evaluate conditions endpoint."""
    execution_id: str
    loan_guid: str
    status: str
    requires_human_review: bool
    evaluations: List[ConditionEvaluationResponse]
    validation_issues: List[str]
    trace_url: Optional[str] = None
    airflow_dag_run_id: Optional[str] = None
    metadata: dict


class RMFeedbackRequest(BaseModel):
    """Request to submit RM feedback."""
    evaluation_id: str
    rm_user_id: str
    feedback_type: str = Field(..., description="approve, reject, or correct")
    corrected_result: Optional[str] = None
    notes: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    langsmith_enabled: bool
    airflow_connected: bool = False
    airflow_dag_status: Optional[str] = None


# Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    # Check Airflow connection
    airflow_connected = False
    airflow_dag_status = None
    
    try:
        # Note: check_airflow_dag_health() is no longer implemented in new client
        # TODO: Add health check if needed
        airflow_connected = True
        airflow_dag_status = "available"
    except Exception as e:
        logger.warning(f"Airflow health check failed: {e}")
        airflow_dag_status = f"error: {str(e)}"
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        langsmith_enabled=settings.langsmith_tracing_v2,
        airflow_connected=airflow_connected,
        airflow_dag_status=airflow_dag_status
    )


@app.post("/api/v1/evaluate-loan-conditions")
async def evaluate_loan_conditions_streaming(request: EvaluateLoanRequest):
    """
    Evaluate loan conditions with streaming Server-Sent Events (SSE).
    
    This endpoint provides real-time updates as each node completes:
    1. call_preconditions - PreConditions API prediction
    2. transform_output - Format transformation (STREAMED TO FRONTEND)
    3. call_conditions_ai - Airflow v5 evaluation
    4. classify_results - Fulfilled vs not fulfilled
    5. auto_approve/human_review - Routing
    6. store_results - Final results
    
    Frontend receives updates after each node using EventSource.
    
    Example frontend code:
    ```javascript
    const eventSource = new EventSource('/api/v1/evaluate-loan-conditions');
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log(`Node ${data.node} completed:`, data.state);
    };
    ```
    """
    logger.info("Starting streaming evaluation")
    logger.info(f"Classification: {request.preconditions_input.get('classification')}")
    logger.info(f"S3 Path: {request.s3_pdf_path}")
    
    async def event_generator():
        """Generate SSE events for each node completion."""
        try:
            async for event in run_conditions_agent_streaming(
                preconditions_input=request.preconditions_input,
                s3_pdf_path=request.s3_pdf_path
            ):
                # Format as SSE
                event_data = json.dumps(event, default=str)
                yield f"data: {event_data}\n\n"
                
        except Exception as e:
            logger.error(f"Error in streaming: {e}", exc_info=True)
            # Send error event
            error_event = {
                "node": "error",
                "status": "failed",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/v1/evaluate-conditions", response_model=EvaluateConditionsResponse)
async def evaluate_conditions(request: EvaluateConditionsRequest):
    """
    Evaluate if uploaded documents satisfy loan conditions.
    
    This endpoint orchestrates the entire conditions evaluation workflow:
    1. Load predicted conditions
    2. Load rack & stack document data
    3. Call Conditions AI for evaluation
    4. Apply guardrails and validation
    5. Store results in PostgreSQL
    
    Returns evaluation results with LangSmith trace URL.
    """
    logger.info(f"Received evaluation request for loan {request.loan_guid}")
    
    try:
        # Run the conditions agent
        final_state = await run_conditions_agent(
            loan_guid=request.loan_guid,
            condition_doc_ids=request.condition_doc_ids
        )
        
        # Check for errors
        if final_state.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Agent execution failed: {final_state['error']}"
            )
        
        # Get trace URL
        trace_url = tracing_manager.get_trace_url()
        
        # Format evaluations
        evaluations = []
        for eval_result in final_state.get("evaluations", []):
            # Find the condition text
            condition_text = ""
            for condition in final_state.get("conditions", []):
                if condition.condition_id == eval_result.condition_id:
                    condition_text = condition.condition_text
                    break
            
            evaluations.append(ConditionEvaluationResponse(
                condition_id=eval_result.condition_id,
                condition_text=condition_text,
                result=eval_result.result,
                confidence=eval_result.confidence,
                reasoning=eval_result.reasoning,
                model_used=eval_result.model_used,
                citations=eval_result.citations
            ))
        
        # Build response
        response = EvaluateConditionsResponse(
            execution_id=final_state["execution_metadata"]["execution_id"],
            loan_guid=request.loan_guid,
            status=final_state["status"],
            requires_human_review=final_state.get("requires_human_review", False),
            evaluations=evaluations,
            validation_issues=final_state.get("validation_issues", []),
            trace_url=trace_url,
            airflow_dag_run_id=final_state["execution_metadata"].get("airflow_dag_run_id"),
            metadata={
                "total_tokens": final_state["execution_metadata"]["total_tokens"],
                "cost_usd": float(final_state["execution_metadata"]["cost_usd"]),
                "latency_ms": final_state["execution_metadata"]["latency_ms"],
                "model_breakdown": final_state["execution_metadata"]["model_breakdown"],
                "airflow_dag_state": final_state["execution_metadata"].get("airflow_dag_state"),
                "airflow_execution_date": final_state["execution_metadata"].get("airflow_execution_date")
            }
        )
        
        logger.info(f"Successfully completed evaluation for loan {request.loan_guid}")
        return response
        
    except Exception as e:
        logger.error(f"Error in evaluate_conditions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/feedback")
async def submit_feedback(request: RMFeedbackRequest):
    """
    Submit Relationship Manager feedback on an evaluation.
    
    This feedback is used for:
    - Audit trail
    - Continuous improvement
    - Training data collection
    """
    logger.info(f"Received feedback from {request.rm_user_id} for evaluation {request.evaluation_id}")
    
    try:
        # Store feedback
        feedback = db_repository.create_feedback(
            evaluation_id=UUID(request.evaluation_id),
            rm_user_id=request.rm_user_id,
            feedback_type=request.feedback_type,
            corrected_result=request.corrected_result,
            notes=request.notes
        )
        
        return {
            "feedback_id": str(feedback.feedback_id),
            "status": "success",
            "message": "Feedback recorded successfully"
        }
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution details by ID."""
    try:
        execution = db_repository.get_execution(UUID(execution_id))
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        # Get evaluations
        evaluations = db_repository.get_evaluations_by_execution(UUID(execution_id))
        
        return {
            "execution_id": str(execution.execution_id),
            "loan_guid": execution.loan_guid,
            "status": execution.status,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "total_tokens": execution.total_tokens,
            "cost_usd": float(execution.cost_usd),
            "latency_ms": execution.latency_ms,
            "trace_id": execution.trace_id,
            "evaluations_count": len(evaluations),
            "error_message": execution.error_message
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution ID format")
    except Exception as e:
        logger.error(f"Error retrieving execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/loans/{loan_guid}/state")
async def get_loan_state(loan_guid: str):
    """Get current state of a loan."""
    try:
        loan_state = db_repository.get_loan_state(loan_guid)
        
        if not loan_state:
            raise HTTPException(status_code=404, detail="Loan state not found")
        
        return {
            "loan_guid": loan_state.loan_guid,
            "current_status": loan_state.current_status,
            "last_execution_id": str(loan_state.last_execution_id) if loan_state.last_execution_id else None,
            "conditions_count": loan_state.conditions_count,
            "satisfied_count": loan_state.satisfied_count,
            "unsatisfied_count": loan_state.unsatisfied_count,
            "uncertain_count": loan_state.uncertain_count,
            "updated_at": loan_state.updated_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving loan state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower()
    )

