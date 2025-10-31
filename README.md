# Quality Alerts System

A comprehensive mortality monitoring and alerting system for hospital quality management.

## Features

- **Historical Data Initialization**: One-time backfill of monthly mortality data from BigQuery
- **Daily Updates**: Automated daily script to append new mortality data
- **Statistical Analysis**: Automatic calculation of average mortality rate and standard deviation per hospital
- **Alert System**: Alerts when mortality rate exceeds +3 standard deviations
- **Web Dashboard**: Interactive frontend with:
  - Hospital dropdown filter
  - Date range picker
  - Line chart visualization showing:
    - Monthly mortality rates
    - Average mortality rate line
    - Alert threshold (+3SD) line
  - Real-time alert display

## Setup

### 1. Install Dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure BigQuery Access

Ensure you have BigQuery access configured:

```bash
gcloud auth application-default login
```

Or set service account credentials:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 3. Important: Check Your BigQuery Schema

The queries assume a date column for discharges. Based on your original query, you may need to adjust the column names in:
- `bigquery_queries.py` - Look for `icu_discharge_date` references
- You may need to use a different date column name depending on your actual schema

Common column names might be:
- `icu_discharge_date`
- `discharge_date`
- `date`
- Or you might need to derive the date from another field

**Please update `bigquery_queries.py` with the correct column names for your schema.**

### 4. Initialize Historical Data (One-time)

```bash
source venv/bin/activate
python initialize_data.py
```

This will:
- Query all historical monthly mortality data from BigQuery
- Calculate monthly death counts per hospital
- Store data in SQLite database
- Calculate initial statistics (average and +3SD thresholds)

### 5. Run Daily Updates

Set up a cron job to run daily:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM
0 2 * * * cd /path/to/quality-alerts && /path/to/venv/bin/python daily_update.py
```

Or run manually:
```bash
source venv/bin/activate
python daily_update.py
```

### 6. Start the Web Dashboard

```bash
source venv/bin/activate
python app.py
```

Then open your browser to: `http://localhost:5000`

## Project Structure

```
quality-alerts/
├── app.py                    # Flask web application
├── config.py                 # Configuration settings
├── database.py               # Database operations
├── bigquery_queries.py       # BigQuery query functions
├── initialize_data.py        # One-time initialization script
├── daily_update.py           # Daily update script
├── query_bigquery.py         # Original query script
├── requirements.txt          # Python dependencies
├── quality_alerts.db         # SQLite database (created on first run)
├── templates/
│   └── index.html           # Dashboard HTML template
└── static/
    ├── css/
    │   └── style.css        # Dashboard styles
    └── js/
        └── main.js          # Dashboard JavaScript

```

## Usage

### Dashboard

1. Select a hospital from the dropdown
2. Choose a date range
3. Click "Update Chart" to view:
   - Mortality rate trend over time
   - Average mortality rate (blue dashed line)
   - Alert threshold at +3SD (red dashed line)
   - Alerts when threshold is exceeded

### Alerts

The system automatically checks for alerts when:
- Daily updates are run
- The dashboard displays data exceeding the threshold

Alerts are shown when mortality rate exceeds: `Average + 3 × Standard Deviation`

## Database Schema

### monthly_mortality
- `hospital_name`: Name of the hospital
- `year`: Year
- `month`: Month (1-12)
- `total_patients`: Total patients discharged in that month
- `deaths`: Number of deaths in that month
- `mortality_rate`: Percentage mortality rate

### daily_mortality
- `hospital_name`: Name of the hospital
- `date`: Date
- `total_patients`: Total patients discharged on that date
- `deaths`: Number of deaths on that date
- `mortality_rate`: Percentage mortality rate

### hospital_statistics
- `hospital_name`: Name of the hospital
- `avg_mortality_rate`: Average mortality rate across all months
- `std_deviation`: Standard deviation of mortality rates
- `threshold_3sd`: Alert threshold (avg + 3 × std_dev)

## Troubleshooting

### BigQuery Authentication Errors
- Ensure you're authenticated: `gcloud auth application-default login`
- Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

### Date Column Not Found
- Check your BigQuery table schema
- Update column names in `bigquery_queries.py`
- The original query didn't show a date column - you may need to determine which column to use

### No Data in Dashboard
- Run `initialize_data.py` first to backfill historical data
- Check that BigQuery queries return data
- Verify database file `quality_alerts.db` exists and has data

## Customization

### Alert Threshold
Edit `config.py`:
```python
ALERT_SD_THRESHOLD = 3  # Change to 2 for tighter alerts, 4 for looser
```

### Email Alerts (TODO)
Configure email settings in `config.py` and implement email sending in `daily_update.py`.

## License

MIT
