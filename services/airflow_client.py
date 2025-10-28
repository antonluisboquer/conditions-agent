"""Airflow DAG trigger client."""
import httpx
from typing import Optional, Dict, Any
from datetime import datetime
from utils.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


class AirflowClient:
    """Client for triggering and monitoring Airflow DAGs."""
    
    def __init__(self):
        self.base_url = settings.airflow_base_url
        self.username = settings.airflow_username
        self.password = settings.airflow_password
        self.dag_id = settings.airflow_dag_id
        self.timeout = 30.0
    
    async def trigger_dag(
        self,
        loan_guid: str,
        condition_doc_ids: list[str],
        execution_id: str,
        additional_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Trigger the check_condition_v3 Airflow DAG.
        
        Args:
            loan_guid: Unique loan identifier
            condition_doc_ids: List of condition document IDs
            execution_id: Execution ID from the agent
            additional_config: Additional configuration to pass to the DAG
            
        Returns:
            Dict containing dag_run_id, state, and execution_date
            
        Raises:
            httpx.HTTPError: If the API request fails
        """
        logger.info(f"Triggering Airflow DAG {self.dag_id} for loan {loan_guid}")
        
        # Prepare the DAG run configuration
        dag_config = {
            "loan_guid": loan_guid,
            "condition_doc_ids": condition_doc_ids,
            "execution_id": execution_id,
            "triggered_at": datetime.utcnow().isoformat(),
        }
        
        if additional_config:
            dag_config.update(additional_config)
        
        # API endpoint for triggering DAG
        url = f"{self.base_url}/api/v1/dags/{self.dag_id}/dagRuns"
        
        # Payload for triggering the DAG
        payload = {
            "conf": dag_config,
            "dag_run_id": f"conditions_agent_{execution_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "note": f"Triggered by Conditions Agent for loan {loan_guid}"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    auth=(self.username, self.password),
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    f"Successfully triggered DAG run: {result.get('dag_run_id')} "
                    f"with state: {result.get('state')}"
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
    
    async def trigger_dag_with_config(
        self,
        dag_config: Dict[str, Any],
        execution_id: str
    ) -> Dict[str, Any]:
        """
        Trigger the Airflow DAG with custom configuration format.
        
        This method sends the configuration in the specific format required by the DAG:
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
        logger.info(f"Triggering Airflow DAG {self.dag_id} with custom configuration")
        
        # API endpoint for triggering DAG
        url = f"{self.base_url}/api/v1/dags/{self.dag_id}/dagRuns"
        
        # Payload for triggering the DAG
        payload = {
            "conf": dag_config,
            "dag_run_id": f"conditions_agent_{execution_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "note": f"Triggered by Conditions Agent - execution {execution_id}"
        }
        
        logger.debug(f"Airflow DAG payload: {payload}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    auth=(self.username, self.password),
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
    
    async def get_dag_run_status(self, dag_run_id: str) -> Dict[str, Any]:
        """
        Get the status of a DAG run.
        
        Args:
            dag_run_id: The DAG run ID to check
            
        Returns:
            Dict containing state, start_date, end_date, etc.
        """
        url = f"{self.base_url}/api/v1/dags/{self.dag_id}/dagRuns/{dag_run_id}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    auth=(self.username, self.password)
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error getting DAG run status: {e}")
            raise
    
    async def check_dag_health(self) -> bool:
        """
        Check if the Airflow DAG is available and healthy.
        
        Returns:
            True if DAG is accessible, False otherwise
        """
        url = f"{self.base_url}/api/v1/dags/{self.dag_id}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    auth=(self.username, self.password)
                )
                response.raise_for_status()
                dag_info = response.json()
                is_paused = dag_info.get("is_paused", True)
                
                if is_paused:
                    logger.warning(f"Airflow DAG {self.dag_id} is paused")
                    return False
                
                return True
                
        except httpx.HTTPError as e:
            logger.error(f"Error checking Airflow DAG health: {e}")
            return False


# Global client instance
airflow_client = AirflowClient()

