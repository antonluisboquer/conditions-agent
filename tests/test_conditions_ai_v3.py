"""
Test script to verify Conditions AI v3 DAG integration.

This script tests calling the check_condition_v3 DAG directly
to ensure the integration works before running through the full agent.
"""
import sys
import os
# Add parent directory to path so we can import from services/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
from datetime import datetime
from services.conditions_ai import conditions_ai_client
from utils.logging_config import get_logger

logger = get_logger(__name__)


async def test_conditions_ai_v3():
    """Test calling Conditions AI v3 DAG directly."""
    
    print("=" * 80)
    print("TESTING CONDITIONS AI V3 INTEGRATION")
    print("=" * 80)
    
    # Prepare test input matching the format from conditions_ai_input.json
    test_input = {
        "conf": {
            "conditions": [
                {
                    "condition": {
                        "id": 2,
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
                    "bucket": "rm-conditions",
                    "key": "Encompass Docs - Preliminary Title Report dtd 9-4-25.pdf"
                }
            ],
            "output_destination": f"rm-conditions/test_v3_output_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        }
    }
    
    print("\n📤 INPUT:")
    print(json.dumps(test_input, indent=2))
    
    try:
        print("\n🚀 Step 1: Triggering DAG...")
        dag_run = await conditions_ai_client.trigger_dag(test_input)
        dag_run_id = dag_run["dag_run_id"]
        print(f"✅ DAG triggered: {dag_run_id}")
        print(f"   State: {dag_run.get('state')}")
        print(f"   Logical date: {dag_run.get('logical_date')}")
        
        print("\n⏳ Step 2: Polling for completion...")
        print("   (This may take 1-2 minutes)")
        await conditions_ai_client.poll_until_complete(dag_run_id, max_wait_seconds=300)
        print("✅ DAG completed successfully!")
        
        print("\n📥 Step 3: Fetching results from S3...")
        output_destination = test_input["conf"]["output_destination"]
        results = await conditions_ai_client.fetch_s3_results(output_destination)
        
        print("✅ Results fetched successfully!")
        print("\n📊 RESULTS SUMMARY:")
        print(f"   Processing Status: {results.get('processing_status')}")
        print(f"   Workflow Version: {results.get('workflow_version')}")
        print(f"   DAG ID: {results.get('workflow_info', {}).get('dag_id')}")
        
        # Show conditions processed
        processed_conditions = results.get('processed_conditions', [])
        print(f"   Conditions Processed: {len(processed_conditions)}")
        
        if processed_conditions:
            print("\n   Condition Results:")
            for i, cond in enumerate(processed_conditions, 1):
                print(f"     {i}. {cond.get('title')}")
                print(f"        Status: {cond.get('document_status')}")
                print(f"        Relevance: {cond.get('is_relevant')}")
                print(f"        Category: {cond.get('category')}")
        
        # Show API usage
        api_usage = results.get('api_usage_summary', {})
        if api_usage:
            overall = api_usage.get('overall', {})
            print(f"\n   API Usage:")
            print(f"     Total Calls: {overall.get('total_api_calls')}")
            print(f"     Total Tokens: {overall.get('total_tokens')}")
            print(f"     Total Cost: ${overall.get('total_cost_usd', 0):.4f}")
            print(f"     Total Latency: {overall.get('total_latency_ms')}ms")
        
        print("\n" + "=" * 80)
        print("✅ TEST PASSED: Conditions AI v3 integration is working!")
        print("=" * 80)
        
        # Save full results to file
        output_file = f"test_v3_results_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Full results saved to: {output_file}")
        
        return results
        
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {str(e)}")
        print("=" * 80)
        logger.error(f"Test failed: {e}", exc_info=True)
        raise
    
    finally:
        # Clean up
        await conditions_ai_client.close()


async def test_trigger_only():
    """Quick test to just trigger the DAG and check if it starts."""
    
    print("=" * 80)
    print("QUICK TEST: Trigger DAG Only")
    print("=" * 80)
    
    test_input = {
        "conf": {
            "conditions": [
                {
                    "condition": {
                        "id": 2,
                        "name": "Test Condition",
                        "data": {
                            "Title": "Test",
                            "Category": "Property",
                            "Description": "Test condition"
                        }
                    }
                }
            ],
            "s3_pdf_paths": [
                {
                    "bucket": "rm-conditions",
                    "key": "Encompass Docs - Preliminary Title Report dtd 9-4-25.pdf"
                }
            ],
            "output_destination": f"rm-conditions/test_trigger_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        }
    }
    
    try:
        print("\n🚀 Triggering DAG...")
        dag_run = await conditions_ai_client.trigger_dag(test_input)
        dag_run_id = dag_run["dag_run_id"]
        
        print(f"✅ DAG triggered successfully!")
        print(f"   DAG Run ID: {dag_run_id}")
        print(f"   State: {dag_run.get('state')}")
        print(f"   DAG ID: {dag_run.get('dag_id')}")
        print(f"   Execution Date: {dag_run.get('execution_date')}")
        
        # Check status once after a few seconds
        print("\n⏳ Waiting 5 seconds then checking status...")
        await asyncio.sleep(5)
        
        status = await conditions_ai_client.check_dag_status(dag_run_id)
        print(f"\n📊 Current Status:")
        print(f"   State: {status.get('state')}")
        print(f"   Start Date: {status.get('start_date')}")
        
        if status.get('state') == 'running':
            print("\n✅ SUCCESS: DAG is running! (v3 is working)")
        elif status.get('state') == 'queued':
            print("\n⚠️  DAG is still queued (may need to wait longer)")
        elif status.get('state') == 'success':
            print("\n✅ SUCCESS: DAG already completed!")
        else:
            print(f"\n⚠️  Unexpected state: {status.get('state')}")
        
        return dag_run
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        logger.error(f"Trigger test failed: {e}", exc_info=True)
        raise
    
    finally:
        await conditions_ai_client.close()


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 80)
    print("Conditions AI v3 Test Script")
    print("=" * 80)
    print("\nOptions:")
    print("  1. Full test (trigger + poll + fetch results)")
    print("  2. Quick test (trigger only)")
    print()
    
    choice = input("Select test [1/2] (default: 2): ").strip() or "2"
    
    if choice == "1":
        print("\n🔬 Running FULL test...")
        asyncio.run(test_conditions_ai_v3())
    elif choice == "2":
        print("\n🔬 Running QUICK test...")
        asyncio.run(test_trigger_only())
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

