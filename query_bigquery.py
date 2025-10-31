#!/usr/bin/env python3
"""
Script to connect to BigQuery and query the discharged_patients_fact table.
"""

from google.cloud import bigquery
import pandas as pd

# BigQuery configuration
PROJECT_ID = "prod-tech-project1-bv479-zo027"
DATASET = "analytics"
TABLE = "discharged_patients_fact"

# Query to execute
QUERY = """
SELECT 
    patient_id, 
    cpmrn, 
    encounters, 
    hospital_name, 
    icu_discharge_disposition 
FROM `prod-tech-project1-bv479-zo027.analytics.discharged_patients_fact` 
LIMIT 1000
"""


def connect_and_query():
    """Connect to BigQuery and execute the query."""
    try:
        # Initialize BigQuery client
        # This will use Application Default Credentials (ADC)
        # Set GOOGLE_APPLICATION_CREDENTIALS environment variable if using service account
        client = bigquery.Client(project=PROJECT_ID)
        
        print(f"Connected to BigQuery project:                            {PROJECT_ID}")
        print(f"Executing query...\n")
        
        # Execute query
        query_job = client.query(QUERY)
        results = query_job.result()
        
        # Convert results to pandas DataFrame for better display
        df = results.to_dataframe()
        
        print("=" * 80)
        print(f"Query Results ({len(df)} rows)")
        print("=" * 80)
        print()
        
        # Display the DataFrame
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 50)
        pd.set_option('display.max_rows', 1000)
        
        print(df.to_string(index=False))
        print()
        print("=" * 80)
        print(f"Total rows returned: {len(df)}")
        print("=" * 80)
        
        return df
        
    except Exception as e:
        print(f"Error connecting to BigQuery or executing query: {e}")
        print("\nMake sure you have:")
        print("1. Installed google-cloud-bigquery: pip install google-cloud-bigquery pandas")
        print("2. Authenticated with Google Cloud (gcloud auth application-default login)")
        print("   OR set GOOGLE_APPLICATION_CREDENTIALS environment variable to your service account key")
        raise


if __name__ == "__main__":
    connect_and_query()
