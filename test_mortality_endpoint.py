#!/usr/bin/env python3
"""
Test script to debug the mortality-data endpoint timeout issue.
"""

import requests
import time
from datetime import date

# Test parameters
BASE_URL = "http://localhost:3000"
HOSPITAL = "Cachar"
START_DATE = "2024-11-07"
END_DATE = "2025-11-07"

def test_mortality_endpoint():
    """Test the mortality-data endpoint with timeout."""
    url = f"{BASE_URL}/api/mortality-data"
    params = {
        "hospital_name": HOSPITAL,
        "start_date": START_DATE,
        "end_date": END_DATE
    }
    
    print("=" * 80)
    print("Testing Mortality Data Endpoint")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"Parameters: {params}")
    print()
    
    start_time = time.time()
    
    try:
        # Set a 130 second timeout (5 seconds more than frontend's 125 seconds)
        response = requests.get(url, params=params, timeout=130)
        elapsed = time.time() - start_time
        
        print(f"✅ Request completed in {elapsed:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
            if 'monthly_data' in data:
                print(f"Monthly data rows: {len(data['monthly_data'])}")
                if len(data['monthly_data']) > 0:
                    print(f"First row: {data['monthly_data'][0]}")
                    print(f"Last row: {data['monthly_data'][-1]}")
            if 'statistics' in data:
                print(f"Statistics: {data['statistics']}")
        else:
            print(f"❌ Error response: {response.text[:500]}")
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"❌ TIMEOUT after {elapsed:.2f} seconds")
        print("The endpoint is taking longer than 130 seconds to respond")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ ERROR after {elapsed:.2f} seconds: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mortality_endpoint()

