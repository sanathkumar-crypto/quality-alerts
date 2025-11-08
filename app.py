"""
Flask web application for quality alerts dashboard.
"""

from flask import Flask, render_template, jsonify, request
from database import MortalityDatabase
from datetime import datetime, date
import json
import pandas as pd
from bigquery_queries import query_daily_pbd, query_current_month_mortality_all_hospitals, query_current_month_mortality

app = Flask(__name__)

# Initialize database once at startup - this is fast
_db = MortalityDatabase()

def get_db():
    """Get database instance."""
    return _db


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    """Return empty favicon to prevent 404 errors."""
    return '', 204


@app.route('/api/hospitals')
def get_hospitals():
    """Get list of all hospitals."""
    hospitals = get_db().get_all_hospitals()
    return jsonify(hospitals)


@app.route('/api/mortality-data')
def get_mortality_data():
    """Get mortality data for a specific hospital and date range."""
    hospital_name = request.args.get('hospital_name')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Parse dates
    start_date = None
    end_date = None
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
    
    # Get monthly data for the filtered date range
    monthly_data = get_db().get_monthly_data(
        hospital_name=hospital_name,
        start_date=start_date,
        end_date=end_date
    )
    
    # Check if current month is in the date range and not in database
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    need_current_month = False
    if end_date:
        # Check if end_date includes current month
        if end_date.year == current_year and end_date.month >= current_month:
            need_current_month = True
        elif end_date.year > current_year:
            need_current_month = True
    
    # Check if current month is already in the data
    if need_current_month:
        current_month_in_data = monthly_data[
            (monthly_data['year'] == current_year) & 
            (monthly_data['month'] == current_month)
        ]
        
        # Try to fetch current month from BigQuery, but don't block if it's slow
        # Return database data immediately, and add BigQuery data if it completes quickly
        if len(current_month_in_data) == 0:
            print(f"[API Mortality Data] Current month {current_year}-{current_month:02d} not in database")
            # Note: BigQuery query disabled due to timeout issues
            # Current month data will be available once synced to database
            # To enable BigQuery: uncomment the code below and ensure proper timeout handling
    
    # Format response
    result = {
        'monthly_data': [],
        'statistics': None
    }
    
    for _, row in monthly_data.iterrows():
        # Create date string for the month
        month_date = f"{int(row['year'])}-{int(row['month']):02d}-01"
        result['monthly_data'].append({
            'date': month_date,
            'year': int(row['year']),
            'month': int(row['month']),
            'total_patients': int(row['total_patients']),
            'deaths': int(row['deaths']),
            'mortality_rate': float(row['mortality_rate'])
        })
    
    # Calculate statistics from the filtered data (not from stored statistics)
    if len(monthly_data) > 0:
        mortality_rates = monthly_data['mortality_rate'].values
        
        avg_mortality = float(mortality_rates.mean())
        std_deviation = float(mortality_rates.std())
        
        # If std_deviation is NaN (only one data point), set to 0
        if pd.isna(std_deviation):
            std_deviation = 0.0
        
        threshold_3sd = avg_mortality + (3 * std_deviation)
        
        result['statistics'] = {
            'avg_mortality_rate': avg_mortality,
            'std_deviation': std_deviation,
            'threshold_3sd': threshold_3sd
        }
    
    return jsonify(result)


