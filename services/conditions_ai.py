"""Conditions AI API client."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import httpx

from config.settings import settings
from services.predicted_conditions import Condition
from services.rack_and_stack import DocumentData


class ConditionEvaluationResult(BaseModel):
    """Single condition evaluation result."""
    condition_id: str
    result: str  # 'satisfied', 'unsatisfied', 'uncertain'
    confidence: float
    reasoning: str
    model_used: str  # e.g., 'gpt-5-mini', 'claude-sonnet-4.5'
    citations: Optional[List[str]] = None  # Document IDs referenced
    details: Optional[Dict[str, Any]] = None


class EvaluationResponse(BaseModel):
    """Complete evaluation response from Conditions AI."""
    evaluations: List[ConditionEvaluationResult]
    total_tokens: int
    cost_usd: float
    latency_ms: int
    model_breakdown: Dict[str, int]  # Count of evaluations per model


class ConditionsAIClient:
    """Client for Conditions AI API."""
    
    def __init__(self, api_url: str = None):
        """Initialize client."""
        self.api_url = api_url or settings.conditions_ai_api_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def evaluate(
        self,
        conditions: List[Condition],
        documents: List[DocumentData]
    ) -> EvaluationResponse:
        """
        Evaluate if documents satisfy conditions.
        
        Args:
            conditions: List of predicted conditions to evaluate
            documents: List of uploaded documents with rack & stack data
            
        Returns:
            Evaluation results for each condition
        """
        # MOCK IMPLEMENTATION - Replace with actual API call
        # Real implementation would be:
        # response = await self.client.post(
        #     f"{self.api_url}/evaluate",
        #     json={
        #         "conditions": [c.model_dump() for c in conditions],
        #         "documents": [d.model_dump() for d in documents]
        #     }
        # )
        # response.raise_for_status()
        # return EvaluationResponse(**response.json())
        
        return self._mock_evaluate(conditions, documents)
    
    def _mock_evaluate(
        self,
        conditions: List[Condition],
        documents: List[DocumentData]
    ) -> EvaluationResponse:
        """Mock implementation returning sample evaluation results."""
        
        # Simple mock logic based on document types
        doc_types = {doc.document_type for doc in documents}
        
        evaluations = []
        
        for condition in conditions:
            # Mock evaluation logic
            if condition.condition_id == "cond_001":  # Proof of income
                if "W-2" in doc_types:
                    evaluations.append(ConditionEvaluationResult(
                        condition_id=condition.condition_id,
                        result="satisfied",
                        confidence=0.95,
                        reasoning="W-2 form for 2024 provided showing annual wages of $85,000",
                        model_used="gpt-5-mini",
                        citations=["doc_001"],
                        details={"wages": 85000.00, "year": 2024}
                    ))
                else:
                    evaluations.append(ConditionEvaluationResult(
                        condition_id=condition.condition_id,
                        result="unsatisfied",
                        confidence=0.88,
                        reasoning="No W-2 or proof of income documents found",
                        model_used="gpt-5-mini",
                        citations=[]
                    ))
            
            elif condition.condition_id == "cond_002":  # Employment verification
                if "Employment Verification Letter" in doc_types:
                    evaluations.append(ConditionEvaluationResult(
                        condition_id=condition.condition_id,
                        result="satisfied",
                        confidence=0.92,
                        reasoning="Employment verification letter confirms active employment at ABC Corporation since 2020",
                        model_used="claude-sonnet-4.5",
                        citations=["doc_003"]
                    ))
                else:
                    evaluations.append(ConditionEvaluationResult(
                        condition_id=condition.condition_id,
                        result="unsatisfied",
                        confidence=0.85,
                        reasoning="No employment verification letter provided",
                        model_used="gpt-5-mini",
                        citations=[]
                    ))
            
            elif condition.condition_id == "cond_003":  # Bank statements
                if "Bank Statement" in doc_types:
                    evaluations.append(ConditionEvaluationResult(
                        condition_id=condition.condition_id,
                        result="satisfied",
                        confidence=0.89,
                        reasoning="Bank statement for October 2024 provided with ending balance of $15,000",
                        model_used="gpt-5-mini",
                        citations=["doc_002"]
                    ))
                else:
                    evaluations.append(ConditionEvaluationResult(
                        condition_id=condition.condition_id,
                        result="uncertain",
                        confidence=0.45,
                        reasoning="Partial bank information found but complete 3-month statements not confirmed",
                        model_used="gpt-5",
                        citations=[]
                    ))
            
            elif condition.condition_id == "cond_004":  # Credit inquiry explanation
                evaluations.append(ConditionEvaluationResult(
                    condition_id=condition.condition_id,
                    result="uncertain",
                    confidence=0.60,
                    reasoning="No clear letter of explanation found. Manual review recommended.",
                    model_used="claude-sonnet-4.5",
                    citations=[]
                ))
            
            else:
                # Default uncertain result for unknown conditions
                evaluations.append(ConditionEvaluationResult(
                    condition_id=condition.condition_id,
                    result="uncertain",
                    confidence=0.50,
                    reasoning="Unable to evaluate condition with provided documents",
                    model_used="claude-haiku-4.5",
                    citations=[]
                ))
        
        # Mock model breakdown
        model_breakdown = {}
        for eval_result in evaluations:
            model_breakdown[eval_result.model_used] = model_breakdown.get(eval_result.model_used, 0) + 1
        
        return EvaluationResponse(
            evaluations=evaluations,
            total_tokens=2500,  # Mock token count
            cost_usd=0.15,      # Mock cost
            latency_ms=1850,    # Mock latency
            model_breakdown=model_breakdown
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global client instance
conditions_ai_client = ConditionsAIClient()

