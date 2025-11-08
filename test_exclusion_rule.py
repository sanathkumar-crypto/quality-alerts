#!/usr/bin/env python3
"""
Test script to verify the exclusion rule for hospitals with death difference <= 2.
Tests specifically with RN Pandey hospital which has 2 deaths in current month.
"""

import sys
from datetime import date
from database import MortalityDatabase
from models import calculate_model_results, get_previous_month_deaths
import pandas as pd

def test_exclusion_rule():
    """Test the exclusion rule for RN Pandey hospital and find hospitals that should be excluded."""
    
    print("=" * 80)
    print("TEST: Exclusion Rule for Hospitals with Death Difference <= 2")
    print("=" * 80)
    print()
    
    hospital_name = "RN Pandey - Gonda"
    model_id = "model10"  # Model 10: Mortality % > Highest (Last 6 months)
    
    print(f"Step 1: Testing hospital: {hospital_name}")
    print(f"Step 2: Testing model: {model_id}")
    print()
    
    # Get database instance
    print("Step 3: Connecting to database...")
    db = MortalityDatabase()
    
    # Get all monthly data for this hospital
    print(f"Step 4: Fetching monthly data for '{hospital_name}'...")
    all_data = db.get_monthly_data(hospital_name=hospital_name)
    
    if len(all_data) == 0:
        print(f"ERROR: No data found for hospital '{hospital_name}'")
        print("Please ensure the hospital exists in the database.")
        return False
    
    print(f"✓ Found {len(all_data)} months of data")
    print()
    
    # Get current month info
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    print(f"Step 5: Current period: {current_year}-{current_month:02d}")
    print()
    
    # Get current month data
    print("Step 6: Checking current month data...")
    current_month_data = all_data[
        (all_data['year'] == current_year) & 
        (all_data['month'] == current_month)
    ]
    
    if len(current_month_data) == 0:
        print(f"WARNING: No data for current month {current_year}-{current_month:02d}")
        print("Trying to get most recent month...")
        all_data_sorted = all_data.sort_values(['year', 'month'], ascending=False)
        if len(all_data_sorted) > 0:
            current_month_data = all_data_sorted.iloc[[0]]
            current_year = int(current_month_data.iloc[0]['year'])
            current_month = int(current_month_data.iloc[0]['month'])
            print(f"Using most recent month: {current_year}-{current_month:02d}")
    
    if len(current_month_data) == 0:
        print("ERROR: No data available for this hospital")
        return False
    
    current_deaths = int(current_month_data.iloc[0]['deaths'])
    current_mortality_rate = float(current_month_data.iloc[0]['mortality_rate'])
    
    print(f"✓ Current month ({current_year}-{current_month:02d}):")
    print(f"  - Deaths: {current_deaths} (NUMBER OF DEATHS, not percentage)")
    print(f"  - Mortality Rate: {current_mortality_rate:.2f}%")
    print()
    
    # Get previous month deaths
    print("Step 7: Getting previous month deaths...")
    prev_month_deaths = get_previous_month_deaths(all_data, current_year, current_month)
    
    if prev_month_deaths is None:
        print("⚠ WARNING: Previous month data not available")
        print("  Cannot apply exclusion rule without previous month data")
        print()
        print("Checking available months in database:")
        months_list = all_data[['year', 'month']].drop_duplicates().sort_values(['year', 'month'], ascending=False)
        print(months_list.to_string())
        print()
        print("The exclusion rule requires previous month data to calculate the difference.")
        print("If previous month data is missing, the hospital will NOT be excluded.")
        return False
    else:
        print(f"✓ Previous month deaths: {prev_month_deaths} (NUMBER OF DEATHS, not percentage)")
        print()
    
    # Calculate increase (current - previous)
    print("Step 8: Calculating increase in deaths (current - previous)...")
    increase = current_deaths - prev_month_deaths
    print(f"  Current deaths: {current_deaths}")
    print(f"  Previous month deaths: {prev_month_deaths}")
    print(f"  Increase: {current_deaths} - {prev_month_deaths} = {increase}")
    print(f"  NOTE: We are using NUMBER OF DEATHS, not percentage!")
    print()
    
    # Check if should be excluded
    print("Step 9: Checking exclusion rule...")
    print(f"  Rule: Exclude if current month is NOT higher than previous month by MORE than 2")
    print(f"  In other words: Exclude if (current - previous) <= 2")
    print(f"  Actual increase: {increase}")
    should_be_excluded = increase <= 2
    print(f"  Should be excluded: {should_be_excluded} (because {increase} <= 2)")
    print()
    
    # Note about RN Pandey
    print("Step 10: Analysis for RN Pandey...")
    print(f"  Current deaths: {current_deaths}")
    print(f"  Previous month deaths: {prev_month_deaths}")
    print(f"  Increase: {increase}")
    if current_deaths == 2:
        print(f"  Since current_deaths = 2:")
        print(f"  - If previous = 0, increase = 2 (<= 2) → EXCLUDE")
        print(f"  - If previous = 13, increase = -11 (<= 2) → EXCLUDE")
        print(f"  - If previous = -1 (impossible), increase = 3 (> 2) → DON'T EXCLUDE")
        print(f"  Current previous month deaths: {prev_month_deaths}")
        if increase <= 2:
            print(f"  ✓ Increase ({increase}) is <= 2, so hospital should be EXCLUDED")
        else:
            print(f"  ⚠ Increase ({increase}) is > 2, so hospital should NOT be excluded")
    print()
    
    # Now test the actual model calculation
    print("Step 11: Testing actual model calculation...")
    print(f"  Running calculate_model_results('{model_id}')...")
    print("  (This may take a moment...)")
    print()
    
    results = calculate_model_results(model_id)
    
    # Check if hospital is in results
    print("Step 12: Checking if hospital appears in model results...")
    hospital_in_results = False
    for result in results:
        if result['hospital_name'] == hospital_name:
            hospital_in_results = True
            print(f"  ⚠ FOUND in results:")
            print(f"    - Hospital: {result['hospital_name']}")
            print(f"    - Current Period: {result['current_period']}")
            print(f"    - Deaths: {result['deaths']} (NUMBER OF DEATHS)")
            print(f"    - Mortality Rate: {result['mortality_rate']:.2f}%")
            break
    
    if not hospital_in_results:
        print(f"  ✓ Hospital NOT found in results")
    print()
    
    # Final analysis
    print("Step 13: Final analysis...")
    print(f"  Current deaths: {current_deaths}")
    print(f"  Previous month deaths: {prev_month_deaths}")
    print(f"  Increase: {increase} (current - previous)")
    print(f"  Should be excluded (increase <= 2): {should_be_excluded}")
    print(f"  Actually in results: {hospital_in_results}")
    print()
    
    if should_be_excluded:
        if hospital_in_results:
            print(f"  ❌ PROBLEM: Hospital should be excluded but appears in results!")
            print(f"     Current deaths: {current_deaths}")
            print(f"     Previous month deaths: {prev_month_deaths}")
            print(f"     Increase: {increase} (<= 2)")
            print(f"     Expected: Hospital should NOT appear in results")
            print(f"     Actual: Hospital appears in results")
            print(f"     This indicates the exclusion rule is NOT working correctly.")
            return False
        else:
            print(f"  ✓ CORRECT: Hospital correctly excluded from results")
            print(f"     Current deaths: {current_deaths}")
            print(f"     Previous month deaths: {prev_month_deaths}")
            print(f"     Increase: {increase} (<= 2)")
            print(f"     Result: Hospital NOT in results (correctly excluded)")
    else:
        if hospital_in_results:
            print(f"  ✓ CORRECT: Hospital should NOT be excluded (increase > 2), and it appears in results")
            print(f"     Current deaths: {current_deaths}")
            print(f"     Previous month deaths: {prev_month_deaths}")
            print(f"     Increase: {increase} (> 2)")
        else:
            print(f"  ⚠ NOTE: Hospital increase > 2, so exclusion not applicable")
            print(f"     Hospital not in results for other reasons (threshold not crossed, etc.)")
    
    print()
    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)
    
    return True

