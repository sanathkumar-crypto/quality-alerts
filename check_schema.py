#!/usr/bin/env python3
"""
Helper script to check BigQuery table schema.
Use this to find the correct date column name for mortality queries.
"""

from google.cloud import bigquery
from config import BIGQUERY_PROJECT_ID, BIGQUERY_DATASET, BIGQUERY_TABLE


def check_schema():
    """Check the schema of the BigQuery table."""
    client = bigquery.Client(project=BIGQUERY_PROJECT_ID)
    
    query = f"""
    SELECT 
        column_name, 
        data_type,
        is_nullable
    FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name = '{BIGQUERY_TABLE}'
    ORDER BY ordinal_position
    """
    
    print("=" * 80)
    print(f"BigQuery Table Schema: {BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print("=" * 80)
    print()
    
    try:
        query_job = client.query(query)
        results = query_job.result()
        
        print(f"{'Column Name':<40} {'Data Type':<20} {'Nullable':<10}")
        print("-" * 80)
        
        date_columns = []
        for row in results:
            print(f"{row.column_name:<40} {row.data_type:<20} {row.is_nullable:<10}")
            
            # Track potential date columns
            if 'date' in row.column_name.lower() or 'time' in row.column_name.lower():
                date_columns.append(row.column_name)
        
        print()
        print("=" * 80)
        
        if date_columns:
            print("Potential date columns found:")
            for col in date_columns:
                print(f"  - {col}")
            print()
            print("Update 'icu_discharge_date' in bigquery_queries.py with the correct column name.")
        else:
            print("⚠ No obvious date columns found.")
            print("You may need to check the data to see which column contains date information.")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"Error checking schema: {e}")
        print("\nTroubleshooting:")
        print("1. Check your BigQuery authentication")
        print("2. Verify the table name is correct")
        print("3. Ensure you have read access to the INFORMATION_SCHEMA")


if __name__ == "__main__":
    check_schema()

