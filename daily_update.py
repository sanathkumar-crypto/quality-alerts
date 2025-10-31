#!/usr/bin/env python3
"""
Daily update script to query previous day's data and append to database.
Should be run via cron job or scheduler daily.
"""

from database import MortalityDatabase
from bigquery_queries import query_daily_mortality, get_bigquery_client
from datetime import date, timedelta, datetime
import sys
import pandas as pd


def daily_update(target_date: date = None):
    """Update database with previous day's mortality data."""
    # Use previous day if no date specified
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    
    print("=" * 80)
    print(f"Daily Mortality Data Update - {target_date}")
    print("=" * 80)
    print()
    
    # Initialize database
    db = MortalityDatabase()
    print("✓ Database initialized")
    
    # Connect to BigQuery
    print("Connecting to BigQuery...")
    try:
        client = get_bigquery_client()
        print("✓ Connected to BigQuery")
    except Exception as e:
        print(f"✗ Error connecting to BigQuery: {e}")
        sys.exit(1)
    
    # Query daily data
    print(f"Querying mortality data for {target_date}...")
    try:
        df = query_daily_mortality(target_date, client)
        print(f"✓ Retrieved data for {len(df)} hospitals")
        
        if len(df) == 0:
            print("⚠ No data found for this date.")
            return
        
    except Exception as e:
        print(f"✗ Error querying data: {e}")
        sys.exit(1)
    
    # Insert/update daily data
    print("Inserting daily data into database...")
    inserted_count = 0
    
    for _, row in df.iterrows():
        db.insert_daily_data(
            hospital_name=row['hospital_name'],
            date_obj=target_date,
            total_patients=int(row['total_patients']),
            deaths=int(row['deaths']),
            mortality_rate=float(row['mortality_rate'])
        )
        inserted_count += 1
    
    print(f"✓ Inserted {inserted_count} daily records")
    
    # Update monthly aggregation if it's the last day of the month
    if target_date.day == (target_date.replace(day=28) + timedelta(days=4)).day - 4:
        print("Last day of month detected. Updating monthly aggregation...")
        update_monthly_aggregation(db, target_date)
    
    # Recalculate statistics with new data
    print("Recalculating statistics...")
    recalculate_statistics(db)
    print("✓ Statistics updated")
    
    # Check for alerts
    print("Checking for alerts...")
    alerts = check_alerts(db, target_date)
    
    if alerts:
        print(f"⚠ {len(alerts)} alert(s) detected:")
        for alert in alerts:
            print(f"  - {alert['hospital_name']}: Mortality rate {alert['mortality_rate']:.2f}% "
                  f"exceeds threshold {alert['threshold']:.2f}%")
        # TODO: Send alerts via email or other notification system
    else:
        print("✓ No alerts")
    
    print()
    print("=" * 80)
    print("Daily Update Complete!")
    print("=" * 80)


def update_monthly_aggregation(db: MortalityDatabase, month_end_date: date):
    """Update monthly aggregation from daily data."""
    year = month_end_date.year
    month = month_end_date.month
    
    # Get all hospitals
    hospitals = db.get_all_hospitals()
    
    # Get daily data for the month
    start_date = date(year, month, 1)
    end_date = month_end_date
    
    for hospital in hospitals:
        # Query daily data for this hospital in this month
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                SUM(total_patients) as total_patients,
                SUM(deaths) as deaths
            FROM daily_mortality
            WHERE hospital_name = ? 
            AND date >= ? 
            AND date <= ?
        """, (hospital, start_date.isoformat(), end_date.isoformat()))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] is not None:
            total_patients = result[0]
            deaths = result[1]
            mortality_rate = (deaths / total_patients * 100) if total_patients > 0 else 0.0
            
            db.insert_monthly_data(
                hospital_name=hospital,
                year=year,
                month=month,
                total_patients=total_patients,
                deaths=deaths,
                mortality_rate=mortality_rate
            )


def recalculate_statistics(db: MortalityDatabase):
    """Recalculate statistics for all hospitals."""
    hospitals = db.get_all_hospitals()
    
    for hospital in hospitals:
        monthly_data = db.get_monthly_data(hospital_name=hospital)
        
        if len(monthly_data) == 0:
            continue
        
        mortality_rates = monthly_data['mortality_rate'].values
        avg_mortality = mortality_rates.mean()
        std_deviation = mortality_rates.std()
        
        if pd.isna(std_deviation):
            std_deviation = 0.0
        
        threshold_3sd = avg_mortality + (3 * std_deviation)
        
        db.update_statistics(
            hospital_name=hospital,
            avg_mortality=avg_mortality,
            std_deviation=std_deviation,
            threshold_3sd=threshold_3sd
        )


def check_alerts(db: MortalityDatabase, check_date: date) -> list:
    """Check if any hospitals exceed the +3SD threshold."""
    alerts = []
    
    # Get statistics for all hospitals
    stats = db.get_statistics()
    
    # Get daily data for the check date
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT hospital_name, mortality_rate
        FROM daily_mortality
        WHERE date = ?
    """, (check_date.isoformat(),))
    
    daily_data = cursor.fetchall()
    conn.close()
    
    # Check each hospital
    for hospital_name, mortality_rate in daily_data:
        hospital_stats = stats[stats['hospital_name'] == hospital_name]
        
        if len(hospital_stats) > 0:
            threshold = hospital_stats.iloc[0]['threshold_3sd']
            
            if mortality_rate > threshold:
                alerts.append({
                    'hospital_name': hospital_name,
                    'date': check_date.isoformat(),
                    'mortality_rate': mortality_rate,
                    'threshold': threshold
                })
    
    return alerts


if __name__ == "__main__":
    import sqlite3
    
    # Allow specifying a date as command line argument (for testing)
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
            daily_update(target_date)
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        daily_update()

