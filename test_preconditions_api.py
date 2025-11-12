"""
Test script to verify PreConditions API connectivity and functionality.

This script tests the PreConditions LangGraph Cloud deployment to ensure:
- Authentication is working
- API is accessible
- Input format is correct
- Response format is as expected
"""
import asyncio
import json
from datetime import datetime
from services.preconditions import preconditions_client
from utils.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


async def test_preconditions_connectivity():
    """Quick test to verify PreConditions API is accessible."""
    
    print("=" * 80)
    print("PRECONDITIONS API CONNECTIVITY TEST")
    print("=" * 80)
    
    print("\n📋 Configuration:")
    print(f"   Deployment URL: {settings.preconditions_deployment_url}")
    print(f"   Assistant ID: {settings.preconditions_assistant_id}")
    print(f"   API Key: {'*' * 20}{settings.preconditions_api_key[-10:] if settings.preconditions_api_key else 'NOT SET'}")
    
    # Minimal test input
    test_input = {
        "loan_program": "Flex Supreme",
        "classification": "1120 Corporate Tax Return",
        "borrower_info": {
            "first_name": "Test",
            "last_name": "User"
        }
    }
    
    print("\n📤 Test Input:")
    print(json.dumps(test_input, indent=2))
    
    try:
        print("\n🚀 Calling PreConditions API...")
        start_time = datetime.utcnow()
        
        result = await preconditions_client.predict_conditions(test_input)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        print(f"✅ SUCCESS! (took {elapsed:.2f}s)")
        print("\n📊 Response Summary:")
        print(f"   Status: Connected")
        print(f"   Response Type: {type(result)}")
        print(f"   Has 'deficient_conditions': {'deficient_conditions' in result}")
        print(f"   Has 'compartments': {'compartments' in result}")
        
        deficient = result.get('deficient_conditions', [])
        compartments = result.get('compartments', [])
        
        print(f"\n   Deficient Conditions: {len(deficient)}")
        print(f"   Compartments: {len(compartments)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        logger.error(f"Connectivity test failed: {e}", exc_info=True)
        return False


async def test_preconditions_full():
    """Full test with complete input and detailed response analysis."""
    
    print("=" * 80)
    print("PRECONDITIONS API FULL TEST")
    print("=" * 80)
    
    # Complete test input with all fields
    test_input = {
        "loan_program": "Flex Supreme",
        "classification": "1120 Corporate Tax Return",
        "borrower_info": {
            "borrower_type": "Self-Employed",
            "business_name": "Test Corporation",
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "middle_name": "A.",
            "phone_number": "(555) 123-4567",
            "ssn": "123-45-6789"
        },
        "extracted_entities": {
            "business_name": "Test Corporation",
            "ein": "12-3456789",
            "gross_receipts": "1,250,000",
            "net_income": "185,000",
            "tax_year": "2023",
            "total_assets": "750,000",
            "total_liabilities": "420,000"
        }
    }
    
    print("\n📤 Full Test Input:")
    print(json.dumps(test_input, indent=2))
    
    try:
        print("\n🚀 Step 1: Calling PreConditions API...")
        start_time = datetime.utcnow()
        
        result = await preconditions_client.predict_conditions(test_input)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        print(f"✅ API call successful! (took {elapsed:.2f}s)")
        
        print("\n📊 Step 2: Analyzing Response...")
        
        # Parse response
        deficient_conditions = result.get('deficient_conditions', [])
        compartments = result.get('compartments', [])
        execution_metadata = result.get('execution_metadata', {})
        
        print(f"\n📋 RESULTS:")
        print(f"   Total Deficient Conditions: {len(deficient_conditions)}")
        print(f"   Total Compartments: {len(compartments)}")
        
        # Show compartments
        if compartments:
            print(f"\n   📁 Compartments:")
            for i, comp in enumerate(compartments, 1):
                print(f"      {i}. {comp}")
        else:
            print(f"\n   ⚠️  No compartments returned")
        
        # Show deficient conditions
        if deficient_conditions:
            print(f"\n   ⚠️  Deficient Conditions:")
            for i, cond in enumerate(deficient_conditions, 1):
                print(f"\n      {i}. {cond.get('condition_name', 'Unknown')}")
                print(f"         ID: {cond.get('condition_id', 'N/A')}")
                print(f"         Compartment: {cond.get('compartment', 'N/A')}")
                if 'actionable_instruction' in cond:
                    print(f"         Instruction: {cond['actionable_instruction'][:80]}...")
                if 'priority' in cond:
                    print(f"         Priority: {cond['priority']}")
        else:
            print(f"\n   ✅ No deficient conditions (all requirements met)")
        
        # Show execution metadata
        if execution_metadata:
            print(f"\n   📈 Execution Metadata:")
            if 'total_tokens' in execution_metadata:
                print(f"      Tokens: {execution_metadata['total_tokens']}")
            if 'cost_usd' in execution_metadata:
                print(f"      Cost: ${execution_metadata['cost_usd']:.4f}")
            if 'latency_ms' in execution_metadata:
                print(f"      Latency: {execution_metadata['latency_ms']}ms")
            if 'model_used' in execution_metadata:
                print(f"      Model: {execution_metadata['model_used']}")
        
        # Save full response
        output_file = f"test_preconditions_output_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Full response saved to: {output_file}")
        
        print("\n" + "=" * 80)
        print("✅ FULL TEST PASSED")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ FULL TEST FAILED: {str(e)}")
        print("=" * 80)
        logger.error(f"Full test failed: {e}", exc_info=True)
        raise


