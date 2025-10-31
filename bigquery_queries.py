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
    if client is None:
        client = get_bigquery_client()
    
    # Build WHERE clause with parameters
    where_clauses = []
    query_params = []
    
    if hospital_name:
        where_clauses.append("hospital_name = @hospital_name")
        query_params.append(bigquery.ScalarQueryParameter("hospital_name", "STRING", hospital_name))
    
    if start_date:
        where_clauses.append("DATE(icu_admit_date) >= @start_date")
        query_params.append(bigquery.ScalarQueryParameter("start_date", "DATE", start_date))
    
    if end_date:
        where_clauses.append("DATE(icu_admit_date) <= @end_date")
        query_params.append(bigquery.ScalarQueryParameter("end_date", "DATE", end_date))
    
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Simplified and optimized query to calculate PBD per day
    # A patient counts as 1 PBD if they were in ICU for >= 6 hours on that day
    # Using a more efficient approach with DATE_DIFF to avoid complex cross joins
    if start_date and end_date:
        # Generate date array based on filter dates (faster than scanning all dates)
        date_array_start = start_date.isoformat()
        date_array_end = end_date.isoformat()
    else:
        # Fallback: use a reasonable default range
        from datetime import timedelta
        date_array_end = date.today().isoformat()
        date_array_start = (date.today() - timedelta(days=365)).isoformat()
    
    query = f"""
    WITH date_range AS (
        SELECT date_value
        FROM UNNEST(GENERATE_DATE_ARRAY('{date_array_start}', '{date_array_end}')) AS date_value
    ),
    admissions AS (
        SELECT 
            hospital_name,
            DATE(icu_admit_date) as admit_date,
            DATETIME(icu_admit_date) as admit_datetime,
            COALESCE(DATETIME(icu_discharge_date), CURRENT_DATETIME()) as discharge_datetime,
            DATE(COALESCE(icu_discharge_date, CURRENT_DATETIME())) as discharge_date
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE icu_admit_date IS NOT NULL
        AND {where_clause}
    ),
    daily_pbd AS (
        SELECT 
            dr.date_value as date,
            a.hospital_name,
            COUNTIF(
                -- Same day admit/discharge: >= 6 hours
                (a.admit_date = dr.date_value AND a.discharge_date = dr.date_value AND
                 DATETIME_DIFF(a.discharge_datetime, a.admit_datetime, HOUR) >= 6)
                OR
                -- Admission day with multi-day stay: >= 6 hours on admission day
                (a.admit_date = dr.date_value AND a.discharge_date > dr.date_value AND
                 DATETIME_DIFF(DATETIME(dr.date_value, '23:59:59'), a.admit_datetime, HOUR) >= 6)
                OR
                -- Discharge day with multi-day stay: >= 6 hours on discharge day
                (a.discharge_date = dr.date_value AND a.admit_date < dr.date_value AND
                 DATETIME_DIFF(a.discharge_datetime, DATETIME(dr.date_value, '00:00:00'), HOUR) >= 6)
                OR
                -- Full days in between (always count as 1)
                (a.admit_date < dr.date_value AND 
                 (a.discharge_date > dr.date_value OR a.discharge_date IS NULL))
            ) as total_pbd
        FROM date_range dr
        CROSS JOIN admissions a
        WHERE a.admit_date <= dr.date_value
        AND (a.discharge_date >= dr.date_value OR a.discharge_date IS NULL)
        GROUP BY dr.date_value, a.hospital_name
    )
    SELECT 
        date,
        hospital_name,
        total_pbd
    FROM daily_pbd
    WHERE total_pbd > 0
    ORDER BY hospital_name, date
    """
    
    job_config = None
    if query_params:
        job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    
    query_job = client.query(query, job_config=job_config)
    results = query_job.result()
    df = results.to_dataframe()
    
    if len(df) == 0:
        # Return empty dataframe with correct columns
        df = pd.DataFrame(columns=['date', 'hospital_name', 'total_pbd'])
    
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



