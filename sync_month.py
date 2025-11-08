#!/usr/bin/env python3
"""
Script to sync a specific month's mortality data from BigQuery to the database.
Usage: python3 sync_month.py [year] [month]
Example: python3 sync_month.py 2025 11
"""

from database import MortalityDatabase
from bigquery_queries import query_current_month_mortality_all_hospitals, get_bigquery_client
from datetime import date
import sys
import pandas as pd


def sync_month(year: int, month: int):
    """Sync a specific month's mortality data from BigQuery to database."""
    print("=" * 80)
    print(f"Syncing Monthly Mortality Data - {year}-{month:02d}")
    print("=" * 80)
    print()
    
    # Initialize database
    db = MortalityDatabase()
    print("✓ Database initialized")
    
    # Check if data already exists
    existing_data = db.get_monthly_data(
        start_date=date(year, month, 1),
        end_date=date(year, month, 28)
    )
    
    if len(existing_data) > 0:
        print(f"⚠ Found {len(existing_data)} existing records for {year}-{month:02d}")
        response = input("Do you want to overwrite existing data? (y/n): ")
        if response.lower() != 'y':
            print("Skipping sync. Exiting...")
            return
    
    # Connect to BigQuery
    print("Connecting to BigQuery...")
    try:
        client = get_bigquery_client()
        print("✓ Connected to BigQuery")
    except Exception as e:
        print(f"✗ Error connecting to BigQuery: {e}")
        sys.exit(1)
    
    # Query monthly data from BigQuery
    print(f"Querying mortality data for {year}-{month:02d} from BigQuery...")
    print("This may take a few minutes...")
    
    try:
        df = query_current_month_mortality_all_hospitals(year=year, month=month, client=client)
        print(f"✓ Retrieved data for {len(df)} hospitals")
        print()
        
        if len(df) == 0:
            print("⚠ No data found for this month in BigQuery.")
            return
        
        # Show sample data
        print("Sample data:")
        print(df.head().to_string())
        print()
        
        # Insert data into database
        print("Inserting data into database...")
        inserted_count = 0
        updated_count = 0
        
        for _, row in df.iterrows():
            # Check if record already exists
            existing = db.get_monthly_data(
                hospital_name=row['hospital_name'],
                start_date=date(year, month, 1),
                end_date=date(year, month, 28)
            )
            
            if len(existing) > 0:
                # Update existing record
                db.insert_monthly_data(
                    hospital_name=row['hospital_name'],
                    year=year,
                    month=month,
                    total_patients=int(row['total_patients']),
                    deaths=int(row['deaths']),
                    mortality_rate=float(row['mortality_rate'])
                )
                updated_count += 1
            else:
                # Insert new record
                db.insert_monthly_data(
                    hospital_name=row['hospital_name'],
                    year=year,
                    month=month,
                    total_patients=int(row['total_patients']),
                    deaths=int(row['deaths']),
                    mortality_rate=float(row['mortality_rate'])
                )
                inserted_count += 1
            
            if (inserted_count + updated_count) % 50 == 0:
                print(f"  Processed {inserted_count + updated_count} records...")
        
        print(f"✓ Successfully synced {len(df)} records")
        print(f"  - New records: {inserted_count}")
        print(f"  - Updated records: {updated_count}")
        print()
        
        print("=" * 80)
        print("Sync Complete!")
        print("=" * 80)
        print(f"Month: {year}-{month:02d}")
        print(f"Total hospitals: {len(df)}")
        print(f"Total records: {inserted_count + updated_count}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Check your BigQuery authentication")
        print("2. Verify the table schema matches the expected columns")
        print("3. Ensure you have read access to the BigQuery table")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 sync_month.py [year] [month]")
        print("Example: python3 sync_month.py 2025 11")
        print()
        print("Or run without arguments to sync current month:")
        today = date.today()
        print(f"Current month: {today.year}-{today.month:02d}")
        response = input(f"Sync current month ({today.year}-{today.month:02d})? (y/n): ")
        if response.lower() == 'y':
            sync_month(today.year, today.month)
        else:
            sys.exit(0)
    else:
        try:
            year = int(sys.argv[1])
            month = int(sys.argv[2])
            
            if month < 1 or month > 12:
                print("Error: Month must be between 1 and 12")
                sys.exit(1)
            
            sync_month(year, month)
        except ValueError:
            print("Error: Year and month must be integers")
            print("Usage: python3 sync_month.py [year] [month]")
            sys.exit(1)

