#!/usr/bin/env python3
"""Test BigQuery query timeout for current month mortality."""

import time
from bigquery_queries import query_current_month_mortality

hospital = "Cachar"
year = 2025
month = 11

print(f"Testing BigQuery query for {hospital}, {year}-{month:02d}...")
print("=" * 80)

start_time = time.time()

try:
    result = query_current_month_mortality(
        hospital_name=hospital,
        year=year,
        month=month
    )
    elapsed = time.time() - start_time
    print(f"\n✅ Query completed in {elapsed:.2f} seconds")
    print(f"Rows returned: {len(result)}")
    if len(result) > 0:
        print(result.to_string())
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\n❌ Query failed after {elapsed:.2f} seconds")
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

