#!/usr/bin/env python3
"""
Test script to verify the raw-data endpoint works with increased timeout.
"""

import requests
import time
from datetime import date

# Test parameters
BASE_URL = "http://localhost:3000"
HOSPITAL = "Cachar"
START_DATE = "2024-11-07"
END_DATE = "2025-11-07"

def test_raw_data_endpoint():
    """Test the raw-data endpoint with increased timeout."""
    url = f"{BASE_URL}/api/raw-data"
    params = {
        "hospital_name": HOSPITAL,
        "start_date": START_DATE,
        "end_date": END_DATE
    }
    
    print("=" * 80)
    print("Testing Raw Data Endpoint")
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
            print(f"Response rows: {len(data)}")
            
            # Check for November 2025 data
            today = date.today()
            current_year = today.year
            current_month = today.month
            
            nov_data = [row for row in data if row.get('year') == current_year and row.get('month') == current_month]
            print(f"November {current_year} data rows: {len(nov_data)}")
            
            if len(nov_data) > 0:
                print(f"✅ November data found!")
                print(f"Sample: {nov_data[0]}")
            else:
                print(f"⚠️  No November data in response")
                # Show available months
                months = sorted(set([f"{row['year']}-{row['month']:02d}" for row in data]))
                print(f"Available months: {months[-6:] if len(months) > 6 else months}")
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
    test_raw_data_endpoint()

