"""Conditions AI API client for Airflow v5 with S3 result fetching."""
import asyncio
import json
from typing import Dict, Any
from datetime import datetime
import httpx
import boto3
from botocore.exceptions import ClientError

from config.settings import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)


class ConditionsAIClient:
    """Client for Conditions AI (Airflow v5 check_condition_v5 DAG)."""
    
    def __init__(
        self,
        api_url: str = None,
        username: str = None,
        password: str = None
    ):
        """Initialize client."""
        self.api_url = api_url or settings.conditions_ai_api_url
        self.username = username or settings.airflow_username
        self.password = password or settings.airflow_password
        self.http_client = httpx.AsyncClient(timeout=300.0)
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )
    
    async def evaluate(
        self,
        conditions_ai_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete workflow to evaluate conditions via Airflow v5.
        
        This method:
        1. Triggers the check_condition_v5 DAG
        2. Polls for completion
        3. Fetches results from S3
        4. Returns the complete evaluation
        
        Args:
            conditions_ai_input: Input in format:
                {
                    "conf": {
                        "conditions": [...],
                        "s3_pdf_paths": [...],
                        "output_destination": "bucket/path/to/output.json"
                    }
                }
        
        Returns:
            Complete evaluation output from S3 (conditions_s3_output.json format)
        """
        logger.info("Starting Conditions AI evaluation via Airflow v5")
        
        # Step 1: Trigger DAG
        dag_run = await self.trigger_dag(conditions_ai_input)
        dag_run_id = dag_run["dag_run_id"]
        
        # Step 2: Poll for completion
        await self.poll_until_complete(dag_run_id, max_wait_seconds=600)
        
        # Step 3: Fetch results from S3
        output_destination = conditions_ai_input["conf"]["output_destination"]
        s3_results = await self.fetch_s3_results(output_destination)
        
        logger.info("Conditions AI evaluation complete")
        return s3_results
    
    async def trigger_dag(
        self,
        conditions_ai_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger the check_condition_v5 DAG.
        
        Args:
            conditions_ai_input: Input configuration for Airflow
        
        Returns:
            DAG run information including dag_run_id
        """
        logger.info("Triggering Airflow v5 check_condition_v5 DAG")
        
        url = f"{self.api_url}/api/v1/dags/check_condition_v5/dagRuns"
        
        # Extract config
        dag_config = conditions_ai_input.get("conf", conditions_ai_input)
        
        payload = {
            "conf": dag_config
        }
        
        logger.debug(f"DAG trigger payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = await self.http_client.post(
                url,
                auth=(self.username, self.password),
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            dag_run_id = result["dag_run_id"]
            
            logger.info(f"DAG triggered successfully: {dag_run_id}")
            logger.info(f"State: {result.get('state')}")
            logger.info(f"Output destination: {dag_config['output_destination']}")
            
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error triggering DAG: {e.response.status_code}")
            logger.error(f"Response: {e.response.text}")
            raise Exception(f"Failed to trigger Airflow DAG: {e.response.text}")
        except Exception as e:
            logger.error(f"Error triggering DAG: {e}", exc_info=True)
            raise
    
    async def poll_until_complete(
        self,
        dag_run_id: str,
        max_wait_seconds: int = 600,
        poll_interval: int = 10
    ):
        """
        Poll DAG status until completion or timeout.
        
        Args:
            dag_run_id: DAG run ID to poll
            max_wait_seconds: Maximum time to wait (default 10 minutes)
            poll_interval: Seconds between polls (default 10s)
        
        Raises:
            TimeoutError: If DAG doesn't complete in time
            Exception: If DAG fails
        """
        logger.info(f"Polling DAG {dag_run_id} for completion")
        
        start_time = datetime.utcnow()
        elapsed = 0
        
        while elapsed < max_wait_seconds:
            status = await self.check_dag_status(dag_run_id)
            state = status.get('state')
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"[{elapsed:.0f}s] DAG state: {state}")
            
            if state == 'success':
                duration = status.get('duration')
                logger.info(f"DAG completed successfully in {duration}s")
                return
            
            elif state == 'failed':
                error_msg = f"DAG failed: {status}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            elif state in ['running', 'queued']:
                logger.debug(f"DAG still {state}, waiting {poll_interval}s")
                await asyncio.sleep(poll_interval)
            
            else:
                logger.warning(f"Unknown DAG state: {state}")
                await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"DAG did not complete within {max_wait_seconds}s")
    
    async def check_dag_status(self, dag_run_id: str) -> Dict[str, Any]:
        """
        Check the status of a DAG run.
        
        Args:
            dag_run_id: DAG run ID
        
        Returns:
            DAG run status information
        """
        url = f"{self.api_url}/api/v1/dags/check_condition_v5/dagRuns/{dag_run_id}"
        
        try:
            response = await self.http_client.get(
                url,
                auth=(self.username, self.password)
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Error checking DAG status: {e}")
            raise
    
    async def fetch_s3_results(self, s3_path: str) -> Dict[str, Any]:
        """
        Fetch evaluation results from S3.
        
        Args:
            s3_path: S3 path in format "bucket/key/to/file.json"
        
        Returns:
            Parsed JSON results from S3
        """
        logger.info(f"Fetching results from S3: {s3_path}")
        
        # Parse S3 path
        if s3_path.startswith('s3://'):
            s3_path = s3_path[5:]
        
        parts = s3_path.split('/', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 path format: {s3_path}")
        
        bucket, key = parts
        
        try:
            # Fetch from S3 (synchronous boto3 call)
            response = await asyncio.to_thread(
                self.s3_client.get_object,
                Bucket=bucket,
                Key=key
            )
            
            # Read and parse JSON
            content = response['Body'].read().decode('utf-8')
            results = json.loads(content)
            
            logger.info(f"Successfully fetched results from s3://{bucket}/{key}")
            logger.info(f"Processing status: {results.get('processing_status')}")
            
            return results
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.error(f"S3 object not found: s3://{bucket}/{key}")
                raise FileNotFoundError(f"Results not found in S3: {s3_path}")
            else:
                logger.error(f"S3 error: {error_code} - {e}")
                raise
        except Exception as e:
            logger.error(f"Error fetching S3 results: {e}", exc_info=True)
            raise
    
    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


# Global client instance
conditions_ai_client = ConditionsAIClient()
