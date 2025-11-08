#!/bin/bash
# Setup script to add cron job for daily monthly data sync at 8:30 AM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="$SCRIPT_DIR/venv/bin/python"
SYNC_SCRIPT="$SCRIPT_DIR/sync_month.py"

# Check if virtual environment exists
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: Virtual environment not found at $PYTHON_PATH"
    echo "Please create a virtual environment first: python3 -m venv venv"
    exit 1
fi

# Check if script exists
if [ ! -f "$SYNC_SCRIPT" ]; then
    echo "Error: Sync script not found at $SYNC_SCRIPT"
    exit 1
fi

# Create log directory if it doesn't exist
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# Get current month (year and month)
# Cron job: Every day at 8:30 AM
# Format: minute hour day month weekday command
# We'll use a wrapper script that gets the current month automatically
CRON_JOB="30 8 * * * cd $SCRIPT_DIR && $PYTHON_PATH $SYNC_SCRIPT >> $LOG_DIR/daily_sync.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "$SYNC_SCRIPT"; then
    echo "Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "$SYNC_SCRIPT" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "Cron job details:"
echo "  Schedule: Every day at 8:30 AM"
echo "  Command: $PYTHON_PATH $SYNC_SCRIPT"
echo "  Log file: $LOG_DIR/daily_sync.log"
echo ""
echo "The script will automatically sync the current month's data daily."
echo ""
echo "To view current cron jobs: crontab -l"
echo "To remove this cron job: crontab -e (then delete the line)"
echo "To view logs: tail -f $LOG_DIR/daily_sync.log"

