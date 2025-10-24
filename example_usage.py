"""
Example usage of the Conditions Agent.

This script demonstrates how to use the Conditions Agent API
to evaluate loan conditions.
"""
import asyncio
import httpx
from pprint import pprint


async def main():
    """Run example evaluation."""
    
    # API endpoint
    api_url = "http://localhost:8000"
    
    # Check health
    print("=" * 80)
    print("1. Checking API health...")
    print("=" * 80)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{api_url}/health")
        print(f"Status: {response.status_code}")
        pprint(response.json())
    
    # Evaluate conditions
    print("\n" + "=" * 80)
    print("2. Evaluating conditions for loan...")
    print("=" * 80)
    
    request_data = {
        "loan_guid": "loan_example_001",
        "condition_doc_ids": ["doc_001", "doc_002", "doc_003"]
    }
    
    print(f"\nRequest:")
    pprint(request_data)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{api_url}/api/v1/evaluate-conditions",
            json=request_data
        )
        
        print(f"\nStatus: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n--- EVALUATION RESULTS ---")
            print(f"Execution ID: {result['execution_id']}")
            print(f"Status: {result['status']}")
            print(f"Requires Human Review: {result['requires_human_review']}")
            print(f"Trace URL: {result['trace_url']}")
            
            print(f"\n--- METADATA ---")
            metadata = result['metadata']
            print(f"Total Tokens: {metadata['total_tokens']}")
            print(f"Cost: ${metadata['cost_usd']:.4f}")
            print(f"Latency: {metadata['latency_ms']}ms")
            print(f"Model Breakdown: {metadata['model_breakdown']}")
            
            print(f"\n--- CONDITION EVALUATIONS ({len(result['evaluations'])}) ---")
            for i, evaluation in enumerate(result['evaluations'], 1):
                print(f"\n{i}. Condition: {evaluation['condition_text']}")
                print(f"   ID: {evaluation['condition_id']}")
                print(f"   Result: {evaluation['result'].upper()}")
                print(f"   Confidence: {evaluation['confidence']:.2%}")
                print(f"   Model: {evaluation['model_used']}")
                print(f"   Reasoning: {evaluation['reasoning']}")
                if evaluation.get('citations'):
                    print(f"   Citations: {', '.join(evaluation['citations'])}")
            
            if result['validation_issues']:
                print(f"\n--- VALIDATION ISSUES ---")
                for issue in result['validation_issues']:
                    print(f"  • {issue}")
        else:
            print(f"Error: {response.text}")
    
    # Get execution details
    print("\n" + "=" * 80)
    print("3. Retrieving execution details...")
    print("=" * 80)
    
    if response.status_code == 200:
        execution_id = result['execution_id']
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v1/executions/{execution_id}"
            )
            print(f"Status: {response.status_code}")
            pprint(response.json())
    
    # Get loan state
    print("\n" + "=" * 80)
    print("4. Retrieving loan state...")
    print("=" * 80)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{api_url}/api/v1/loans/loan_example_001/state"
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            pprint(response.json())
        else:
            print("Note: Loan state not found (expected on first run)")
    
    # Submit feedback example
    print("\n" + "=" * 80)
    print("5. Example: Submitting RM feedback...")
    print("=" * 80)
    
    if response.status_code == 200 and result['evaluations']:
        # Get first evaluation ID
        # Note: In a real scenario, you'd get this from the condition_evaluations table
        print("Note: To submit feedback, you would use an evaluation_id from the database")
        print("Example feedback payload:")
        feedback_example = {
            "evaluation_id": "00000000-0000-0000-0000-000000000000",
            "rm_user_id": "rm_john_doe",
            "feedback_type": "approve",
            "notes": "Looks good, documents satisfy the condition"
        }
        pprint(feedback_example)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("CONDITIONS AGENT - EXAMPLE USAGE")
    print("=" * 80)
    print("\nMake sure the API is running:")
    print("  docker-compose up")
    print("  OR")
    print("  uvicorn api.main:app --reload")
    print("\n" + "=" * 80 + "\n")
    
    asyncio.run(main())

