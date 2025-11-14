"""Conditions AI API client for Airflow v3 with S3 result fetching."""
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
    """Client for Conditions AI (Airflow v3 check_condition_v3 DAG)."""
    
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
        # Priority: Role ARN > Temporary Credentials > Static Keys > Default Credential Chain
        if settings.aws_role_arn:
            # Use STS to assume the specified role
            logger.info(f"Assuming IAM role: {settings.aws_role_arn}")
            sts_client = boto3.client('sts', region_name=settings.aws_region)
            assumed_role = sts_client.assume_role(
                RoleArn=settings.aws_role_arn,
                RoleSessionName='conditions-agent-session'
            )
            credentials = assumed_role['Credentials']
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=settings.aws_region
            )
            logger.info("Successfully assumed role and created S3 client")
        elif settings.aws_access_key_id and settings.aws_secret_access_key:
            # Use provided credentials (with or without session token)
            if settings.aws_session_token:
                logger.info("Creating S3 client with temporary credentials (session token)")
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    aws_session_token=settings.aws_session_token,
                    region_name=settings.aws_region
                )
            else:
                logger.info("Creating S3 client with static credentials")
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region
                )
        else:
            # Use default credential chain (IAM role, env vars, ~/.aws/credentials)
            logger.info("Creating S3 client with default credential chain")
            self.s3_client = boto3.client('s3', region_name=settings.aws_region)
    
    async def evaluate(
        self,
        conditions_ai_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete workflow to evaluate conditions via Airflow v3.
        
        This method:
        1. Triggers the check_condition_v3 DAG
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
        logger.info("Starting Conditions AI evaluation via Airflow v3")
        
        # Step 1: Trigger DAG
        num_conditions = len(conditions_ai_input.get("conf", {}).get("conditions", []))
        num_documents = len(conditions_ai_input.get("conf", {}).get("s3_pdf_paths", []))
        logger.info(f"Triggering DAG with {num_conditions} conditions and {num_documents} documents")
        
        dag_run = await self.trigger_dag(conditions_ai_input)
        dag_run_id = dag_run["dag_run_id"]
        logger.info(f"DAG triggered successfully: {dag_run_id}")
        
        # Step 2: Poll for completion
        await self.poll_until_complete(dag_run_id, max_wait_seconds=600)
        
        # Step 3: Fetch results from S3
        output_destination = conditions_ai_input["conf"]["output_destination"]
        logger.info(f"DAG completed, fetching results from: {output_destination}")
        
        try:
            s3_results = await self.fetch_s3_results(output_destination)
            logger.info("Conditions AI evaluation complete")
            return s3_results
        except FileNotFoundError as e:
            # DAG completed but no output file - this happens when no documents are relevant
            logger.warning(f"DAG completed successfully but no output file found in S3: {e}")
            logger.info("This likely means no documents were relevant to the conditions being evaluated")
            
            # Return a structured result indicating no relevant documents
            return {
                "workflow_info": {
                    "dag_id": "check_condition_v3",
                    "dag_run_id": dag_run_id,
                    "processing_status": "completed_no_relevant_documents",
                    "output_destination": output_destination,
                    "s3_output_written": False,
                    "reason": "No documents were relevant to the specified conditions"
                },
                "processed_conditions": [],
                "api_usage_summary": {
                    "relevance_check": {"total_calls": 0, "note": "All conditions marked as unrelated"},
                    "condition_analysis": {"total_calls": 0, "note": "Skipped - no relevant documents"},
                    "overall": {"total_api_calls": 0, "total_cost_usd": 0.0}
                },
                "processing_status": "completed_no_relevant_documents",
                "message": "DAG completed successfully but found no documents relevant to the specified conditions. This may occur when uploaded documents do not match the condition requirements.",
                "workflow_version": "3.0"
            }
    
    async def trigger_dag(
        self,
        conditions_ai_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger the check_condition_v3 DAG.
        
        Args:
            conditions_ai_input: Input configuration for Airflow
        
        Returns:
            DAG run information including dag_run_id
        """
        logger.info("Triggering Airflow check_condition_v3 DAG")
        logger.debug(f"DAG input: {json.dumps(conditions_ai_input, indent=2)}")
        
        url = f"{self.api_url}/api/v1/dags/check_condition_v3/dagRuns"
        
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
        url = f"{self.api_url}/api/v1/dags/check_condition_v3/dagRuns/{dag_run_id}"
        
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
    
    async def fetch_s3_results(
        self, 
        s3_path: str,
        max_wait_seconds: int = 180,  # 3 minutes for heavy document processing
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Fetch evaluation results from S3, with polling if file not immediately available.
        
        After DAG completion, there may be a delay before the S3 file is written.
        This method polls for the file to appear.
        
        Args:
            s3_path: S3 path in format "bucket/key/to/file.json"
            max_wait_seconds: Maximum time to wait for file (default 60s)
            poll_interval: Seconds between polls (default 5s)
        
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
        
        # Poll for S3 file availability
        start_time = datetime.utcnow()
        attempt = 0
        
        while True:
            attempt += 1
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            try:
                # Try to fetch from S3 (synchronous boto3 call)
                response = await asyncio.to_thread(
                    self.s3_client.get_object,
                    Bucket=bucket,
                    Key=key
                )
                
                # Read and parse JSON
                content = response['Body'].read().decode('utf-8')
                results = json.loads(content)
                
                logger.info(f"Successfully fetched results from s3://{bucket}/{key} after {elapsed:.1f}s (attempt {attempt})")
                logger.info(f"Processing status: {results.get('processing_status')}")
                
                return results
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'NoSuchKey':
                    # File not found - check if we should retry
                    if elapsed >= max_wait_seconds:
                        logger.error(f"S3 object not found after {elapsed:.1f}s: s3://{bucket}/{key}")
                        raise FileNotFoundError(
                            f"Results not found in S3 after {max_wait_seconds}s: {s3_path}. "
                            f"DAG may have completed but failed to write output file."
                        )
                    
                    # Wait and retry
                    logger.debug(f"[{elapsed:.0f}s] S3 file not ready (attempt {attempt}), waiting {poll_interval}s...")
                    await asyncio.sleep(poll_interval)
                else:
                    # Other S3 error - don't retry
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
