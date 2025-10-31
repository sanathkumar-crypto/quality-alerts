"""
Configuration file for the quality alerts system.
"""

# BigQuery configuration
BIGQUERY_PROJECT_ID = "prod-tech-project1-bv479-zo027"
BIGQUERY_DATASET = "analytics"
BIGQUERY_TABLE = "discharged_patients_fact"

# Database configuration
DATABASE_PATH = "quality_alerts.db"

# Alert configuration
ALERT_SD_THRESHOLD = 3  # Number of standard deviations for alert threshold

# Email configuration (optional - for sending alerts)
# SMTP_HOST = "smtp.gmail.com"
# SMTP_PORT = 587
# SMTP_USER = "your_email@gmail.com"
# SMTP_PASSWORD = "your_password"
# ALERT_EMAIL_TO = "alerts@example.com"



