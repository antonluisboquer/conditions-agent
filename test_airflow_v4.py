"""
Test script for Airflow check_condition_v4 endpoint.

This script triggers the v4 DAG with Extended Thinking and polls for completion.
"""
import asyncio
import httpx
from datetime import datetime
import json
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Configuration
AIRFLOW_BASE_URL = "https://uat-airflow-llm.cybersoftbpo.ai"
AIRFLOW_USERNAME = os.getenv("AIRFLOW_USERNAME")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD") 

# Test data - simple example with 1 condition
TEST_PAYLOAD = {
    "conf": {
        "conditions": [
            {
                "condition": {
                    "id": 1,
                    "name": "Property: Title Company Documents",
                    "data": {
                        "Title": "Property: Title Company Documents",
                        "Category": "Property",
                        "Description": "Wiring instructions from Title Company"
                    }
                }
            }
        ],
        "s3_pdf_paths": [
            {
                "bucket": "quick-quote-demo",
                "key": "mock/Wiring Instructions - demo.pdf"
            }
        ],
        "output_destination": f"quick-quote-demo/test/conditions_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    }
}


async def trigger_dag(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Trigger the check_condition_v4 DAG."""
    print("=" * 80)
    print("🚀 TRIGGERING DAG")
    print("=" * 80)
    
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/check_condition_v4/dagRuns"
    
    print(f"\nEndpoint: {url}")
    print(f"Payload: {json.dumps(TEST_PAYLOAD, indent=2)}")
    
    response = await client.post(
        url,
        auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
        json=TEST_PAYLOAD,
        timeout=30.0
    )
    
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ ERROR: {response.text}")
        response.raise_for_status()
    
    data = response.json()
    print(f"✅ DAG Triggered Successfully!")
    print(f"DAG Run ID: {data['dag_run_id']}")
    print(f"State: {data.get('state', 'N/A')}")
    
    return data


async def check_dag_status(client: httpx.AsyncClient, dag_run_id: str) -> Dict[str, Any]:
    """Check the status of a DAG run."""
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/check_condition_v4/dagRuns/{dag_run_id}"
    
    response = await client.get(
        url,
        auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
        timeout=30.0
    )
    
    if response.status_code != 200:
        print(f"❌ ERROR checking status: {response.text}")
        response.raise_for_status()
    
    return response.json()


async def poll_until_complete(client: httpx.AsyncClient, dag_run_id: str, max_wait_seconds: int = 600):
    """Poll DAG status until completion or timeout."""
    print("\n" + "=" * 80)
    print("⏳ POLLING FOR COMPLETION")
    print("=" * 80)
    
    start_time = datetime.now()
    poll_interval = 10  # seconds
    elapsed = 0
    
    while elapsed < max_wait_seconds:
        status_data = await check_dag_status(client, dag_run_id)
        state = status_data.get('state')
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print(f"\n[{elapsed:.0f}s] State: {state}")
        
        if state == 'success':
            print("\n" + "=" * 80)
            print("✅ DAG COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print(f"Start Date: {status_data.get('start_date')}")
            print(f"End Date: {status_data.get('end_date')}")
            print(f"Duration: {status_data.get('duration')} seconds")
            return status_data
        
        elif state == 'failed':
            print("\n" + "=" * 80)
            print("❌ DAG FAILED")
            print("=" * 80)
            print(f"Error: {status_data}")
            return status_data
        
        elif state in ['running', 'queued']:
            print(f"   Still {state}... waiting {poll_interval}s")
            await asyncio.sleep(poll_interval)
        
        else:
            print(f"   Unknown state: {state}")
            await asyncio.sleep(poll_interval)
    
    print("\n" + "=" * 80)
    print("⏰ TIMEOUT - DAG did not complete in time")
    print("=" * 80)
    return None


async def get_task_instances(client: httpx.AsyncClient, dag_run_id: str):
    """Get all task instances for a DAG run."""
    print("\n" + "=" * 80)
    print("📋 TASK INSTANCES")
    print("=" * 80)
    
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags/check_condition_v4/dagRuns/{dag_run_id}/taskInstances"
    
    response = await client.get(
        url,
        auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
        timeout=30.0
    )
    
    if response.status_code != 200:
        print(f"❌ ERROR: {response.text}")
        return None
    
    data = response.json()
    task_instances = data.get('task_instances', [])
    
    print(f"\nFound {len(task_instances)} tasks:\n")
    
    for task in task_instances:
        task_id = task.get('task_id')
        state = task.get('state')
        duration = task.get('duration', 0)
        
        status_emoji = {
            'success': '✅',
            'failed': '❌',
            'running': '⏳',
            'queued': '⏸️'
        }.get(state, '❓')
        
        print(f"{status_emoji} {task_id:40s} | {state:10s} | {duration:.2f}s")
    
    return task_instances


async def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("AIRFLOW CHECK_CONDITION_V4 TEST")
    print("=" * 80)
    print(f"\nBase URL: {AIRFLOW_BASE_URL}")
    print(f"Username: {AIRFLOW_USERNAME}")
    print(f"Testing with: 1 condition, 1 document")
    
    # Validate credentials
    if AIRFLOW_USERNAME == "your_username_here" or AIRFLOW_PASSWORD == "your_password_here":
        print("\n" + "=" * 80)
        print("⚠️  WARNING: Please update AIRFLOW_USERNAME and AIRFLOW_PASSWORD in the script!")
        print("=" * 80)
        return
    
    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Trigger DAG
            trigger_result = await trigger_dag(client)
            dag_run_id = trigger_result['dag_run_id']
            
            # Step 2: Poll until complete
            final_status = await poll_until_complete(client, dag_run_id, max_wait_seconds=600)
            
            if final_status and final_status.get('state') == 'success':
                # Step 3: Get task instances
                await get_task_instances(client, dag_run_id)
                
                print("\n" + "=" * 80)
                print("📄 RESULTS")
                print("=" * 80)
                print(f"\nOutput saved to S3:")
                print(f"  {TEST_PAYLOAD['conf']['output_destination']}")
                print(f"\nTo view results, download from S3 or check Airflow UI:")
                print(f"  {AIRFLOW_BASE_URL}")
                print(f"\nDAG Run ID: {dag_run_id}")
            
            print("\n" + "=" * 80)
            print("✅ TEST COMPLETE")
            print("=" * 80)
            
        except httpx.HTTPStatusError as e:
            print("\n" + "=" * 80)
            print("❌ HTTP ERROR")
            print("=" * 80)
            print(f"Status: {e.response.status_code}")
            print(f"Response: {e.response.text}")
            
            if e.response.status_code == 401:
                print("\n⚠️  Authentication failed. Please check your username and password.")
            elif e.response.status_code == 404:
                print("\n⚠️  DAG not found. Please verify the endpoint URL.")
        
        except Exception as e:
            print("\n" + "=" * 80)
            print("❌ ERROR")
            print("=" * 80)
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("\n🧪 Starting Airflow v4 Test...")
    asyncio.run(main())

