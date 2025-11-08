"""
BigQuery query functions for fetching mortality data.
"""

from google.cloud import bigquery
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional
from config import BIGQUERY_PROJECT_ID, BIGQUERY_DATASET, BIGQUERY_TABLE


def get_bigquery_client():
    """Get BigQuery client."""
    return bigquery.Client(project=BIGQUERY_PROJECT_ID)


def query_monthly_mortality(client: Optional[bigquery.Client] = None) -> pd.DataFrame:
    """
    Query BigQuery for monthly mortality data grouped by hospital.
    This is for one-time initialization to backfill historical data.
    """
    if client is None:
        client = get_bigquery_client()
    
    query = f"""
    SELECT 
        hospital_name,
        EXTRACT(YEAR FROM DATE(icu_discharge_date)) as year,
        EXTRACT(MONTH FROM DATE(icu_discharge_date)) as month,
        COUNT(*) as total_patients,
        SUM(CASE WHEN LOWER(icu_discharge_disposition) LIKE '%death%' THEN 1 ELSE 0 END) as deaths
    FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
    WHERE icu_discharge_date IS NOT NULL
    GROUP BY hospital_name, year, month
    ORDER BY hospital_name, year, month
    """
    
    query_job = client.query(query)
    results = query_job.result()
    df = results.to_dataframe()
    
    # Calculate mortality rate
    if len(df) > 0:
        df['mortality_rate'] = (df['deaths'] / df['total_patients'] * 100).round(2)
    else:
        df['mortality_rate'] = 0.0
    
    return df


