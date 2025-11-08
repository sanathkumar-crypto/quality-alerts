#!/usr/bin/env python3
"""
Script to filter hospitals based on death count changes from September to October:
- Worsening: October deaths >= September deaths + 2
- Improvement: October deaths <= September deaths - 2
"""

import pandas as pd
from datetime import date
from database import MortalityDatabase


def get_hospitals_with_significant_death_change(year: int = 2025, threshold: int = 2):
    """
    Get list of hospitals where October deaths differ from September by at least threshold.
    
    Args:
        year: Year to analyze (2025)
        threshold: Minimum difference in number of deaths (default 2)
    
    Returns:
        Tuple of (worsened_df, improved_df) DataFrames
    """
    db = MortalityDatabase()
    
    # Query data for September and October
    start_date = date(year, 9, 1)  # September
    end_date = date(year, 10, 31)  # October
    
    df = db.get_monthly_data(start_date=start_date, end_date=end_date)
    df = df[(df['year'] == year) & (df['month'].isin([9, 10]))]
    
    # Hospitals to exclude from analysis
    excluded_hospitals = [
        'GSVM Kanpur', 
        'The Children\'s Hospital - Shillong', 
        'The Children\'s Hospital Shillong', 
        'Swaroop Rani Hospital - Prayagraj', 
        'Sai Children Hospital - Tohana',
        'Heritage Hospital - Gorakhpur',
        'SHRI Guntur',
        'MLB Jhansi',
        'SNMC Agra'
    ]
    
    # Filter out excluded hospitals
    df = df[~df['hospital_name'].isin(excluded_hospitals)]
    
    # Also exclude any hospital with "child" in the name (case-insensitive)
    df = df[~df['hospital_name'].str.contains('child', case=False, na=False)]
    
    # Get September and October data for each hospital
    worsened = []
    improved = []
    hospitals = df['hospital_name'].unique()
    
    for hospital in hospitals:
        hospital_data = df[df['hospital_name'] == hospital].copy()
        
        # Check if we have both September and October data
        months_present = set(hospital_data['month'].values)
        if not (9 in months_present and 10 in months_present):
            continue
        
        sept_data = hospital_data[hospital_data['month'] == 9].iloc[0]
        oct_data = hospital_data[hospital_data['month'] == 10].iloc[0]
        
        sept_rate = float(sept_data['mortality_rate'])
        oct_rate = float(oct_data['mortality_rate'])
        sept_deaths = int(sept_data['deaths'])
        oct_deaths = int(oct_data['deaths'])
        
        # Calculate death difference
        death_difference = oct_deaths - sept_deaths
        
        # Worsening: October deaths >= September deaths + threshold
        if death_difference >= threshold:
            worsened.append({
                'hospital_name': hospital,
                'september_rate': sept_rate,
                'september_deaths': sept_deaths,
                'october_rate': oct_rate,
                'october_deaths': oct_deaths,
                'death_difference': death_difference,
                'rate_difference': oct_rate - sept_rate
            })
        
        # Improvement: October deaths <= September deaths - threshold
        elif death_difference <= -threshold:
            improved.append({
                'hospital_name': hospital,
                'september_rate': sept_rate,
                'september_deaths': sept_deaths,
                'october_rate': oct_rate,
                'october_deaths': oct_deaths,
                'death_difference': death_difference,
                'rate_difference': oct_rate - sept_rate
            })
    
    # Convert to DataFrames and sort
    worsened_df = pd.DataFrame(worsened)
    improved_df = pd.DataFrame(improved)
    
    if len(worsened_df) > 0:
        worsened_df = worsened_df.sort_values('death_difference', ascending=False)
    if len(improved_df) > 0:
        improved_df = improved_df.sort_values('death_difference', ascending=True)  # Most negative first
    
    return worsened_df, improved_df


def main():
    """Main function to display filtered hospitals."""
    print("=" * 80)
    print("Hospitals with Significant Death Count Changes")
    print("September to October 2025")
    print("=" * 80)
    print()
    print("Criteria:")
    print("  - Worsening: October deaths >= September deaths + 2")
    print("  - Improvement: October deaths <= September deaths - 2")
    print()
    
    threshold = 2
    worsened_df, improved_df = get_hospitals_with_significant_death_change(year=2025, threshold=threshold)
    
    # Display worsened hospitals (top 5)
    print("=" * 80)
    print(f"TOP 5 HOSPITALS WITH WORSENED MORTALITY")
    print(f"(Total: {len(worsened_df)} hospitals meeting criteria)")
    print("=" * 80)
    print()
    
    if len(worsened_df) == 0:
        print("No hospitals found with worsened mortality (October deaths >= September + 2)")
    else:
        top_worsened = worsened_df.head(5)
        for i, (idx, row) in enumerate(top_worsened.iterrows(), 1):
            print(f"{i}. {row['hospital_name']}")
            print(f"   September: {row['september_rate']:.2f}% ({row['september_deaths']} deaths)")
            print(f"   October:   {row['october_rate']:.2f}% ({row['october_deaths']} deaths)")
            print(f"   Death change: +{row['death_difference']} deaths")
            print(f"   Rate change: {row['rate_difference']:+.2f} percentage points")
            print()
    
    print()
    print("=" * 80)
    print(f"TOP 5 HOSPITALS WITH IMPROVED MORTALITY")
    print(f"(Total: {len(improved_df)} hospitals meeting criteria)")
    print("=" * 80)
    print()
    
    if len(improved_df) == 0:
        print("No hospitals found with improved mortality (October deaths <= September - 2)")
    else:
        top_improved = improved_df.head(5)
        for i, (idx, row) in enumerate(top_improved.iterrows(), 1):
            print(f"{i}. {row['hospital_name']}")
            print(f"   September: {row['september_rate']:.2f}% ({row['september_deaths']} deaths)")
            print(f"   October:   {row['october_rate']:.2f}% ({row['october_deaths']} deaths)")
            print(f"   Death change: {row['death_difference']} deaths")
            print(f"   Rate change: {row['rate_difference']:+.2f} percentage points")
            print()
    
    print("=" * 80)
    print(f"SUMMARY")
    print("=" * 80)
    print(f"  Total hospitals with worsened mortality: {len(worsened_df)}")
    print(f"  Total hospitals with improved mortality: {len(improved_df)}")
    print(f"  Grand total: {len(worsened_df) + len(improved_df)} hospitals")
    print()
    
    if len(worsened_df) > 0:
        print("Worsened Statistics:")
        print(f"  Average death increase: {worsened_df['death_difference'].mean():.1f} deaths")
        print(f"  Maximum death increase: {worsened_df['death_difference'].max()} deaths")
        print(f"  Minimum death increase: {worsened_df['death_difference'].min()} deaths")
        print()
    
    if len(improved_df) > 0:
        print("Improved Statistics:")
        print(f"  Average death decrease: {abs(improved_df['death_difference'].mean()):.1f} deaths")
        print(f"  Maximum death decrease: {abs(improved_df['death_difference'].min())} deaths")
        print(f"  Minimum death decrease: {abs(improved_df['death_difference'].max())} deaths")


if __name__ == "__main__":
    main()

