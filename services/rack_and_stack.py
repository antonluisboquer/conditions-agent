"""Rack and Stack API client."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import httpx

from config.settings import settings


class DocumentData(BaseModel):
    """Document data from rack and stack processing."""
    document_id: str
    document_type: str  # e.g., 'W-2', 'Bank Statement', 'Pay Stub'
    classification_confidence: float
    extracted_entities: Dict[str, Any]
    raw_text: Optional[str] = None
    page_count: int = 1


class RackAndStackClient:
    """Client for Rack and Stack API."""
    
    def __init__(self, api_url: str = None):
        """Initialize client."""
        self.api_url = api_url or settings.rack_and_stack_api_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_document_data(self, document_ids: List[str]) -> List[DocumentData]:
        """
        Get rack and stack results for documents.
        
        Args:
            document_ids: List of document IDs to retrieve
            
        Returns:
            List of document data with classification and extraction
        """
        # MOCK IMPLEMENTATION - Replace with actual API call
        # Real implementation would be:
        # response = await self.client.post(
        #     f"{self.api_url}/documents/batch",
        #     json={"document_ids": document_ids}
        # )
        # response.raise_for_status()
        # return [DocumentData(**d) for d in response.json()["documents"]]
        
        return self._mock_get_document_data(document_ids)
    
    def _mock_get_document_data(self, document_ids: List[str]) -> List[DocumentData]:
        """Mock implementation returning sample document data."""
        mock_documents = {
            "doc_001": DocumentData(
                document_id="doc_001",
                document_type="W-2",
                classification_confidence=0.98,
                extracted_entities={
                    "borrower_name": "John Doe",
                    "employer": "ABC Corporation",
                    "year": 2024,
                    "wages": 85000.00,
                    "federal_tax_withheld": 12750.00
                },
                raw_text="W-2 Wage and Tax Statement for John Doe...",
                page_count=1
            ),
            "doc_002": DocumentData(
                document_id="doc_002",
                document_type="Bank Statement",
                classification_confidence=0.95,
                extracted_entities={
                    "account_holder": "John Doe",
                    "bank_name": "Chase Bank",
                    "account_number": "****1234",
                    "statement_period": "Oct 2024",
                    "ending_balance": 15000.00
                },
                raw_text="Chase Bank statement for account ending in 1234...",
                page_count=3
            ),
            "doc_003": DocumentData(
                document_id="doc_003",
                document_type="Employment Verification Letter",
                classification_confidence=0.92,
                extracted_entities={
                    "employee_name": "John Doe",
                    "employer": "ABC Corporation",
                    "position": "Senior Software Engineer",
                    "employment_start_date": "2020-01-15",
                    "annual_salary": 85000.00,
                    "employment_status": "Active"
                },
                raw_text="This letter verifies that John Doe is employed at ABC Corporation...",
                page_count=1
            )
        }
        
        # Return requested documents or generate mock ones
        return [
            mock_documents.get(doc_id, self._generate_mock_doc(doc_id))
            for doc_id in document_ids
        ]
    
    def _generate_mock_doc(self, document_id: str) -> DocumentData:
        """Generate a generic mock document."""
        return DocumentData(
            document_id=document_id,
            document_type="Unknown",
            classification_confidence=0.5,
            extracted_entities={"note": "Mock document"},
            raw_text=f"Mock document content for {document_id}",
            page_count=1
        )
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global client instance
rack_and_stack_client = RackAndStackClient()