async def test_preconditions_various_inputs():
    """Test with various loan programs and document types."""
    
    print("=" * 80)
    print("PRECONDITIONS API - MULTIPLE INPUT SCENARIOS")
    print("=" * 80)
    
    test_scenarios = [
        {
            "name": "1120 Corporate Tax Return",
            "input": {
                "loan_program": "Flex Supreme",
                "classification": "1120 Corporate Tax Return",
                "borrower_info": {"first_name": "Test", "last_name": "Corp"}
            }
        },
        {
            "name": "Bank Statements",
            "input": {
                "loan_program": "Flex Supreme",
                "classification": "Bank Statements",
                "borrower_info": {"first_name": "Test", "last_name": "User"}
            }
        },
        {
            "name": "W-2 Documents",
            "input": {
                "loan_program": "Flex Supreme",
                "classification": "W-2",
                "borrower_info": {"first_name": "Test", "last_name": "Employee"}
            }
        }
    ]
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'─' * 80}")
        print(f"Scenario {i}/{len(test_scenarios)}: {scenario['name']}")
        print(f"{'─' * 80}")
        
        try:
            result = await preconditions_client.predict_conditions(scenario['input'])
            
            deficient = result.get('deficient_conditions', [])
            compartments = result.get('compartments', [])
            
            print(f"✅ Success")
            print(f"   Conditions: {len(deficient)}")
            print(f"   Compartments: {len(compartments)}")
            
            results.append({
                "scenario": scenario['name'],
                "success": True,
                "conditions_count": len(deficient),
                "compartments_count": len(compartments)
            })
            
        except Exception as e:
            print(f"❌ Failed: {str(e)}")
            results.append({
                "scenario": scenario['name'],
                "success": False,
                "error": str(e)
            })
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['scenario']}")
        if result['success']:
            print(f"   Conditions: {result['conditions_count']}, Compartments: {result['compartments_count']}")
    
    success_count = sum(1 for r in results if r['success'])
    print(f"\nTotal: {success_count}/{len(results)} scenarios passed")


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 80)
    print("PreConditions API Test Script")
    print("=" * 80)
    print("\nOptions:")
    print("  1. Quick connectivity test (5 seconds)")
    print("  2. Full test with detailed analysis (10 seconds)")
    print("  3. Multiple scenarios test (30 seconds)")
    print()
    
    choice = input("Select test [1/2/3] (default: 1): ").strip() or "1"
    
    if choice == "1":
        print("\n🔬 Running QUICK connectivity test...")
        success = asyncio.run(test_preconditions_connectivity())
        sys.exit(0 if success else 1)
    elif choice == "2":
        print("\n🔬 Running FULL test...")
        asyncio.run(test_preconditions_full())
    elif choice == "3":
        print("\n🔬 Running MULTIPLE SCENARIOS test...")
        asyncio.run(test_preconditions_various_inputs())
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

