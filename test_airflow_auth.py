"""
Quick authentication test for Airflow endpoint.

This script just tests if your credentials work.
"""
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

# Configuration
AIRFLOW_BASE_URL = "https://uat-airflow-llm.cybersoftbpo.ai"
AIRFLOW_USERNAME = os.getenv("AIRFLOW_USERNAME")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD") 

def test_authentication():
    """Test if credentials work by listing DAGs."""
    print("=" * 80)
    print("🔐 TESTING AIRFLOW AUTHENTICATION")
    print("=" * 80)
    
    print(f"\nBase URL: {AIRFLOW_BASE_URL}")
    print(f"Username: {AIRFLOW_USERNAME}")
    
    # Validate credentials are set
    if AIRFLOW_USERNAME == "your_username_here" or AIRFLOW_PASSWORD == "your_password_here":
        print("\n❌ ERROR: Please update AIRFLOW_USERNAME and AIRFLOW_PASSWORD in the script!")
        return False
    
    # Test authentication by listing DAGs
    url = f"{AIRFLOW_BASE_URL}/api/v1/dags"
    
    print(f"\nTesting endpoint: {url}")
    print("Attempting to list DAGs...")
    
    try:
        response = httpx.get(
            url,
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            timeout=30.0,
            params={"limit": 5}
        )
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ AUTHENTICATION SUCCESSFUL!")
            
            data = response.json()
            dags = data.get('dags', [])
            
            print(f"\nFound {data.get('total_entries', 0)} DAGs")
            print("\nFirst few DAGs:")
            for dag in dags[:5]:
                print(f"  • {dag.get('dag_id')} - {dag.get('is_active', 'N/A')}")
            
            # Check if check_condition_v4 exists
            print("\nLooking for check_condition_v4...")
            v4_url = f"{AIRFLOW_BASE_URL}/api/v1/dags/check_condition_v4"
            v4_response = httpx.get(
                v4_url,
                auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
                timeout=30.0
            )
            
            if v4_response.status_code == 200:
                print("✅ check_condition_v4 DAG found and accessible!")
                dag_info = v4_response.json()
                print(f"   Is Active: {dag_info.get('is_active')}")
                print(f"   Is Paused: {dag_info.get('is_paused')}")
            else:
                print("⚠️  check_condition_v4 DAG not found or not accessible")
            
            return True
        
        elif response.status_code == 401:
            print("❌ AUTHENTICATION FAILED!")
            print("   Please check your username and password.")
            return False
        
        else:
            print(f"❌ UNEXPECTED STATUS: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    
    except httpx.ConnectError:
        print("❌ CONNECTION ERROR!")
        print("   Could not connect to Airflow. Check the URL and your network connection.")
        return False
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🧪 Testing Airflow Authentication...\n")
    success = test_authentication()
    
    if success:
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\nYou can now run: python test_airflow_v4.py")
        print("to trigger a full DAG execution test.")
    else:
        print("\n" + "=" * 80)
        print("❌ TESTS FAILED")
        print("=" * 80)
        print("\nPlease fix the issues above before proceeding.")

