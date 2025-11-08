"""
Alert Models Module
Implements 12 different alert models for detecting hospitals that exceed thresholds.
"""

import pandas as pd
import time
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from database import MortalityDatabase
from bigquery_queries import get_bigquery_client, query_current_month_mortality, query_current_month_mortality_all_hospitals
from config import BIGQUERY_PROJECT_ID, BIGQUERY_DATASET, BIGQUERY_TABLE
from google.cloud import bigquery


def get_expected_death_percentage(hospital_name: str) -> Optional[float]:
    """Get expected death percentage from BigQuery for a hospital."""
    try:
        client = get_bigquery_client()
        query = f"""
        SELECT DISTINCT expected_death_percentage
        FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
        WHERE hospital_name = @hospital_name
        AND expected_death_percentage IS NOT NULL
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("hospital_name", "STRING", hospital_name)
            ]
        )
        
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        for row in results:
            return float(row.expected_death_percentage)
        
        return None
    except Exception as e:
        print(f"Error fetching expected_death_percentage for {hospital_name}: {e}")
        return None


def calculate_smr(monthly_data: pd.DataFrame, expected_pct: float) -> pd.DataFrame:
    """Calculate Standardized Mortality Ratio (SMR) for monthly data.
    SMR = (Mortality Rate / Expected Death Percentage) for each month.
    """
    df = monthly_data.copy()
    if expected_pct and expected_pct > 0:
        df['smr'] = df['mortality_rate'] / expected_pct
    else:
        df['smr'] = None
    return df


def get_recent_months_data(monthly_data: pd.DataFrame, months: int, exclude_year: int = None, exclude_month: int = None) -> pd.DataFrame:
    """Get data for the most recent N months (excluding specified current month)."""
    if len(monthly_data) == 0:
        return monthly_data
    
    # Exclude current month if specified
    df = monthly_data.copy()
    if exclude_year is not None and exclude_month is not None:
        df = df[~((df['year'] == exclude_year) & (df['month'] == exclude_month))]
    
    if len(df) == 0:
        return pd.DataFrame()
    
    # Sort by year and month descending
    df = df.sort_values(['year', 'month'], ascending=False).copy()
    
    # Get unique (year, month) combinations and take N most recent
    unique_periods = df[['year', 'month']].drop_duplicates().iloc[:months]
    
    if len(unique_periods) == 0:
        return pd.DataFrame()
    
    # Create a set of tuples for faster lookup
    period_set = set(zip(unique_periods['year'], unique_periods['month']))
    
    # Filter data to only include these periods
    mask = df.apply(lambda row: (int(row['year']), int(row['month'])) in period_set, axis=1)
    
    return df[mask].copy()


def get_last_6_months_mortality(monthly_data: pd.DataFrame, current_year: int, current_month: int) -> List[Dict[str, float]]:
    """Get mortality rates for the last 6 months (including current month), with 0 for missing months."""
    from calendar import monthrange
    
    result = []
    
    # Generate list of last 6 months (including current)
    months_list = []
    year = current_year
    month = current_month
    
    for _ in range(6):
        months_list.append((year, month))
        # Go back one month
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    
    # Create a lookup dictionary from the data
    data_dict = {}
    for _, row in monthly_data.iterrows():
        key = (int(row['year']), int(row['month']))
        data_dict[key] = float(row.get('mortality_rate', 0.0))
    
    # Build result with mortality rates (0 for missing months)
    # Reverse to show oldest to newest (most intuitive for users)
    for year, month in reversed(months_list):
        period = f"{year}-{month:02d}"
        mortality_rate = data_dict.get((year, month), 0.0)
        result.append({
            'period': period,
            'mortality_rate': mortality_rate
        })
    
    return result


def get_all_expected_death_percentages(hospital_names: List[str]) -> Dict[str, float]:
    """Get expected death percentages for all hospitals in a single BigQuery query."""
    if not hospital_names:
        return {}
    
    try:
        client = get_bigquery_client()
        
        # Use UNNEST with array parameter for better performance
        # BigQuery can handle large arrays efficiently
        batch_size = 5000  # BigQuery can handle large arrays
        result_dict = {}
        
        for i in range(0, len(hospital_names), batch_size):
            batch = hospital_names[i:i+batch_size]
            
            # Use ARRAY type parameter with UNNEST
            query = f"""
            SELECT DISTINCT hospital_name, expected_death_percentage
            FROM `{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}`
            WHERE hospital_name IN UNNEST(@hospital_names)
            AND expected_death_percentage IS NOT NULL
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ArrayQueryParameter("hospital_names", "STRING", batch)
                ]
            )
            
            query_job = client.query(query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
                if row.hospital_name not in result_dict:
                    result_dict[row.hospital_name] = float(row.expected_death_percentage)
        
        return result_dict
    except Exception as e:
        print(f"Error fetching expected_death_percentages: {e}")
        import traceback
        traceback.print_exc()
        return {}


def get_previous_month_deaths(all_data: pd.DataFrame, current_year: int, current_month: int) -> Optional[int]:
    """Get the number of deaths for the previous month."""
    # Calculate previous month
    prev_month = current_month - 1
    prev_year = current_year
    if prev_month < 1:
        prev_month = 12
        prev_year = current_year - 1
    
    # Try to get from database
    prev_month_data = all_data[
        (all_data['year'] == prev_year) & 
        (all_data['month'] == prev_month)
    ]
    
    if len(prev_month_data) > 0:
        return int(prev_month_data.iloc[0]['deaths'])
    
    # If not in database, return None (we don't have previous month data)
    return None


def calculate_model_results(model_id: str, apply_death_increase_filter: bool = False) -> List[Dict]:
    """
    Calculate alert results for a specific model.
    
    Args:
        model_id: Model ID to calculate (e.g., 'model10')
        apply_death_increase_filter: If True, only include hospitals where current month deaths
            is at least 2 higher than previous month. This filter is typically used for
            Google Chat alerts to reduce noise, but not for dashboard display.
    
    Models:
    1-4: Deaths-based (3mo/6mo highest, 3mo/6mo avg+1SD)
    5-8: SMR-based (using expected_death_percentage)
    9-12: Percentage-based (mortality rate %)
    13: Mortality rate increasing for 3 consecutive months (including current month)
    """
    start_time = time.time()
    db = MortalityDatabase()
    hospitals = db.get_all_hospitals()
    
    results = []
    today = date.today()
    current_month = today.month
    current_year = today.year
    
    # Determine if we use 3 or 6 months lookback
    months_lookback = 3 if model_id in ['model1', 'model3', 'model5', 'model7', 'model9', 'model11'] else 6
    
    # Check if this is Model 13 (increasing trend)
    is_increasing_trend = model_id == 'model13'
    
    # Determine metric type (only for models 1-12)
    is_deaths = not is_increasing_trend and model_id.startswith('model') and int(model_id.replace('model', '')) <= 4
    is_smr = not is_increasing_trend and model_id.startswith('model') and 5 <= int(model_id.replace('model', '')) <= 8
    is_percentage = not is_increasing_trend and model_id.startswith('model') and int(model_id.replace('model', '')) >= 9
    
    # Determine threshold type
    use_highest = model_id in ['model1', 'model2', 'model5', 'model6', 'model9', 'model10']
    use_avg_1sd = model_id in ['model3', 'model4', 'model7', 'model8', 'model11', 'model12']
    
    # For SMR models, fetch all expected_death_percentages in a single query
    expected_death_pct_dict = {}
    if is_smr:
        print(f"Fetching expected_death_percentages for {len(hospitals)} hospitals...")
        expected_death_pct_dict = get_all_expected_death_percentages(hospitals)
        print(f"Found expected_death_percentages for {len(expected_death_pct_dict)} hospitals")
    
    # Query current month data for all hospitals at once (if not in database)
    # This is much faster than querying individually
    current_month_live_data = {}
    print(f"[Models] Checking database for current month {current_year}-{current_month:02d}...")
    current_month_data_check = db.get_monthly_data(
        start_date=date(current_year, current_month, 1),
        end_date=date(current_year, current_month, 28)  # Approximate end of month
    )
    has_current_month_in_db = len(current_month_data_check) > 0
    print(f"[Models] Database check: {len(current_month_data_check)} rows found for {current_year}-{current_month:02d}")
    if len(current_month_data_check) > 0:
        print(f"[Models] Sample database data:")
        print(current_month_data_check.head().to_string())
    
    if not has_current_month_in_db:
        print(f"[Models] Current month {current_year}-{current_month:02d} NOT in database, querying BigQuery for all hospitals...")
        try:
            live_df = query_current_month_mortality_all_hospitals(year=current_year, month=current_month)
            print(f"[Models] BigQuery returned {len(live_df)} rows")
            for _, row in live_df.iterrows():
                current_month_live_data[row['hospital_name']] = {
                    'deaths': int(row['deaths']),
                    'mortality_rate': float(row['mortality_rate']),
                    'total_patients': int(row['total_patients'])
                }
            print(f"[Models] Cached live data for {len(current_month_live_data)} hospitals")
            if len(current_month_live_data) > 0:
                sample_hospital = list(current_month_live_data.keys())[0]
                print(f"[Models] Sample live data for '{sample_hospital}': {current_month_live_data[sample_hospital]}")
        except Exception as e:
            print(f"[Models] ERROR querying BigQuery for current month: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[Models] Current month {current_year}-{current_month:02d} found in database, skipping BigQuery query")
    
    total_hospitals = len(hospitals)
    print(f"[Models] Processing {total_hospitals} hospitals for {model_id}...")
    
    for idx, hospital in enumerate(hospitals, 1):
        # Log progress every 50 hospitals
        if idx % 50 == 0 or idx == total_hospitals:
            print(f"[Models] Progress: {idx}/{total_hospitals} hospitals processed ({idx*100//total_hospitals}%)")
        
        try:
            # Get all monthly data for this hospital
            all_data = db.get_monthly_data(hospital_name=hospital)
            
            if len(all_data) == 0:
                continue
            
            # Use today's date for current period (not the most recent data)
            today = date.today()
            current_year = today.year
            current_month = today.month
            current_period = f"{current_year}-{current_month:02d}"
            
            # Sort by date descending for threshold calculation
            all_data_sorted = all_data.sort_values(['year', 'month'], ascending=False).copy()
            
            # Get current month data from database (for today's month)
            current_month_data = all_data[
                (all_data['year'] == current_year) & 
                (all_data['month'] == current_month)
            ]
            
            # Only log detailed info for first few hospitals or on errors
            if idx <= 3:
                print(f"[Models] Hospital '{hospital}': Checking for {current_year}-{current_month:02d} data...")
                print(f"[Models] Hospital '{hospital}': Database has {len(current_month_data)} rows for current month")
                print(f"[Models] Hospital '{hospital}': Live data cache has {hospital in current_month_live_data}")
            
            # If no data for current month in database, use live query data (or show 0)
            if len(current_month_data) == 0:
                # Check if we have live data from batch query
                if hospital in current_month_live_data:
                    live_data = current_month_live_data[hospital]
                    current_deaths = live_data['deaths']
                    current_mortality_rate = live_data['mortality_rate']
                    if idx <= 3:
                        print(f"[Models] Hospital '{hospital}': Using LIVE data - {current_deaths} deaths, {current_mortality_rate:.2f}%")
                else:
                    # No data for current month - show as 0 (don't fall back to previous month)
                    current_deaths = 0
                    current_mortality_rate = 0.0
                    if idx <= 3:
                        print(f"[Models] Hospital '{hospital}': NO DATA (not in DB, not in live cache) - using 0")
            else:
                current_data = current_month_data.iloc[0]
                current_deaths = int(current_data['deaths'])
                current_mortality_rate = float(current_data['mortality_rate'])
                if idx <= 3:
                    print(f"[Models] Hospital '{hospital}': Using DATABASE data - {current_deaths} deaths, {current_mortality_rate:.2f}%")
            
            # Model 13: Check for increasing trend (3 consecutive months including current)
            if is_increasing_trend:
                # Get mortality rates for current month, previous month, and month before that
                def get_mortality_for_month(year, month):
                    # Check if this is the current month
                    if year == current_year and month == current_month:
                        # Check database first
                        month_data = all_data[
                            (all_data['year'] == year) & 
                            (all_data['month'] == month)
                        ]
                        if len(month_data) > 0:
                            return float(month_data.iloc[0]['mortality_rate'])
                        # Then check live data
                        elif hospital in current_month_live_data:
                            return current_month_live_data[hospital]['mortality_rate']
                        # No data = 0
                        return 0.0
                    else:
                        # For past months, use database
                        month_data = all_data[
                            (all_data['year'] == year) & 
                            (all_data['month'] == month)
                        ]
                        if len(month_data) > 0:
                            return float(month_data.iloc[0]['mortality_rate'])
                        # No data = 0
                        return 0.0
                
                # Calculate previous months
                prev_month = current_month - 1
                prev_year = current_year
                if prev_month < 1:
                    prev_month = 12
                    prev_year = current_year - 1
                
                prev_prev_month = prev_month - 1
                prev_prev_year = prev_year
                if prev_prev_month < 1:
                    prev_prev_month = 12
                    prev_prev_year = prev_year - 1
                
                # Get mortality rates for the 3 months
                rate_current = get_mortality_for_month(current_year, current_month)
                rate_prev = get_mortality_for_month(prev_year, prev_month)
                rate_prev_prev = get_mortality_for_month(prev_prev_year, prev_prev_month)
                
                # Check if all 3 months have data and show increasing trend
                if (rate_current is not None and rate_prev is not None and rate_prev_prev is not None and
                    rate_current > rate_prev > rate_prev_prev):
                    # EXCLUSION RULE: Only apply if apply_death_increase_filter is True
                    # Exclude hospitals where current month deaths is NOT higher than 
                    # previous month by more than 2. In other words, exclude if (current - previous) <= 2
                    # This means: exclude if current <= previous + 2
                    if apply_death_increase_filter:
                        prev_month_deaths = get_previous_month_deaths(all_data, current_year, current_month)
                        if prev_month_deaths is not None:
                            increase = current_deaths - prev_month_deaths
                            if increase <= 2:
                                print(f"[Models] Hospital '{hospital}': EXCLUDING from alert - current month deaths ({current_deaths}) is not higher than previous month ({prev_month_deaths}) by more than 2 (increase: {increase})")
                                continue  # Skip adding this hospital to alerts
                        else:
                            # Log when previous month data is not available (for debugging)
                            if idx <= 10:  # Only log for first 10 hospitals to avoid spam
                                print(f"[Models] Hospital '{hospital}': Previous month data not available, cannot apply exclusion rule (current deaths: {current_deaths})")
                    
                    # Get last 6 months mortality data
                    last_6_months = get_last_6_months_mortality(all_data, current_year, current_month)
                    
                    result = {
                        'hospital_name': hospital,
                        'current_period': current_period,
                        'deaths': current_deaths,
                        'mortality_rate': current_mortality_rate,
                        'smr': None,
                        'threshold': rate_prev_prev,  # Show the starting rate
                        'status': 'Alert',
                        'last_6_months_mortality': last_6_months,
                        'trend_info': {
                            'month1': f"{prev_prev_year}-{prev_prev_month:02d}",
                            'month2': f"{prev_year}-{prev_month:02d}",
                            'month3': current_period,
                            'rate1': rate_prev_prev,
                            'rate2': rate_prev,
                            'rate3': rate_current
                        }
                    }
                    results.append(result)
                    continue  # Skip the rest of the processing for this hospital
            
            # Get recent months for threshold calculation
            # Determine which month we're actually comparing (current if exists, otherwise previous)
            # Calculate previous month for exclusion rule and threshold calculation
            prev_month = current_month - 1
            prev_year = current_year
            if prev_month < 1:
                prev_month = 12
                prev_year = current_year - 1
            
            if len(current_month_data) > 0:
                # We're comparing current month, exclude it from threshold calculation
                exclude_year = current_year
                exclude_month = current_month
            else:
                # We're comparing previous month, exclude previous month from threshold calculation
                # (so threshold is based on months before the previous month)
                exclude_year = prev_year
                exclude_month = prev_month
            
            recent_data = get_recent_months_data(all_data_sorted, months_lookback, exclude_year, exclude_month)
            
            if len(recent_data) == 0:
                continue
            
            # Calculate SMR if needed
            smr_value = None
            recent_smr = None
            if is_smr:
                # Use cached expected_death_percentage from batch query
                expected_pct = expected_death_pct_dict.get(hospital)
                if expected_pct and expected_pct > 0:
                    # Calculate SMR for current month
                    smr_value = current_mortality_rate / expected_pct
                    # Calculate SMR for recent months too
                    recent_smr_df = calculate_smr(recent_data.copy(), expected_pct)
                    if 'smr' in recent_smr_df.columns:
                        recent_smr = recent_smr_df
                else:
                    continue  # Skip if no expected_death_percentage
            
            # Calculate threshold based on model type
            threshold = None
            threshold_value = None
            
            if is_deaths:
                if use_highest:
                    threshold = int(recent_data['deaths'].max())
                    threshold_value = current_deaths
                elif use_avg_1sd:
                    deaths_avg = recent_data['deaths'].mean()
                    deaths_std = recent_data['deaths'].std()
                    if pd.isna(deaths_std):
                        deaths_std = 0.0
                    threshold = deaths_avg + (1 * deaths_std)
                    threshold_value = current_deaths
                else:
                    continue
            
            elif is_smr:
                if recent_smr is None or 'smr' not in recent_smr.columns:
                    continue
                
                smr_data = recent_smr['smr'].dropna()
                if len(smr_data) == 0:
                    continue
                
                if use_highest:
                    threshold = float(smr_data.max())
                    threshold_value = smr_value
                elif use_avg_1sd:
                    smr_avg = float(smr_data.mean())
                    smr_std = float(smr_data.std())
                    if pd.isna(smr_std):
                        smr_std = 0.0
                    threshold = smr_avg + (1 * smr_std)
                    threshold_value = smr_value
                else:
                    continue
                
                if smr_value is None:
                    continue
            
            elif is_percentage:
                if use_highest:
                    threshold = float(recent_data['mortality_rate'].max())
                    threshold_value = current_mortality_rate
                elif use_avg_1sd:
                    rate_avg = recent_data['mortality_rate'].mean()
                    rate_std = recent_data['mortality_rate'].std()
                    if pd.isna(rate_std):
                        rate_std = 0.0
                    threshold = rate_avg + (1 * rate_std)
                    threshold_value = current_mortality_rate
                else:
                    continue
            
            # Check if threshold is crossed
            if threshold is not None and threshold_value is not None:
                if threshold_value > threshold:
                    # For SMR models, ensure smr_value is valid
                    if is_smr and (smr_value is None or pd.isna(smr_value)):
                        continue
                    
                    # EXCLUSION RULE: Only apply if apply_death_increase_filter is True
                    # Exclude hospitals where current month deaths is NOT higher than 
                    # previous month by more than 2. In other words, exclude if (current - previous) <= 2
                    # This means: exclude if current <= previous + 2
                    # This applies to all models (1-12) to filter out minor fluctuations
                    # NOTE: This filter is typically used for Google Chat alerts, not for dashboard display
                    if apply_death_increase_filter:
                        prev_month_deaths = get_previous_month_deaths(all_data, current_year, current_month)
                        if prev_month_deaths is not None:
                            increase = current_deaths - prev_month_deaths
                            if increase <= 2:
                                print(f"[Models] Hospital '{hospital}': EXCLUDING from alert - current month deaths ({current_deaths}) is not higher than previous month ({prev_month_deaths}) by more than 2 (increase: {increase})")
                                continue  # Skip adding this hospital to alerts
                        else:
                            # Log when previous month data is not available (for debugging)
                            if idx <= 10:  # Only log for first 10 hospitals to avoid spam
                                print(f"[Models] Hospital '{hospital}': Previous month data not available, cannot apply exclusion rule (current deaths: {current_deaths})")
                    
                    # Get last 6 months mortality data
                    # Include current month live data if we queried it
                    last_6_months = get_last_6_months_mortality(all_data, current_year, current_month)
                    
                    # If current month data was queried live or is 0, update the last_6_months with it
                    if len(last_6_months) > 0:
                        # Update the last item (current month) with live data or 0
                        last_6_months[-1]['mortality_rate'] = current_mortality_rate
                    
                    result = {
                        'hospital_name': hospital,
                        'current_period': current_period,
                        'deaths': current_deaths,
                        'mortality_rate': current_mortality_rate,
                        'threshold': float(threshold),
                        'status': 'Alert',
                        'last_6_months_mortality': last_6_months
                    }
                    # Only add smr if this is an SMR model
                    if is_smr:
                        result['smr'] = float(smr_value) if smr_value is not None and not pd.isna(smr_value) else None
                    
                    results.append(result)
        
        except Exception as e:
            print(f"Error processing hospital {hospital} for model {model_id}: {e}")
            continue
    
    # Sort by threshold value (highest alerts first)
    if results:
        if is_increasing_trend:
            # Sort by current mortality rate (highest first)
            results.sort(key=lambda x: x.get('mortality_rate', 0), reverse=True)
        elif is_smr:
            results.sort(key=lambda x: x.get('smr', 0), reverse=True)
        elif is_percentage:
            results.sort(key=lambda x: x.get('mortality_rate', 0), reverse=True)
        else:
            results.sort(key=lambda x: x.get('deaths', 0), reverse=True)
    
    elapsed_time = time.time() - start_time
    print(f"[Models] ========================================")
    print(f"[Models] Completed {model_id} in {elapsed_time:.2f} seconds")
    print(f"[Models] Found {len(results)} hospitals with alerts")
    print(f"[Models] ========================================")
    
    return results