@app.route('/api/pbd-data')
def get_pbd_data():
    """Get Patient Bed Days (PBD) data for a specific hospital and date range."""
    hospital_name = request.args.get('hospital_name')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Parse dates
    start_date = None
    end_date = None
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
    
    try:
        import time
        from datetime import timedelta
        start_time = time.time()
        print(f"[API PBD] ========================================")
        print(f"[API PBD] NEW REQUEST RECEIVED")
        print(f"[API PBD] ========================================")
        print(f"[API PBD] Request: hospital={hospital_name}, start_date={start_date}, end_date={end_date}")
        
        # Check date range - if too large, limit it
        if start_date and end_date:
            days_diff = (end_date - start_date).days
            print(f"[API PBD] Date range: {days_diff} days")
            if days_diff > 180:
                print(f"[API PBD] ⚠️  Date range {days_diff} days exceeds 180 days, limiting to last 180 days")
                start_date = end_date - timedelta(days=180)
                print(f"[API PBD] Adjusted start_date: {start_date}")
        
        # Query PBD data from BigQuery with timeout
        print(f"[API PBD] Calling query_daily_pbd()...")
        try:
            pbd_data = query_daily_pbd(
                hospital_name=hospital_name,
                start_date=start_date,
                end_date=end_date
            )
            query_time = time.time() - start_time
            print(f"[API PBD] ✅ Query completed in {query_time:.2f} seconds, returned {len(pbd_data)} rows")
        except TimeoutError as timeout_error:
            query_time = time.time() - start_time
            print(f"[API PBD] ❌ TIMEOUT after {query_time:.2f} seconds")
            print(f"[API PBD] Error: {timeout_error}")
            return jsonify({'error': 'PBD query timed out. Please try a shorter date range (max 3 months).'}), 408
        except Exception as query_error:
            query_time = time.time() - start_time
            print(f"[API PBD] ❌ ERROR after {query_time:.2f} seconds")
            print(f"[API PBD] Error type: {type(query_error).__name__}")
            print(f"[API PBD] Error message: {query_error}")
            import traceback
            print(f"[API PBD] Traceback:")
            traceback.print_exc()
            return jsonify({'error': f'PBD query failed: {str(query_error)}'}), 500
        
        # Format response
        print(f"[API PBD] Formatting response...")
        result = {
            'daily_pbd': []
        }
        
        for _, row in pbd_data.iterrows():
            result['daily_pbd'].append({
                'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                'hospital_name': row['hospital_name'],
                'total_pbd': int(row['total_pbd'])
            })
        
        total_time = time.time() - start_time
        print(f"[API PBD] ✅ Returning {len(result['daily_pbd'])} PBD records")
        print(f"[API PBD] Total request time: {total_time:.2f} seconds")
        print(f"[API PBD] ========================================")
        return jsonify(result)
    except Exception as e:
        print(f"[API PBD] EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/raw-data')
def get_raw_data():
    """Get raw mortality data for the applied filters."""
    hospital_name = request.args.get('hospital_name')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Parse dates
    start_date = None
    end_date = None
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
    
    # Get raw data from database
    raw_data = get_db().get_raw_mortality_data(
        hospital_name=hospital_name,
        start_date=start_date,
        end_date=end_date
    )
    
    # Check if current month is in the date range and not in database
    today = date.today()
    current_year = today.year
    current_month = today.month
    
    print(f"[API Raw Data] Request: hospital={hospital_name}, start_date={start_date}, end_date={end_date}")
    print(f"[API Raw Data] Current date: {today}, Current month: {current_year}-{current_month:02d}")
    print(f"[API Raw Data] Database returned {len(raw_data)} rows")
    if len(raw_data) > 0:
        months_list = raw_data[['year', 'month']].drop_duplicates().apply(
            lambda x: f"{int(x['year'])}-{int(x['month']):02d}", axis=1
        ).tolist()
        print(f"[API Raw Data] Database data months: {sorted(months_list)}")
    
    # Check if we need to add current month data
    need_current_month = False
    if end_date:
        # Check if end_date includes current month
        if end_date.year == current_year and end_date.month >= current_month:
            need_current_month = True
        elif end_date.year > current_year:
            need_current_month = True
    else:
        # If no end_date specified, check if start_date includes current month
        if start_date and start_date.year == current_year and start_date.month <= current_month:
            need_current_month = True
    
    print(f"[API Raw Data] Need current month data: {need_current_month}")
    
    # Check if current month is already in the data
    if need_current_month:
        current_month_in_data = raw_data[
            (raw_data['year'] == current_year) & 
            (raw_data['month'] == current_month)
        ]
        
        print(f"[API Raw Data] Current month in database result: {len(current_month_in_data)} rows")
        
        # NOTE: BigQuery query for current month is disabled to prevent timeouts
        # The endpoint now returns database data only (matches mortality-data endpoint behavior)
        # Current month data will be available once it's synced to the database
        if len(current_month_in_data) == 0:
            print(f"[API Raw Data] Current month {current_year}-{current_month:02d} not in database")
            print(f"[API Raw Data] Returning database data only (BigQuery query disabled to prevent timeouts)")
            # Skip BigQuery query - return database data only
            # This matches the mortality-data endpoint behavior
    
    # Sort by year, month for consistent display
    raw_data = raw_data.sort_values(['year', 'month'], ascending=[True, True])
    
    print(f"[API Raw Data] Final data: {len(raw_data)} rows")
    if len(raw_data) > 0:
        final_months_list = raw_data[['year', 'month']].drop_duplicates().apply(
            lambda x: f"{int(x['year'])}-{int(x['month']):02d}", axis=1
        ).tolist()
        print(f"[API Raw Data] Final months in data: {sorted(final_months_list)}")
        # Check specifically for November
        nov_data = raw_data[(raw_data['year'] == current_year) & (raw_data['month'] == current_month)]
        print(f"[API Raw Data] November {current_year} rows: {len(nov_data)}")
        if len(nov_data) > 0:
            print(f"[API Raw Data] November data sample:")
            print(nov_data[['hospital_name', 'year', 'month', 'deaths', 'mortality_rate']].to_string())
    
    # Format response
    result = []
    for _, row in raw_data.iterrows():
        result.append({
            'hospital_name': row['hospital_name'],
            'year': int(row['year']),
            'month': int(row['month']),
            'month_name': datetime(2000, int(row['month']), 1).strftime('%B'),
            'total_patients': int(row['total_patients']),
            'deaths': int(row['deaths']),
            'mortality_rate': float(row['mortality_rate'])
        })
    
    print(f"[API Raw Data] Returning {len(result)} rows to frontend")
    return jsonify(result)


@app.route('/api/models/<model_id>')
def get_model_results(model_id):
    """Get alert results for a specific model."""
    from models import calculate_model_results
    import traceback
    
    try:
        print(f"[API] Calculating results for {model_id}...")
        results = calculate_model_results(model_id)
        print(f"[API] Found {len(results)} results for {model_id}")
        return jsonify({
            'model_id': model_id,
            'results': results
        })
    except Exception as e:
        print(f"[API] Error calculating model results for {model_id}: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/send-alert', methods=['POST'])
def send_alert():
    """Send alert to Google Chat for a specific model."""
    from google_chat import send_model_alert
    import traceback
    
    try:
        data = request.get_json()
        model_id = data.get('model_id', 'model10')
        
        if not model_id:
            return jsonify({'error': 'model_id is required'}), 400
        
        print(f"[API] Sending alert for {model_id}...")
        result = send_model_alert(model_id)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    
    except Exception as e:
        print(f"[API] Error sending alert: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500


if __name__ == '__main__':
    # Set use_reloader=False to prevent double-process issues in production
    # Debug mode can be enabled but reloader disabled for more stable operation
    app.run(debug=True, host='0.0.0.0', port=3000, use_reloader=False)



