"""
Test script for various ReWOO agent scenarios.

Tests different user instructions to verify the planner chooses the right tools:
1. Deficiency prediction only → call_preconditions_api
2. Document validation only → call_conditions_ai_api  
3. S3 access check only → retrieve_s3_document
4. Full evaluation → call_preconditions_api + call_conditions_ai_api

Test scenarios are loaded from JSON files in the tests/ directory:
- scenario_1_deficiencies_only.json
- scenario_2_validation_only.json
- scenario_3_s3_access.json
- scenario_4_full_evaluation.json
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
from datetime import datetime
from agent.rewoo_graph import run_rewoo_agent_streaming
from utils.logging_config import get_logger

logger = get_logger(__name__)


# Load test scenarios from JSON files
def load_scenario(filename: str) -> dict:
    """Load a scenario from a JSON file."""
    scenario_file = os.path.join(os.path.dirname(__file__), filename)
    with open(scenario_file, 'r') as f:
        return json.load(f)


# Load scenarios from JSON files
SCENARIO_1_DEFICIENCIES_ONLY = load_scenario('scenario_1_deficiencies_only.json')
SCENARIO_2_VALIDATION_ONLY = load_scenario('scenario_2_validation_only.json')
SCENARIO_3_S3_ACCESS = load_scenario('scenario_3_s3_access.json')
SCENARIO_4_FULL_EVALUATION = load_scenario('scenario_4_full_evaluation.json')


async def test_scenario(scenario_name: str, input_data: dict):
    """Test a single scenario and display results."""
    
    print("=" * 80)
    print(f"SCENARIO: {scenario_name}")
    print("=" * 80)
    
    print(f"\n📋 User Instructions:")
    print(f'   "{input_data["instructions"]}"')
    
    print(f"\n📊 Input Summary:")
    print(f"   Metadata fields: {list(input_data['metadata'].keys())}")
    print(f"   Documents: {len(input_data['s3_pdf_paths'])}")
    if input_data['s3_pdf_paths']:
        for doc in input_data['s3_pdf_paths']:
            print(f"      - {doc.split('/')[-1]}")
    
    print(f"\n🚀 Running agent...")
    start_time = datetime.utcnow()
    
    try:
        plan_shown = False
        tools_used = []
        
        async for event in run_rewoo_agent_streaming(**input_data):
            stage = event.get('stage')
            
            # Show plan
            if stage == 'planning_complete' and not plan_shown:
                state = event.get('state', {})
                plan = state.get('plan', {})
                
                print(f"\n📝 PLAN:")
                print(f"   Summary: {plan.get('summary', 'N/A')}")
                print(f"   Steps: {len(plan.get('steps', []))}")
                
                for i, step in enumerate(plan.get('steps', []), 1):
                    tool = step.get('tool')
                    tools_used.append(tool)
                    print(f"      {i}. {tool}")
                    print(f"         {step.get('description', 'N/A')}")
                
                plan_shown = True
            
            # Show completion
            elif stage == 'completed':
                state = event.get('state', {})
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                
                print(f"\n✅ COMPLETED in {elapsed:.2f}s")
                print(f"\n🔧 Tools Used: {', '.join(tools_used)}")
                
                # Show key results
                final_results = state.get('final_results', {})
                if final_results:
                    print(f"\n📊 Results:")
                    fulfilled = final_results.get('fulfilled_count', 0)
                    not_fulfilled = final_results.get('not_fulfilled_count', 0)
                    print(f"   Fulfilled: {fulfilled}")
                    print(f"   Not Fulfilled: {not_fulfilled}")
        
        print("\n" + "=" * 80)
        return True
        
    except Exception as e:
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        print(f"\n❌ FAILED after {elapsed:.2f}s")
        print(f"   Error: {str(e)}")
        logger.error(f"Scenario failed: {e}", exc_info=True)
        print("\n" + "=" * 80)
        return False


async def run_all_scenarios():
    """Run all test scenarios."""
    
    print("\n" + "=" * 80)
    print("ReWOO AGENT SCENARIO TESTS")
    print("=" * 80)
    print("\nTesting if the agent chooses the right tools based on user instructions.\n")
    
    scenarios = [
        ("1. Deficiency Prediction Only", SCENARIO_1_DEFICIENCIES_ONLY),
        ("2. Document Validation Only", SCENARIO_2_VALIDATION_ONLY),
        ("3. S3 Access Check", SCENARIO_3_S3_ACCESS),
        ("4. Full Evaluation", SCENARIO_4_FULL_EVALUATION),
    ]
    
    results = []
    
    for name, input_data in scenarios:
        try:
            success = await test_scenario(name, input_data)
            results.append((name, success))
            await asyncio.sleep(1)  # Brief pause between scenarios
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Scenario setup failed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} {name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nTotal: {passed}/{total} scenarios passed")


async def run_single_scenario(scenario_num: int):
    """Run a specific scenario by number."""
    
    scenarios = {
        1: ("Deficiency Prediction Only", SCENARIO_1_DEFICIENCIES_ONLY),
        2: ("Document Validation Only", SCENARIO_2_VALIDATION_ONLY),
        3: ("S3 Access Check", SCENARIO_3_S3_ACCESS),
        4: ("Full Evaluation", SCENARIO_4_FULL_EVALUATION),
    }
    
    if scenario_num not in scenarios:
        print(f"❌ Invalid scenario number: {scenario_num}")
        print(f"   Valid options: 1-{len(scenarios)}")
        return
    
    name, input_data = scenarios[scenario_num]
    await test_scenario(name, input_data)


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("ReWOO Agent Scenario Tests")
    print("=" * 80)
    print("\nTest Options:")
    print("  1. Deficiency prediction only (PreConditions API)")
    print("  2. Document validation only (Conditions AI)")
    print("  3. S3 access check (retrieve_s3_document)")
    print("  4. Full evaluation (PreConditions + Conditions AI)")
    print("  all - Run all scenarios")
    print()
    
    choice = input("Select test [1-4/all] (default: all): ").strip().lower() or "all"
    
    if choice == "all":
        print("\n🔬 Running ALL scenarios...")
        asyncio.run(run_all_scenarios())
    elif choice.isdigit() and 1 <= int(choice) <= 4:
        print(f"\n🔬 Running scenario {choice}...")
        asyncio.run(run_single_scenario(int(choice)))
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