def test_multiple_scenarios():
    """Test multiple scenarios to verify the exclusion logic."""
    
    print()
    print("=" * 80)
    print("ADDITIONAL TEST: Multiple Scenarios")
    print("=" * 80)
    print()
    
    scenarios = [
        {"current": 2, "previous": 0, "should_exclude": True, "desc": "2 - 0 = 2 (<= 2, should exclude)"},
        {"current": 2, "previous": 1, "should_exclude": True, "desc": "2 - 1 = 1 (<= 2, should exclude)"},
        {"current": 2, "previous": 2, "should_exclude": True, "desc": "2 - 2 = 0 (<= 2, should exclude)"},
        {"current": 2, "previous": 13, "should_exclude": True, "desc": "2 - 13 = -11 (<= 2, should exclude)"},
        {"current": 2, "previous": 4, "should_exclude": True, "desc": "2 - 4 = -2 (<= 2, should exclude)"},
        {"current": 5, "previous": 2, "should_exclude": False, "desc": "5 - 2 = 3 (> 2, should NOT exclude)"},
        {"current": 1, "previous": 0, "should_exclude": True, "desc": "1 - 0 = 1 (<= 2, should exclude)"},
        {"current": 3, "previous": 1, "should_exclude": True, "desc": "3 - 1 = 2 (<= 2, should exclude)"},
        {"current": 3, "previous": 0, "should_exclude": False, "desc": "3 - 0 = 3 (> 2, should NOT exclude)"},
        {"current": 4, "previous": 1, "should_exclude": False, "desc": "4 - 1 = 3 (> 2, should NOT exclude)"},
    ]
    
    print("Testing exclusion logic with various death counts:")
    print("Rule: Exclude if (current - previous) <= 2")
    print()
    
    all_passed = True
    for i, scenario in enumerate(scenarios, 1):
        current = scenario["current"]
        previous = scenario["previous"]
        expected = scenario["should_exclude"]
        desc = scenario["desc"]
        
        increase = current - previous
        actual = increase <= 2
        
        status = "✓" if actual == expected else "❌"
        if actual != expected:
            all_passed = False
        
        print(f"{i}. {desc}")
        print(f"   Current: {current}, Previous: {previous}, Increase: {increase}")
        print(f"   Expected exclude: {expected}, Actual exclude: {actual} {status}")
        print()
    
    if all_passed:
        print("✓ All scenario tests PASSED")
    else:
        print("❌ Some scenario tests FAILED")
    
    return all_passed

