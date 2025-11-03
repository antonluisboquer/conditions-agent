"""State schema for Conditions Agent LangGraph."""
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime


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


class NodeOutput(TypedDict, total=False):
    """Track completion of each node for streaming."""
    node: str
    completed_at: str
    output_summary: Optional[str]


class AgentState(TypedDict, total=False):
    """
    State for Conditions Agent LangGraph with streaming support.
    
    This state flows through the graph nodes and accumulates
    data as the agent progresses. Each node updates relevant
    fields which can be streamed to the frontend.
    """
    # ========== Input (from frontend) ==========
    preconditions_input: Dict[str, Any]  # Includes borrower_info, classification, extracted_entities
    s3_pdf_path: str  # Path to uploaded PDF in S3
    
    # ========== Node Outputs (streamed after each node) ==========
    preconditions_output: Optional[Dict[str, Any]]  # Output from PreConditions API
    transformed_input: Optional[Dict[str, Any]]  # Transformed input for Conditions AI
    conditions_ai_output: Optional[Dict[str, Any]]  # Complete output from Conditions AI (S3)
    
    # ========== Classification Results ==========
    fulfilled_conditions: List[Dict[str, Any]]  # Conditions that were fulfilled
    not_fulfilled_conditions: List[Dict[str, Any]]  # Conditions needing RM review
    
    # ========== Final Results ==========
    final_results: Optional[Dict[str, Any]]  # Consolidated results for frontend
    
    # ========== Execution Tracking ==========
    execution_metadata: ExecutionMetadata
    node_outputs: List[NodeOutput]  # Track each node completion for streaming
    
    # ========== Decision Flags ==========
    requires_human_review: bool
    auto_approved_count: int
    
    # ========== Error Handling ==========
    error: Optional[str]
    status: str  # 'running', 'completed', 'failed', 'needs_review'
