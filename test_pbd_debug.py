#!/usr/bin/env python3
"""
Debug script to test PBD query step by step and identify failures.
"""

import sys
import time
from datetime import date, timedelta
from bigquery_queries import get_bigquery_client, query_daily_pbd
from config import BIGQUERY_PROJECT_ID, BIGQUERY_DATASET, BIGQUERY_TABLE

def log_step(step_num, description):
    """Log a test step."""
    print(f"\n{'='*80}")
    print(f"STEP {step_num}: {description}")
    print(f"{'='*80}")

def test_bigquery_connection():
    """Test 1: Can we connect to BigQuery?"""
    log_step(1, "Testing BigQuery Connection")
    try:
        client = get_bigquery_client()
        print(f"✅ BigQuery client created successfully")
        print(f"   Project: {BIGQUERY_PROJECT_ID}")
        print(f"   Dataset: {BIGQUERY_DATASET}")
        print(f"   Table: {BIGQUERY_TABLE}")
        return client
    except Exception as e:
        print(f"❌ Failed to create BigQuery client: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_november_data_exists(client):
    """Test 2: Does November 2025 data exist in BigQuery?"""
    log_step(2, "Checking if November 2025 data exists")
    try:
        query = f"""
        SELECT 
            hospital_name,
            DATE(icu_admit_date) as admit_date,
            COUNT(*) as count
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE DATE(icu_admit_date) >= '2025-11-01'
          AND DATE(icu_admit_date) <= '2025-11-06'
          AND hospital_name = 'Cachar'
        GROUP BY hospital_name, admit_date
        ORDER BY admit_date
        """
        print(f"Executing query...")
        job = client.query(query)
        results = job.result()
        df = results.to_dataframe()
        
        if len(df) > 0:
            print(f"✅ Found {len(df)} rows for November 2025 (Cachar)")
            print(f"\nSample data:")
            print(df.head(10).to_string())
            return True
        else:
            print(f"⚠️  No November 2025 data found for Cachar")
            return False
    except Exception as e:
        print(f"❌ Query failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_simple_pbd_query(client):
    """Test 3: Simple PBD query for November only"""
    log_step(3, "Testing Simple PBD Query (November 2025 only)")
    try:
        start_date = date(2025, 11, 1)
        end_date = date(2025, 11, 6)
        
        print(f"Query parameters:")
        print(f"  Hospital: Cachar")
        print(f"  Start date: {start_date}")
        print(f"  End date: {end_date}")
        print(f"  Date range: {(end_date - start_date).days} days")
        
        start_time = time.time()
        result = query_daily_pbd(
            hospital_name='Cachar',
            start_date=start_date,
            end_date=end_date,
            client=client
        )
        elapsed = time.time() - start_time
        
        print(f"\n✅ Query completed in {elapsed:.2f} seconds")
        print(f"   Rows returned: {len(result)}")
        
        if len(result) > 0:
            print(f"\nSample results:")
            print(result.head(10).to_string())
            return True
        else:
            print(f"⚠️  Query returned 0 rows")
            return False
            
    except TimeoutError as e:
        elapsed = time.time() - start_time
        print(f"❌ Query TIMED OUT after {elapsed:.2f} seconds")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"❌ Query FAILED after {elapsed:.2f} seconds")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_larger_date_range(client):
    """Test 4: PBD query with larger date range (like the frontend request)"""
    log_step(4, "Testing PBD Query with Larger Date Range (2024-08-01 to 2025-11-06)")
    try:
        start_date = date(2024, 8, 1)
        end_date = date(2025, 11, 6)
        
        print(f"Query parameters:")
        print(f"  Hospital: Cachar")
        print(f"  Start date: {start_date}")
        print(f"  End date: {end_date}")
        print(f"  Date range: {(end_date - start_date).days} days")
        print(f"  Note: This will be limited to last 180 days if > 180")
        
        start_time = time.time()
        result = query_daily_pbd(
            hospital_name='Cachar',
            start_date=start_date,
            end_date=end_date,
            client=client
        )
        elapsed = time.time() - start_time
        
        print(f"\n✅ Query completed in {elapsed:.2f} seconds")
        print(f"   Rows returned: {len(result)}")
        
        if len(result) > 0:
            print(f"\nFirst 5 rows:")
            print(result.head(5).to_string())
            print(f"\nLast 5 rows:")
            print(result.tail(5).to_string())
            
            # Check if November data is in results
            nov_data = result[result['date'].apply(lambda x: x.month == 11 and x.year == 2025)]
            if len(nov_data) > 0:
                print(f"\n✅ November 2025 data found in results: {len(nov_data)} rows")
                print(nov_data.to_string())
            else:
                print(f"\n⚠️  November 2025 data NOT found in results")
            
            return True
        else:
            print(f"⚠️  Query returned 0 rows")
            return False
            
    except TimeoutError as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"❌ Query TIMED OUT after {elapsed:.2f} seconds")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"❌ Query FAILED after {elapsed:.2f} seconds")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_raw_query_structure(client):
    """Test 5: Test the actual query structure being used"""
    log_step(5, "Testing Raw Query Structure")
    try:
        from datetime import date
        from google.cloud import bigquery
        
        start_date = date(2025, 11, 1)
        end_date = date(2025, 11, 6)
        date_array_start = start_date.isoformat()
        date_array_end = end_date.isoformat()
        
        # Build the exact query that query_daily_pbd uses
        query = f"""
        WITH admissions AS (
            SELECT 
                hospital_name,
                DATE(icu_admit_date) as admit_date,
                DATE(COALESCE(icu_discharge_date, CURRENT_TIMESTAMP())) as discharge_date,
                GENERATE_DATE_ARRAY(
                    GREATEST(DATE(icu_admit_date), DATE('{date_array_start}')),
                    LEAST(DATE(COALESCE(icu_discharge_date, CURRENT_TIMESTAMP())), DATE('{date_array_end}'))
                ) as date_array
            FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
            WHERE icu_admit_date IS NOT NULL
            AND hospital_name = 'Cachar'
            AND DATE(icu_admit_date) <= '{date_array_end}'
            AND (DATE(COALESCE(icu_discharge_date, CURRENT_TIMESTAMP())) >= '{date_array_start}' 
                 OR icu_discharge_date IS NULL)
        ),
        expanded AS (
            SELECT 
                hospital_name,
                date_value
            FROM admissions,
            UNNEST(date_array) AS date_value
        )
        SELECT 
            date_value as date,
            hospital_name,
            COUNT(*) as total_pbd
        FROM expanded
        GROUP BY date_value, hospital_name
        ORDER BY hospital_name, date_value
        LIMIT 100
        """
        
        print("Executing raw query...")
        print(f"Query length: {len(query)} characters")
        
        job_config = bigquery.QueryJobConfig(
            job_timeout_ms=60000,  # 60 second timeout
            use_legacy_sql=False
        )
        
        start_time = time.time()
        query_job = client.query(query, job_config=job_config)
        print(f"Job created: {query_job.job_id}")
        
        # Wait with progress updates
        timeout_seconds = 60
        while not query_job.done():
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                print(f"❌ Query timeout after {timeout_seconds} seconds")
                query_job.cancel()
                return False
            if int(elapsed) % 5 == 0:
                print(f"   Still waiting... ({int(elapsed)}s elapsed)")
            time.sleep(1)
            query_job.reload()
        
        elapsed = time.time() - start_time
        print(f"✅ Query completed in {elapsed:.2f} seconds")
        
        if query_job.errors:
            print(f"❌ Query has errors: {query_job.errors}")
            return False
        
        results = query_job.result()
        df = results.to_dataframe()
        print(f"✅ Results fetched: {len(df)} rows")
        
        if len(df) > 0:
            print(f"\nSample results:")
            print(df.head(10).to_string())
        
        return True
        
    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"❌ Query FAILED after {elapsed:.2f} seconds")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("PBD QUERY DEBUG SCRIPT")
    print("="*80)
    
    # Test 1: Connection
    client = test_bigquery_connection()
    if not client:
        print("\n❌ Cannot proceed without BigQuery connection")
        sys.exit(1)
    
    # Test 2: November data exists
    has_nov_data = test_november_data_exists(client)
    
    # Test 3: Simple PBD query
    simple_works = test_simple_pbd_query(client)
    
    # Test 4: Larger date range
    large_works = test_larger_date_range(client)
    
    # Test 5: Raw query structure
    raw_works = test_raw_query_structure(client)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"BigQuery Connection: {'✅' if client else '❌'}")
    print(f"November Data Exists: {'✅' if has_nov_data else '❌'}")
    print(f"Simple PBD Query (Nov only): {'✅' if simple_works else '❌'}")
    print(f"Large Date Range Query: {'✅' if large_works else '❌'}")
    print(f"Raw Query Structure: {'✅' if raw_works else '❌'}")
    print("="*80)

if __name__ == "__main__":
    main()

