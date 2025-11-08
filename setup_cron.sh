#!/bin/bash
# Setup script to add cron job for Monday 9am alerts

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="$SCRIPT_DIR/venv/bin/python"
SCRIPT_PATH="$SCRIPT_DIR/send_scheduled_alert.py"

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: Virtual environment not found at $PYTHON_PATH"
    echo "Please create a virtual environment first: python3 -m venv venv"
    exit 1
fi

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script not found at $SCRIPT_PATH"
    exit 1
fi

# Create log directory if it doesn't exist
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# Cron job: Every Monday at 9:00 AM
# Format: minute hour day month weekday command
CRON_JOB="0 9 * * 1 $PYTHON_PATH $SCRIPT_PATH model10 >> $LOG_DIR/scheduled_alert.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$SCRIPT_PATH"; then
    echo "Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "$SCRIPT_PATH" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "Cron job details:"
echo "  Schedule: Every Monday at 9:00 AM"
echo "  Command: $PYTHON_PATH $SCRIPT_PATH model10"
echo "  Log file: $LOG_DIR/scheduled_alert.log"
echo ""
echo "To view current cron jobs: crontab -l"
echo "To remove this cron job: crontab -e (then delete the line)"

