# Important Notes

## BigQuery Schema Considerations

The original query only showed these columns:
- `patient_id`
- `cpmrn`
- `encounters`
- `hospital_name`
- `icu_discharge_disposition`

**IMPORTANT**: The queries in `bigquery_queries.py` assume a column called `icu_discharge_date` exists. 

You may need to:
1. Check your actual BigQuery table schema to find the correct date column name
2. Update `bigquery_queries.py` with the correct date column
3. Common alternatives might be:
   - `discharge_date`
   - `icu_admission_date` (if using admission date instead)
   - A timestamp column that needs to be converted
   - A derived date from another field

To check your schema, run:
```sql
SELECT column_name, data_type
FROM `prod-tech-project1-bv479-zo027.analytics.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'discharged_patients_fact'
ORDER BY ordinal_position
```

## Testing the System

1. **First, verify BigQuery columns**:
   ```bash
   python query_bigquery.py  # This works, so the connection is good
   ```

2. **Check what columns are available** by modifying the query temporarily to see all columns

3. **Update `bigquery_queries.py`** with the correct date column name

4. Then run initialization:
   ```bash
   python initialize_data.py
   ```

## Daily Cron Setup

To set up automatic daily updates:

```bash
crontab -e
```

Add:
```bash
# Run daily update at 2 AM
0 2 * * * cd /home/sanath/quality-alerts && /home/sanath/quality-alerts/venv/bin/python /home/sanath/quality-alerts/daily_update.py >> /home/sanath/quality-alerts/logs/daily_update.log 2>&1
```

Make sure to create the logs directory:
```bash
mkdir -p logs
```

