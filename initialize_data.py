#!/usr/bin/env python3
"""
One-time initialization script to backfill historical monthly mortality data.
This calculates monthly death counts per hospital from BigQuery.
"""

from database import MortalityDatabase
from bigquery_queries import query_monthly_mortality, check_column_exists, get_bigquery_client
from datetime import datetime
import sys
import pandas as pd


def initialize_historical_data():
    """Initialize database with historical monthly mortality data."""
    print("=" * 80)
    print("Initializing Historical Mortality Data")
    print("=" * 80)
    print()
    
    # Initialize database
    db = MortalityDatabase()
    print("✓ Database initialized")
    
    # Check BigQuery connection and column
    print("Connecting to BigQuery...")
    client = get_bigquery_client()
    
    # Check if icu_discharge_date column exists
    print("Checking table schema...")
    if not check_column_exists(client):
        print("⚠ Warning: 'icu_discharge_date' column not found.")
        print("Will attempt to query using alternative methods...")
        # You may need to adjust the query based on your actual schema
        print("Please ensure the BigQuery table has a discharge date column.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...")
            return
    
    print("✓ Connected to BigQuery")
    print()
    
    # Query monthly mortality data
    print("Querying historical monthly mortality data from BigQuery...")
    print("This may take a few minutes depending on data size...")
    
    try:
        df = query_monthly_mortality(client)
        print(f"✓ Retrieved {len(df)} monthly records")
        print()
        
        if len(df) == 0:
            print("⚠ No data found. Please check your BigQuery table and query.")
            return
        
        # Insert data into database
        print("Inserting data into database...")
        inserted_count = 0
        
        for _, row in df.iterrows():
            db.insert_monthly_data(
                hospital_name=row['hospital_name'],
                year=int(row['year']),
                month=int(row['month']),
                total_patients=int(row['total_patients']),
                deaths=int(row['deaths']),
                mortality_rate=float(row['mortality_rate'])
            )
            inserted_count += 1
            
            if inserted_count % 100 == 0:
                print(f"  Processed {inserted_count} records...")
        
        print(f"✓ Successfully inserted {inserted_count} monthly records")
        print()
        
        # Calculate and store statistics
        print("Calculating statistics for each hospital...")
        calculate_statistics(db)
        print("✓ Statistics calculated and stored")
        print()
        
        print("=" * 80)
        print("Initialization Complete!")
        print("=" * 80)
        print(f"Total hospitals: {len(db.get_all_hospitals())}")
        print(f"Total monthly records: {inserted_count}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your BigQuery authentication")
        print("2. Verify the table schema matches the expected columns")
        print("3. Ensure you have read access to the BigQuery table")
        sys.exit(1)


def calculate_statistics(db: MortalityDatabase):
    """Calculate average and standard deviation for each hospital."""
    hospitals = db.get_all_hospitals()
    
    for hospital in hospitals:
        # Get all monthly data for this hospital
        monthly_data = db.get_monthly_data(hospital_name=hospital)
        
        if len(monthly_data) == 0:
            continue
        
        # Calculate statistics
        mortality_rates = monthly_data['mortality_rate'].values
        avg_mortality = mortality_rates.mean()
        std_deviation = mortality_rates.std()
        
        # If std_deviation is NaN (only one data point), set to 0
        if pd.isna(std_deviation):
            std_deviation = 0.0
        
        threshold_3sd = avg_mortality + (3 * std_deviation)
        
        # Store statistics
        db.update_statistics(
            hospital_name=hospital,
            avg_mortality=avg_mortality,
            std_deviation=std_deviation,
            threshold_3sd=threshold_3sd
        )


if __name__ == "__main__":
    initialize_historical_data()

