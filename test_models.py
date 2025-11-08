"""
Test script to check why models aren't finding hospitals.
Focuses on 'Shree Narsinh Balod' hospital.
"""

import sys
from models import calculate_model_results
from database import MortalityDatabase
from datetime import date
import pandas as pd

def test_hospital(hospital_name):
    """Test a specific hospital across all models."""
    print(f"\n{'='*80}")
    print(f"Testing Hospital: {hospital_name}")
    print(f"{'='*80}\n")
    
    db = MortalityDatabase()
    
    # Get all monthly data for this hospital
    all_data = db.get_monthly_data(hospital_name=hospital_name)
    
    if len(all_data) == 0:
        print(f"❌ No data found for {hospital_name}")
        return
    
    print(f"📊 Total months of data: {len(all_data)}")
    print("\nRecent months (sorted by date, most recent first):")
    all_data_sorted = all_data.sort_values(['year', 'month'], ascending=False).copy()
    for idx, row in all_data_sorted.head(12).iterrows():
        print(f"  {int(row['year'])}-{int(row['month']):02d}: {int(row['deaths'])} deaths, {float(row['mortality_rate']):.2f}% mortality")
    
    # Get current month info
    today = date.today()
    current_year = today.year
    current_month = today.month
    current_period = f"{current_year}-{current_month:02d}"
    
    print(f"\n📅 Current period (today's month): {current_period}")
    
    # Check current month data
    current_month_data = all_data[
        (all_data['year'] == current_year) & 
        (all_data['month'] == current_month)
    ]
    
    if len(current_month_data) == 0:
        print(f"⚠️  No data for current month {current_period} - will use 0")
        current_deaths = 0
        current_mortality_rate = 0.0
    else:
        current_data = current_month_data.iloc[0]
        current_deaths = int(current_data['deaths'])
        current_mortality_rate = float(current_data['mortality_rate'])
        print(f"✅ Current month data: {current_deaths} deaths, {current_mortality_rate:.2f}% mortality")
    
    # Test each model
    models_to_test = [
        'model1', 'model2', 'model3', 'model4',
        'model5', 'model6', 'model7', 'model8',
        'model9', 'model10', 'model11', 'model12',
        'model13'
    ]
    
    print(f"\n{'='*80}")
    print("TESTING EACH MODEL:")
    print(f"{'='*80}\n")
    
    for model_id in models_to_test:
        print(f"\n🔍 {model_id.upper()}:")
        results = calculate_model_results(model_id)
        
        # Check if this hospital is in results
        hospital_in_results = [r for r in results if r['hospital_name'] == hospital_name]
        
        if hospital_in_results:
            result = hospital_in_results[0]
            print(f"  ✅ ALERT TRIGGERED for {hospital_name}")
            print(f"     Current Period: {result['current_period']}")
            print(f"     Deaths: {result['deaths']}")
            print(f"     Mortality Rate: {result['mortality_rate']:.2f}%")
            print(f"     Threshold: {result['threshold']}")
            if 'smr' in result and result['smr'] is not None:
                print(f"     SMR: {result['smr']:.2f}")
            if 'trend_info' in result:
                t = result['trend_info']
                print(f"     Trend: {t['month1']}: {t['rate1']:.2f}% → {t['month2']}: {t['rate2']:.2f}% → {t['month3']}: {t['rate3']:.2f}%")
        else:
            print(f"  ❌ No alert for {hospital_name}")
            print(f"     Total hospitals in results: {len(results)}")
            
            # Manual calculation to see why
            if model_id in ['model1', 'model2', 'model3', 'model4']:
                # Deaths models
                months_lookback = 3 if model_id in ['model1', 'model3'] else 6
                recent_data = all_data_sorted.iloc[1:months_lookback+1] if len(all_data_sorted) > 1 else pd.DataFrame()
                if len(recent_data) > 0:
                    if 'model1' in model_id or 'model2' in model_id:
                        threshold = int(recent_data['deaths'].max())
                        print(f"     Current deaths: {current_deaths}, Threshold (highest of last {months_lookback}mo): {threshold}")
                        print(f"     Recent months deaths: {recent_data['deaths'].tolist()}")
                    else:
                        threshold = recent_data['deaths'].mean() + recent_data['deaths'].std()
                        print(f"     Current deaths: {current_deaths}, Threshold (avg+1SD of last {months_lookback}mo): {threshold:.2f}")
                        print(f"     Recent months deaths: {recent_data['deaths'].tolist()}")
                        print(f"     Avg: {recent_data['deaths'].mean():.2f}, Std: {recent_data['deaths'].std():.2f}")
            
            elif model_id in ['model9', 'model10', 'model11', 'model12']:
                # Percentage models
                months_lookback = 3 if model_id in ['model9', 'model11'] else 6
                # Need to exclude current month
                recent_data = all_data_sorted[
                    ~((all_data_sorted['year'] == current_year) & (all_data_sorted['month'] == current_month))
                ].iloc[:months_lookback]
                if len(recent_data) > 0:
                    if 'model9' in model_id or 'model10' in model_id:
                        threshold = float(recent_data['mortality_rate'].max())
                        print(f"     Current mortality rate: {current_mortality_rate:.2f}%, Threshold (highest of last {months_lookback}mo): {threshold:.2f}%")
                    else:
                        threshold = recent_data['mortality_rate'].mean() + recent_data['mortality_rate'].std()
                        print(f"     Current mortality rate: {current_mortality_rate:.2f}%, Threshold (avg+1SD of last {months_lookback}mo): {threshold:.2f}%")
                        print(f"     Recent months rates: {recent_data['mortality_rate'].tolist()}")
                        print(f"     Avg: {recent_data['mortality_rate'].mean():.2f}%, Std: {recent_data['mortality_rate'].std():.2f}%")


if __name__ == '__main__':
    hospital_name = "Shree Narsinh - Balod"
    if len(sys.argv) > 1:
        hospital_name = sys.argv[1]
    
    test_hospital(hospital_name)

