"""Predicted Conditions API client."""
from typing import List, Dict, Any
from pydantic import BaseModel
import httpx

from config.settings import settings


class Condition(BaseModel):
    """Predicted condition model."""
    condition_id: str
    condition_text: str
    condition_type: str  # e.g., 'document_required', 'verification_needed'
    priority: str  # 'high', 'medium', 'low'
    expected_documents: List[str]


class PredictedConditionsClient:
    """Client for Predicted Conditions API."""
    
    def __init__(self, api_url: str = None):
        """Initialize client."""
        self.api_url = api_url or settings.predicted_conditions_api_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_conditions(self, loan_guid: str) -> List[Condition]:
        """
        Get predicted conditions for a loan.
        
        Args:
            loan_guid: Unique loan identifier
            
        Returns:
            List of predicted conditions
        """
        # MOCK IMPLEMENTATION - Replace with actual API call
        # Real implementation would be:
        # response = await self.client.get(
        #     f"{self.api_url}/loans/{loan_guid}/conditions"
        # )
        # response.raise_for_status()
        # return [Condition(**c) for c in response.json()["conditions"]]
        
        return self._mock_get_conditions(loan_guid)
    
    def _mock_get_conditions(self, loan_guid: str) -> List[Condition]:
        """Mock implementation returning sample conditions."""
        return [
            Condition(
                condition_id="cond_001",
                condition_text="Provide proof of income for the last 2 years",
                condition_type="document_required",
                priority="high",
                expected_documents=["W-2", "1099", "Pay Stubs"]
            ),
            Condition(
                condition_id="cond_002",
                condition_text="Verification of employment required",
                condition_type="verification_needed",
                priority="high",
                expected_documents=["Employment Verification Letter"]
            ),
            Condition(
                condition_id="cond_003",
                condition_text="Bank statements for the last 3 months",
                condition_type="document_required",
                priority="medium",
                expected_documents=["Bank Statement"]
            ),
            Condition(
                condition_id="cond_004",
                condition_text="Explanation of credit inquiries",
                condition_type="explanation_required",
                priority="low",
                expected_documents=["Letter of Explanation"]
            )
        ]
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global client instance
predicted_conditions_client = PredictedConditionsClient()