def find_hospitals_to_exclude():
    """Find hospitals that should be excluded based on the rule."""
    
    print()
    print("=" * 80)
    print("FINDING HOSPITALS THAT SHOULD BE EXCLUDED")
    print("=" * 80)
    print()
    
    db = MortalityDatabase()
    hospitals = db.get_all_hospitals()
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    print(f"Checking all hospitals for current month {current_year}-{current_month:02d}...")
    print()
    
    hospitals_to_exclude = []
    hospitals_not_excluded = []
    
    for hospital in hospitals[:50]:  # Check first 50 to avoid taking too long
        try:
            all_data = db.get_monthly_data(hospital_name=hospital)
            if len(all_data) == 0:
                continue
            
            current_month_data = all_data[
                (all_data['year'] == current_year) & 
                (all_data['month'] == current_month)
            ]
            
            if len(current_month_data) == 0:
                continue
            
            current_deaths = int(current_month_data.iloc[0]['deaths'])
            prev_month_deaths = get_previous_month_deaths(all_data, current_year, current_month)
            
            if prev_month_deaths is not None:
                increase = current_deaths - prev_month_deaths
                if increase <= 2:
                    hospitals_to_exclude.append({
                        'hospital': hospital,
                        'current_deaths': current_deaths,
                        'prev_deaths': prev_month_deaths,
                        'increase': increase
                    })
                else:
                    hospitals_not_excluded.append({
                        'hospital': hospital,
                        'current_deaths': current_deaths,
                        'prev_deaths': prev_month_deaths,
                        'increase': increase
                    })
        except Exception as e:
            continue
    
    print(f"Found {len(hospitals_to_exclude)} hospitals that SHOULD be excluded (increase <= 2):")
    print()
    for h in hospitals_to_exclude:
        print(f"  - {h['hospital']}: current={h['current_deaths']}, previous={h['prev_deaths']}, increase={h['increase']}")
    
    print()
    print(f"Found {len(hospitals_not_excluded)} hospitals that should NOT be excluded (increase > 2):")
    print("(Showing first 5)")
    for h in hospitals_not_excluded[:5]:
        print(f"  - {h['hospital']}: current={h['current_deaths']}, previous={h['prev_deaths']}, increase={h['increase']}")
    
    return hospitals_to_exclude

if __name__ == "__main__":
    print()
    print("Starting exclusion rule test...")
    print()
    
    try:
        # Test the actual hospital
        test_passed = test_exclusion_rule()
        
        # Find hospitals that should be excluded
        hospitals_to_exclude = find_hospitals_to_exclude()
        
        # Test multiple scenarios
        scenarios_passed = test_multiple_scenarios()
        
        print()
        if test_passed and scenarios_passed:
            print("=" * 80)
            print("✓ ALL TESTS PASSED")
            print("=" * 80)
            if len(hospitals_to_exclude) > 0:
                print(f"\nFound {len(hospitals_to_exclude)} hospitals that should be excluded.")
                print("These hospitals should NOT appear in model results.")
            sys.exit(0)
        else:
            print("=" * 80)
            print("❌ SOME TESTS FAILED")
            print("=" * 80)
            sys.exit(1)
            
    except AssertionError as e:
        print()
        print("=" * 80)
        print(f"❌ ASSERTION ERROR: {e}")
        print("=" * 80)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        sys.exit(1)

