"""PreConditions API client for LangGraph Cloud."""
from typing import Dict, Any
from langgraph_sdk import get_client

from config.settings import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)


class PreConditionsClient:
    """Client for PreConditions LangGraph Cloud API."""
    
    def __init__(
        self, 
        deployment_url: str = None,
        api_key: str = None,
        assistant_id: str = None
    ):
        """
        Initialize PreConditions client.
        
        Args:
            deployment_url: LangGraph Cloud deployment URL
            api_key: LangSmith API key
            assistant_id: Assistant/graph ID
        """
        self.deployment_url = deployment_url or settings.preconditions_deployment_url
        self.api_key = api_key or settings.preconditions_api_key
        self.assistant_id = assistant_id or settings.preconditions_assistant_id
    
    async def predict_conditions(self, preconditions_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call PreConditions API to predict required conditions.
        
        This API analyzes borrower information, loan program, and document classification
        to predict which conditions will be required by the underwriter.
        
        Args:
            preconditions_input: Input containing:
                - borrower_info: Borrower details
                - classification: Document classification
                - extracted_entities: Entities from Rack & Stack
                - loan_program: Loan program type
        
        Returns:
            PreConditions output containing:
                - compartments: List of condition categories
                - deficient_conditions: Predicted conditions that may be deficient
                - top_n: Top priority conditions
                - execution_metadata: Tokens, cost, latency
        """
        logger.info(f"Calling PreConditions API for classification: {preconditions_input.get('classification')}")
        
        try:
            # Initialize LangGraph Cloud client
            client = get_client(url=self.deployment_url, api_key=self.api_key)
            
            # Create a thread for this execution
            thread = await client.threads.create()
            thread_id = thread["thread_id"]
            logger.info(f"Created thread: {thread_id}")
            
            # Run the assistant with the input
            run = await client.runs.create(
                thread_id,
                assistant_id=self.assistant_id,
                input=preconditions_input
            )
            run_id = run["run_id"]
            logger.info(f"Started run: {run_id}")
            
            # Wait for completion
            run = await client.runs.join(thread_id, run_id)
            logger.info(f"Run completed with status: {run.get('status')}")
            
            # Get the final state
            thread_state = await client.threads.get_state(thread_id)
            output = thread_state["values"]
            
            logger.info(
                f"PreConditions completed: {len(output.get('deficient_conditions', []))} deficient conditions, "
                f"{len(output.get('compartments', []))} compartments"
            )
            
            return output
            
        except Exception as e:
            logger.error(f"Error calling PreConditions API: {e}", exc_info=True)
            raise Exception(f"PreConditions API call failed: {str(e)}")
    
    async def close(self):
        """Close any open connections."""
        # LangGraph SDK client doesn't require explicit closing
        pass


# Global client instance
preconditions_client = PreConditionsClient()

