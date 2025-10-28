"""Conditions AI API client."""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import httpx

from config.settings import settings
from services.predicted_conditions import Condition
from services.rack_and_stack import DocumentData
from utils.logging_config import get_logger

logger = get_logger(__name__)


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
    
    async def check_airflow_dag_health(self) -> bool:
        """
        Check if the Airflow DAG is available and healthy.
        
        Returns:
            True if DAG is accessible, False otherwise
        """
        url = f"{settings.airflow_base_url}/api/v1/dags/{settings.airflow_dag_id}"
        
        try:
            response = await self.client.get(
                url,
                auth=(settings.airflow_username, settings.airflow_password)
            )
            response.raise_for_status()
            dag_info = response.json()
            is_paused = dag_info.get("is_paused", True)
            
            if is_paused:
                logger.warning(f"Airflow DAG {settings.airflow_dag_id} is paused")
                return False
            
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"Error checking Airflow DAG health: {e}")
            return False
    
    async def trigger_airflow_dag(
        self,
        dag_config: Dict[str, Any],
        execution_id: str
    ) -> Dict[str, Any]:
        """
        Trigger the Airflow DAG with custom configuration format.
        
        This method sends the configuration to the Airflow DAG after evaluation:
        {
            "conf": {
                "conditions": [...],
                "s3_pdf_paths": [...],
                "output_destination": "..."
            }
        }
        
        Args:
            dag_config: The configuration dict containing conditions, s3_pdf_paths, and output_destination
            execution_id: Execution ID for tracking
            
        Returns:
            Dict containing dag_run_id, state, and execution_date
            
        Raises:
            httpx.HTTPError: If the API request fails
        """
        logger.info(f"Triggering Airflow DAG {settings.airflow_dag_id} with custom configuration")
        
        # API endpoint for triggering DAG
        url = f"{settings.airflow_base_url}/api/v1/dags/{settings.airflow_dag_id}/dagRuns"
        
        # Payload for triggering the DAG
        payload = {
            "conf": dag_config,
            "dag_run_id": f"conditions_agent_{execution_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "note": f"Triggered by Conditions Agent - execution {execution_id}"
        }
        
        logger.debug(f"Airflow DAG payload: {payload}")
        
        try:
            response = await self.client.post(
                url,
                json=payload,
                auth=(settings.airflow_username, settings.airflow_password),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(
                f"Successfully triggered DAG run: {result.get('dag_run_id')} "
                f"with state: {result.get('state')}"
            )
            logger.info(
                f"Output destination: s3://{dag_config.get('output_destination')}"
            )
            
            return {
                "dag_run_id": result.get("dag_run_id"),
                "state": result.get("state"),
                "execution_date": result.get("execution_date"),
                "logical_date": result.get("logical_date"),
                "conf": result.get("conf")
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error triggering Airflow DAG: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error triggering Airflow DAG: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error triggering Airflow DAG: {e}", exc_info=True)
            raise
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global client instance
conditions_ai_client = ConditionsAIClient()

