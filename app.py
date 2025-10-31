"""
Flask web application for quality alerts dashboard.
"""

from flask import Flask, render_template, jsonify, request
from database import MortalityDatabase
from datetime import datetime, date
import json
import pandas as pd
from bigquery_queries import query_daily_pbd

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
        # Query PBD data from BigQuery
        pbd_data = query_daily_pbd(
            hospital_name=hospital_name,
            start_date=start_date,
            end_date=end_date
        )
        
        # Format response
        result = {
            'daily_pbd': []
        }
        
        for _, row in pbd_data.iterrows():
            result['daily_pbd'].append({
                'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date']),
                'hospital_name': row['hospital_name'],
                'total_pbd': int(row['total_pbd'])
            })
        
        return jsonify(result)
    except Exception as e:
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
    
    # Get raw data
    raw_data = get_db().get_raw_mortality_data(
        hospital_name=hospital_name,
        start_date=start_date,
        end_date=end_date
    )
    
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
    
    return jsonify(result)


if __name__ == '__main__':
    # Set use_reloader=False to prevent double-process issues in production
    # Debug mode can be enabled but reloader disabled for more stable operation
    app.run(debug=True, host='0.0.0.0', port=3000, use_reloader=False)



