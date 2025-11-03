#!/usr/bin/env python3
"""
Invoke the deployed LangGraph agent on LangGraph Cloud.
"""

import json
import sys
import asyncio
import os
from pathlib import Path
from langgraph_sdk import get_client
from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# CONFIGURATION - Update these with your deployment details
# ============================================================================

DEPLOYMENT_URL = os.getenv("PRECONDITIONS_DEPLOYMENT_URL")  # From LangSmith Deployments
API_KEY = os.getenv("PRECONDITIONS_LANGSMITH_API_KEY") # From LangSmith Settings → API Keys
ASSISTANT_ID = os.getenv("PRECONDITIONS_ASSISTANT_ID")  # Your graph name

# ============================================================================
# MAIN SCRIPT
# ============================================================================

async def main():
    """Invoke the deployed LangGraph agent."""
    
    print("=" * 70)
    print("🚀 INVOKING LANGGRAPH CLOUD DEPLOYMENT")
    print("=" * 70)
    
    # Check configuration
    if "your-deployment" in DEPLOYMENT_URL or "your_api_key" in API_KEY:
        print("\n❌ ERROR: Please update the configuration at the top of this script!")
        print("\nYou need to set:")
        print("  1. DEPLOYMENT_URL - Found in LangSmith → Deployments → Your deployment")
        print("  2. API_KEY - Found in LangSmith → Settings → API Keys")
        sys.exit(1)
    
    # Load input data
    script_dir = Path(__file__).parent
    input_file = script_dir / "sample_input.json"
    
    if not input_file.exists():
        print(f"\n❌ ERROR: Input file not found: {input_file}")
        sys.exit(1)
    
    with open(input_file, "r") as f:
        input_data = json.load(f)
    
    print(f"\n📥 Loaded input from: {input_file}")
    print(f"   Classification: {input_data.get('classification', 'N/A')}")
    print(f"   Loan Program: {input_data.get('loan_program', 'N/A')}")
    
    # Initialize client
    print(f"\n🔗 Connecting to: {DEPLOYMENT_URL}")
    try:
        client = get_client(url=DEPLOYMENT_URL, api_key=API_KEY)
    except Exception as e:
        print(f"\n❌ ERROR: Failed to connect to LangGraph Cloud")
        print(f"   {e}")
        print("\nPlease check:")
        print("  1. DEPLOYMENT_URL is correct")
        print("  2. API_KEY is valid")
        print("  3. You have internet connection")
        sys.exit(1)
    
    # Create a thread
    print(f"\n🧵 Creating thread...")
    try:
        thread = await client.threads.create()
        thread_id = thread["thread_id"]
        print(f"   Thread ID: {thread_id}")
    except Exception as e:
        print(f"\n❌ ERROR: Failed to create thread")
        print(f"   {e}")
        sys.exit(1)
    
    # Run the graph
    print(f"\n▶️  Running graph: {ASSISTANT_ID}")
    print("   This may take 60-90 seconds...")
    
    try:
        run = await client.runs.create(
            thread_id,
            assistant_id=ASSISTANT_ID,
            input=input_data
        )
        run_id = run["run_id"]
        print(f"   Run ID: {run_id}")
        
        # Wait for completion
        print("\n⏳ Waiting for completion...")
        run = await client.runs.join(thread_id, run_id)
        
        print("\n✅ Run completed successfully!")
        
    except Exception as e:
        print(f"\n❌ ERROR: Run failed")
        print(f"   {e}")
        sys.exit(1)
    
    # Get the output - the state is in the thread's state after the run
    thread_state = await client.threads.get_state(thread_id)
    output = thread_state["values"]
    
    # Display results
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    
    # Execution metadata
    print(f"\n🔍 Execution ID: {output.get('execution_id', 'N/A')}")
    print(f"⏱️  Total Latency: {output.get('total_latency', 0):.2f}s")
    
    # Compartments
    compartments = output.get('compartments', [])
    print(f"\n📁 COMPARTMENTS FOUND: {len(compartments)}")
    for comp in compartments:
        print(f"   - {comp}")
    
    # Deficiencies
    deficient = output.get('deficient_conditions', [])
    print(f"\n⚠️  DEFICIENCIES FOUND: {len(deficient)}")
    
    # Top scored deficiencies
    final_results = output.get('final_results', {})
    top_n = final_results.get('top_n', [])
    print(f"\n🏆 TOP {len(top_n)} SCORED DEFICIENCIES:")
    
    for i, item in enumerate(top_n, 1):
        priority_dims = item.get('priority_dimensions', {})
        print(f"\n  {i}. {item.get('condition_id', 'N/A')}")
        print(f"     Priority Score: {item.get('priority_score', 0):.2f}")
        print(f"     Detection Confidence: {item.get('detection_confidence', 0):.2%}")
        print(f"     Severity: {priority_dims.get('severity', 0):.2f}")
        print(f"     Impact: {priority_dims.get('impact', 0):.2f}")
        print(f"     Urgency: {priority_dims.get('urgency', 0):.2f}")
        
        # Show actionable instruction
        instruction = item.get('actionable_instruction', '')
        if instruction:
            print(f"     Action: {instruction}")
    
    # Token usage
    total_tokens = output.get('total_tokens', {})
    grand_total = total_tokens.get('grand_total', {})
    print(f"\n💰 TOKEN USAGE:")
    print(f"   Total Input Tokens: {grand_total.get('total_input_tokens', 0):,}")
    print(f"   Total Output Tokens: {grand_total.get('total_output_tokens', 0):,}")
    print(f"   Grand Total: {grand_total.get('total_tokens', 0):,}")
    
    # Save output
    output_file = script_dir / "cloud_output.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n💾 Full output saved to: {output_file}")
    print("=" * 70)
    print("\n✨ Done! Your agent is working on LangGraph Cloud!")
    
    return output


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