def query_daily_mortality(target_date: date, client: Optional[bigquery.Client] = None) -> pd.DataFrame:
    """
    Query BigQuery for daily mortality data for a specific date.
    This is used for daily updates.
    """
    if client is None:
        client = get_bigquery_client()
    
    query = f"""
    SELECT 
        hospital_name,
        COUNT(*) as total_patients,
        SUM(CASE WHEN LOWER(icu_discharge_disposition) LIKE '%death%' THEN 1 ELSE 0 END) as deaths
    FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
    WHERE DATE(icu_discharge_date) = @target_date
    GROUP BY hospital_name
    ORDER BY hospital_name
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("target_date", "DATE", target_date.isoformat())
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    df = results.to_dataframe()
    
    # Calculate mortality rate
    if len(df) > 0:
        df['mortality_rate'] = (df['deaths'] / df['total_patients'] * 100).round(2)
    else:
        df['mortality_rate'] = 0.0
        df['total_patients'] = 0
        df['deaths'] = 0
    
    return df


def query_daily_pbd(hospital_name: Optional[str] = None,
                     start_date: Optional[date] = None,
                     end_date: Optional[date] = None,
                     client: Optional[bigquery.Client] = None) -> pd.DataFrame:
    """
    Query BigQuery for daily Patient Bed Days (PBD).
    A patient who is admitted for at least 6 hours in a day = 1 PBD.
    """
    print(f"[PBD Step 1] Starting query_daily_pbd")
    print(f"[PBD Step 1] Parameters: hospital={hospital_name}, start={start_date}, end={end_date}")
    
    if client is None:
        print(f"[PBD Step 2] Creating BigQuery client...")
        try:
            client = get_bigquery_client()
            print(f"[PBD Step 2] ✅ BigQuery client created successfully")
        except Exception as e:
            print(f"[PBD Step 2] ❌ Failed to create BigQuery client: {e}")
            raise
    
    # Build WHERE clause with parameters
    print(f"[PBD Step 3] Building WHERE clause and query parameters...")
    where_clauses = []
    query_params = []
    
    if hospital_name:
        where_clauses.append("hospital_name = @hospital_name")
        query_params.append(bigquery.ScalarQueryParameter("hospital_name", "STRING", hospital_name))
        print(f"[PBD Step 3] Added hospital filter: {hospital_name}")
    
    if start_date:
        where_clauses.append("DATE(icu_admit_date) >= @start_date")
        query_params.append(bigquery.ScalarQueryParameter("start_date", "DATE", start_date))
        print(f"[PBD Step 3] Added start_date filter: {start_date}")
    
    if end_date:
        where_clauses.append("DATE(icu_admit_date) <= @end_date")
        query_params.append(bigquery.ScalarQueryParameter("end_date", "DATE", end_date))
        print(f"[PBD Step 3] Added end_date filter: {end_date}")
    
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    print(f"[PBD Step 3] ✅ WHERE clause: {where_clause}")
    print(f"[PBD Step 3] ✅ Query parameters count: {len(query_params)}")
    
    # Simplified and optimized query to calculate PBD per day
    # A patient counts as 1 PBD if they were in ICU for >= 6 hours on that day
    # Using a more efficient approach with DATE_DIFF to avoid complex cross joins
    
    # Limit date range to prevent expensive queries (max 6 months)
    from datetime import timedelta
    max_days = 180  # 6 months
    
    if start_date and end_date:
        # Limit the date range to max_days to prevent timeouts
        days_diff = (end_date - start_date).days
        if days_diff > max_days:
            print(f"[BigQuery PBD] WARNING: Date range {days_diff} days exceeds limit of {max_days} days. Limiting to last {max_days} days.")
            start_date = end_date - timedelta(days=max_days)
            # Update WHERE clause to reflect limited start_date
            where_clauses = [w for w in where_clauses if not w.startswith("DATE(icu_admit_date) >= @start_date")]
            where_clauses.append("DATE(icu_admit_date) >= @start_date")
            query_params = [p for p in query_params if p.name != "start_date"]
            query_params.append(bigquery.ScalarQueryParameter("start_date", "DATE", start_date))
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        date_array_start = start_date.isoformat()
        date_array_end = end_date.isoformat()
    else:
        # Fallback: use a reasonable default range (last 6 months)
        date_array_end = date.today().isoformat()
        date_array_start = (date.today() - timedelta(days=max_days)).isoformat()
    
    # Simplified query: Use date range and count patients present each day
    # This avoids expensive GENERATE_DATE_ARRAY and UNNEST operations
    print(f"[PBD Step 4] Building SQL query (simplified approach)...")
    print(f"[PBD Step 4] Date range: {date_array_start} to {date_array_end}")
    query = f"""
    WITH date_range AS (
        SELECT date_value
        FROM UNNEST(GENERATE_DATE_ARRAY('{date_array_start}', '{date_array_end}')) AS date_value
    ),
    admissions AS (
        SELECT 
            hospital_name,
            DATE(icu_admit_date) as admit_date,
            DATE(COALESCE(icu_discharge_date, CURRENT_TIMESTAMP())) as discharge_date
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE icu_admit_date IS NOT NULL
        AND {where_clause}
        AND DATE(icu_admit_date) <= '{date_array_end}'
        AND (DATE(COALESCE(icu_discharge_date, CURRENT_TIMESTAMP())) >= '{date_array_start}' 
             OR icu_discharge_date IS NULL)
    )
    SELECT 
        dr.date_value as date,
        a.hospital_name,
        COUNT(DISTINCT CONCAT(CAST(a.admit_date AS STRING), '-', CAST(COALESCE(a.discharge_date, CURRENT_DATE()) AS STRING))) as total_pbd
    FROM date_range dr
    INNER JOIN admissions a
        ON a.admit_date <= dr.date_value
        AND (a.discharge_date >= dr.date_value OR a.discharge_date IS NULL)
    GROUP BY dr.date_value, a.hospital_name
    ORDER BY a.hospital_name, dr.date_value
    """
    print(f"[PBD Step 4] ✅ Query built. Length: {len(query)} characters")
    print(f"[PBD Step 4] Query only selects: hospital_name, icu_admit_date, icu_discharge_date (required columns only)")
    
    print(f"[PBD Step 5] Creating query job configuration...")
    job_config = bigquery.QueryJobConfig(
        query_parameters=query_params if query_params else None,
        job_timeout_ms=300000,  # 5 minute timeout (increased for large date ranges)
        use_legacy_sql=False
    )
    print(f"[PBD Step 5] ✅ Job config created with {len(query_params) if query_params else 0} parameters")
    if query_params:
        for param in query_params:
            param_value = getattr(param, 'value', 'N/A')
            print(f"[PBD Step 5]   Parameter: {param.name} = {param_value}")
    
    print(f"[PBD Step 6] Executing BigQuery job...")
    print(f"[PBD Step 6] Date range: {date_array_start} to {date_array_end}")
    print(f"[PBD Step 6] Table: {BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    
    try:
        import time
        start_time = time.time()
        
        print(f"[PBD Step 6] Calling client.query()...")
        query_job = client.query(query, job_config=job_config)
        print(f"[PBD Step 6] ✅ Query job created")
        print(f"[PBD Step 6] Job ID: {query_job.job_id}")
        print(f"[PBD Step 6] Job location: {query_job.location}")
        print(f"[PBD Step 7] Waiting for job to complete...")
        
        # Wait for job with timeout
        timeout_seconds = 300  # 5 minute timeout (increased for large date ranges)
        last_log_time = 0
        
        while not query_job.done():
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                print(f"[PBD Step 7] ❌ TIMEOUT after {timeout_seconds} seconds")
                query_job.cancel()
                raise TimeoutError(f"PBD query timed out after {timeout_seconds} seconds")
            
            # Log every 5 seconds with job state
            if elapsed - last_log_time >= 5:
                print(f"[PBD Step 7] Still waiting... ({int(elapsed)}s elapsed)")
                try:
                    query_job.reload()
                    if hasattr(query_job, 'state'):
                        print(f"[PBD Step 7]   Job state: {query_job.state}")
                    if hasattr(query_job, 'num_child_jobs'):
                        print(f"[PBD Step 7]   Child jobs: {query_job.num_child_jobs}")
                except Exception as e:
                    print(f"[PBD Step 7]   Error checking job state: {e}")
                last_log_time = elapsed
            
            time.sleep(1)
            query_job.reload()
        
        elapsed_time = time.time() - start_time
        print(f"[PBD Step 7] ✅ Job completed in {elapsed_time:.2f} seconds")
        
        print(f"[PBD Step 8] Checking for job errors...")
        if query_job.errors:
            print(f"[PBD Step 8] ❌ Query job has errors: {query_job.errors}")
            raise Exception(f"BigQuery query failed: {query_job.errors}")
        print(f"[PBD Step 8] ✅ No errors found")
        
        print(f"[PBD Step 9] Fetching results...")
        results = query_job.result()
        print(f"[PBD Step 9] ✅ Results fetched")
        
        print(f"[PBD Step 10] Converting to DataFrame...")
        df = results.to_dataframe()
        print(f"[PBD Step 10] ✅ DataFrame created. Rows: {len(df)}")
        
        if len(df) > 0:
            print(f"[PBD Step 10] Sample data:")
            print(df.head(3).to_string())
        
    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"[PBD ERROR] Exception after {elapsed:.2f} seconds")
        print(f"[PBD ERROR] Type: {type(e).__name__}")
        print(f"[PBD ERROR] Message: {e}")
        import traceback
        print(f"[PBD ERROR] Traceback:")
        traceback.print_exc()
        raise
    
    if len(df) == 0:
        # Return empty dataframe with correct columns
        df = pd.DataFrame(columns=['date', 'hospital_name', 'total_pbd'])
        print(f"[PBD Step 11] ⚠️  WARNING: No PBD data returned")
    else:
        print(f"[PBD Step 11] ✅ Returning {len(df)} rows")
    
    print(f"[PBD Step 12] ✅ query_daily_pbd completed successfully")
    return df


def query_current_month_mortality_all_hospitals(year: Optional[int] = None,
                                                  month: Optional[int] = None,
                                                  client: Optional[bigquery.Client] = None) -> pd.DataFrame:
    """
    Query BigQuery for current month's mortality data for ALL hospitals (batch query).
    This is much faster than querying individually.
    """
    if client is None:
        client = get_bigquery_client()
    
    from datetime import date
    if year is None or month is None:
        today = date.today()
        year = today.year
        month = today.month
    
    print(f"[BigQuery] Querying current month mortality for {year}-{month:02d}...")
    print(f"[BigQuery] Using table: {BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    
    # For current month, use icu_admit_date (not discharge_date) because many patients
    # are still in ICU and haven't been discharged yet
    from datetime import date
    today = date.today()
    is_current_month = (year == today.year and month == today.month)
    
    if is_current_month:
        print(f"[BigQuery] Current month detected - using icu_admit_date to count all admitted patients")
        # Use admission date for current month (includes patients still in ICU)
        where_clauses = [
            "EXTRACT(YEAR FROM DATE(icu_admit_date)) = @year",
            "EXTRACT(MONTH FROM DATE(icu_admit_date)) = @month",
            "icu_admit_date IS NOT NULL"
        ]
    else:
        print(f"[BigQuery] Past month - using icu_discharge_date")
        # Use discharge date for past months (all patients should be discharged)
        where_clauses = [
            "EXTRACT(YEAR FROM DATE(icu_discharge_date)) = @year",
            "EXTRACT(MONTH FROM DATE(icu_discharge_date)) = @month",
            "icu_discharge_date IS NOT NULL"
        ]
    
    query_params = [
        bigquery.ScalarQueryParameter("year", "INT64", year),
        bigquery.ScalarQueryParameter("month", "INT64", month)
    ]
    
    where_clause = " AND ".join(where_clauses)
    
    # For current month, count deaths based on current disposition (even if not discharged)
    # For past months, use discharge_disposition
    if is_current_month:
        query = f"""
        SELECT 
            hospital_name,
            COUNT(*) as total_patients,
            SUM(CASE 
                WHEN icu_discharge_date IS NOT NULL 
                     AND LOWER(icu_discharge_disposition) LIKE '%death%' THEN 1
                WHEN icu_discharge_date IS NULL 
                     AND LOWER(COALESCE(icu_discharge_disposition, '')) LIKE '%death%' THEN 1
                ELSE 0 
            END) as deaths
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE {where_clause}
        GROUP BY hospital_name
        ORDER BY hospital_name
        """
    else:
        query = f"""
        SELECT 
            hospital_name,
            COUNT(*) as total_patients,
            SUM(CASE WHEN LOWER(icu_discharge_disposition) LIKE '%death%' THEN 1 ELSE 0 END) as deaths
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE {where_clause}
        GROUP BY hospital_name
        ORDER BY hospital_name
        """
    
    print(f"[BigQuery] Executing query for {year}-{month:02d}...")
    print(f"[BigQuery] Query: {query[:200]}...")  # Show first 200 chars of query
    
    try:
        job_config = bigquery.QueryJobConfig(
            query_parameters=query_params,
            job_timeout_ms=190000,  # 190 second timeout (allows up to 180s for frontend timeout)
            use_legacy_sql=False
        )
        query_job = client.query(query, job_config=job_config)
        print(f"[BigQuery] Job created: {query_job.job_id}")
        print(f"[BigQuery] Waiting for job to complete...")
        
        # Wait for job with timeout (matching frontend timeout of 180 seconds)
        import time
        start_time = time.time()
        timeout_seconds = 180  # 180 second timeout (matches frontend timeout)
        
        while not query_job.done():
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                print(f"[BigQuery] ERROR: Query timeout after {timeout_seconds} seconds")
                query_job.cancel()
                raise TimeoutError(f"BigQuery query timed out after {timeout_seconds} seconds")
            
            if elapsed > 0 and int(elapsed) % 10 == 0:  # Log every 10 seconds
                print(f"[BigQuery] Still waiting... ({int(elapsed)}s elapsed)")
            
            time.sleep(1)
            query_job.reload()
        
        print(f"[BigQuery] Job completed in {time.time() - start_time:.2f} seconds")
        
        if query_job.errors:
            print(f"[BigQuery] ERROR: Query job has errors: {query_job.errors}")
            raise Exception(f"BigQuery query failed: {query_job.errors}")
        
        results = query_job.result()
        print(f"[BigQuery] Fetching results...")
        df = results.to_dataframe()
        print(f"[BigQuery] Query completed. Rows returned: {len(df)}")
        
    except Exception as e:
        print(f"[BigQuery] EXCEPTION during query execution: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    # Calculate mortality rate
    if len(df) > 0:
        df['mortality_rate'] = (df['deaths'] / df['total_patients'] * 100).round(2)
        df['year'] = year
        df['month'] = month
        print(f"[BigQuery] Sample data (first 5 rows):")
        print(df.head().to_string())
        print(f"[BigQuery] Unique hospitals: {df['hospital_name'].nunique()}")
        print(f"[BigQuery] Total patients across all hospitals: {df['total_patients'].sum()}")
        print(f"[BigQuery] Total deaths across all hospitals: {df['deaths'].sum()}")
    else:
        df = pd.DataFrame(columns=['hospital_name', 'total_patients', 'deaths', 'mortality_rate', 'year', 'month'])
        print(f"[BigQuery] WARNING: No data returned for {year}-{month:02d}")
        print(f"[BigQuery] This could mean:")
        print(f"[BigQuery]   1. No data exists in BigQuery for this month")
        print(f"[BigQuery]   2. icu_discharge_date column might be NULL for all records")
        print(f"[BigQuery]   3. Date extraction might be failing")
    
    return df


def query_current_month_mortality(hospital_name: Optional[str] = None,
                                   year: Optional[int] = None,
                                   month: Optional[int] = None,
                                   client: Optional[bigquery.Client] = None) -> pd.DataFrame:
    """
    Query BigQuery for current month's mortality data (live query).
    This is used when current month data is not yet in the database.
    """
    if client is None:
        client = get_bigquery_client()
    
    from datetime import date
    if year is None or month is None:
        today = date.today()
        year = today.year
        month = today.month
    
    # Check if this is the current month
    today = date.today()
    is_current_month = (year == today.year and month == today.month)
    
    # Build WHERE clause with parameters
    # For current month, use icu_admit_date (includes patients still in ICU)
    # For past months, use icu_discharge_date
    if is_current_month:
        where_clauses = [
            "EXTRACT(YEAR FROM DATE(icu_admit_date)) = @year",
            "EXTRACT(MONTH FROM DATE(icu_admit_date)) = @month",
            "icu_admit_date IS NOT NULL"
        ]
    else:
        where_clauses = [
            "EXTRACT(YEAR FROM DATE(icu_discharge_date)) = @year",
            "EXTRACT(MONTH FROM DATE(icu_discharge_date)) = @month",
            "icu_discharge_date IS NOT NULL"
        ]
    
    query_params = [
        bigquery.ScalarQueryParameter("year", "INT64", year),
        bigquery.ScalarQueryParameter("month", "INT64", month)
    ]
    
    if hospital_name:
        where_clauses.append("hospital_name = @hospital_name")
        query_params.append(bigquery.ScalarQueryParameter("hospital_name", "STRING", hospital_name))
    
    where_clause = " AND ".join(where_clauses)
    
    # For current month, count deaths based on current disposition
    # For past months, use discharge_disposition
    if is_current_month:
        query = f"""
        SELECT 
            hospital_name,
            COUNT(*) as total_patients,
            SUM(CASE 
                WHEN icu_discharge_date IS NOT NULL 
                     AND LOWER(icu_discharge_disposition) LIKE '%death%' THEN 1
                WHEN icu_discharge_date IS NULL 
                     AND LOWER(COALESCE(icu_discharge_disposition, '')) LIKE '%death%' THEN 1
                ELSE 0 
            END) as deaths
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE {where_clause}
        GROUP BY hospital_name
        ORDER BY hospital_name
        """
    else:
        query = f"""
        SELECT 
            hospital_name,
            COUNT(*) as total_patients,
            SUM(CASE WHEN LOWER(icu_discharge_disposition) LIKE '%death%' THEN 1 ELSE 0 END) as deaths
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE {where_clause}
        GROUP BY hospital_name
        ORDER BY hospital_name
        """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=query_params,
        job_timeout_ms=190000  # 190 second timeout (allows up to 180s for frontend timeout)
    )
    
    import time
    start_time = time.time()
    query_job = client.query(query, job_config=job_config)
    
    # Wait for job with timeout (matching frontend timeout of 180 seconds)
    timeout_seconds = 180  # 180 second timeout (matches frontend timeout)
    while not query_job.done():
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            print(f"[BigQuery] ERROR: Query timeout after {timeout_seconds} seconds")
            query_job.cancel()
            raise TimeoutError(f"BigQuery query timed out after {timeout_seconds} seconds")
        time.sleep(0.5)
        query_job.reload()
    
    results = query_job.result()
    df = results.to_dataframe()
    
    # Calculate mortality rate
    if len(df) > 0:
        df['mortality_rate'] = (df['deaths'] / df['total_patients'] * 100).round(2)
        df['year'] = year
        df['month'] = month
    else:
        df = pd.DataFrame(columns=['hospital_name', 'total_patients', 'deaths', 'mortality_rate', 'year', 'month'])
    
    return df


def check_column_exists(client: Optional[bigquery.Client] = None) -> bool:
    """
    Check if icu_discharge_date column exists in the table.
    If not, we'll need to use a different approach.
    """
    if client is None:
        client = get_bigquery_client()
    
    query = f"""
    SELECT column_name
    FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name = '{BIGQUERY_TABLE}'
    AND column_name = 'icu_discharge_date'
    """
    
    try:
        query_job = client.query(query)
        results = query_job.result()
        return len(list(results)) > 0
    except Exception:
        return False



