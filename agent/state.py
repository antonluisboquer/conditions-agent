"""State schema for Conditions Agent LangGraph."""
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

from services.predicted_conditions import Condition
from services.rack_and_stack import DocumentData
from services.conditions_ai import EvaluationResponse, ConditionEvaluationResult


class ExecutionMetadata(TypedDict, total=False):
    """Metadata about the execution."""
    trace_id: Optional[str]
    execution_id: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    total_tokens: int
    cost_usd: float
    latency_ms: int
    model_breakdown: Dict[str, int]


class AgentState(TypedDict, total=False):
    """
    State for Conditions Agent LangGraph.
    
    This state flows through the graph nodes and accumulates
    data as the agent progresses through the workflow.
    """
    # Input
    loan_guid: str
    condition_doc_ids: List[str]
    
    # Loaded data
    conditions: List[Condition]
    uploaded_docs: List[DocumentData]
    
    # Conditions AI response
    conditions_ai_response: Optional[EvaluationResponse]
    
    # Processed results
    evaluations: List[ConditionEvaluationResult]
    confidence_scores: Dict[str, float]  # condition_id -> confidence
    
    # Decision flags
    requires_human_review: bool
    validation_issues: List[str]
    
    # Execution metadata
    execution_metadata: ExecutionMetadata
    
    # Error tracking
    error: Optional[str]
    status: str  # 'running', 'completed', 'failed', 'needs_review'

