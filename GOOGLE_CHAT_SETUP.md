# Google Chat Alerts Setup Guide

This guide explains how to set up automated alerts to Google Chat for quality monitoring.

## Features

1. **Automated Weekly Alerts**: Sends alerts every Monday at 9:00 AM for Model 10
2. **Manual Alerts**: Send alerts manually from the web interface for any model
3. **Rich Message Format**: Includes hospital details, mortality rates, and statistics

## Setup Instructions

### 1. Install Dependencies

Make sure you have the required Python packages installed:

```bash
pip install -r requirements.txt
```

The `requests` library is required for sending messages to Google Chat.

### 2. Google Chat Webhook Configuration

The webhook URL is already configured in `google_chat.py`:
- Webhook URL: `https://chat.googleapis.com/v1/spaces/AAQAqw1Odpo/messages?key=...`

If you need to change the webhook URL, edit the `GOOGLE_CHAT_WEBHOOK_URL` constant in `google_chat.py`.

### 3. Set Up Scheduled Alerts (Monday 9am)

#### Option A: Using Cron (Recommended for Linux/Mac)

Run the setup script:

```bash
./setup_cron.sh
```

This will:
- Add a cron job that runs every Monday at 9:00 AM
- Execute `send_scheduled_alert.py` with model10
- Log output to `logs/scheduled_alert.log`

#### Option B: Manual Cron Setup

Edit your crontab:

```bash
crontab -e
```

Add this line (adjust paths as needed):

```cron
0 9 * * 1 /path/to/venv/bin/python /path/to/send_scheduled_alert.py model10 >> /path/to/logs/scheduled_alert.log 2>&1
```

#### Option C: Using systemd Timer (Linux)

Create a systemd service file and timer for more advanced scheduling.

### 4. Manual Alert Sending

You can send alerts manually from the web interface:

1. Open the Quality Alerts Dashboard
2. Go to the "Alert Models" tab
3. Select a model from the dropdown
4. Click "📤 Send Alert to Google Chat" button
5. The alert will be sent immediately with the current model results

### 5. Testing

Test the alert system manually:

```bash
# Test with default model (model10)
python send_scheduled_alert.py

# Test with a different model
python send_scheduled_alert.py model9
```

Or use the web interface to send a test alert.

## Alert Message Format

The alert messages include:

- **Header**: Model name, period, and alert date
- **Hospital Details**: For each hospital with alerts:
  - Hospital name
  - This month's mortality rate
  - This month's absolute number of deaths
  - Threshold value
  - Last 6 months mortality rates
- **Summary**: Total hospitals, total deaths, average mortality rate

## Troubleshooting

### Alerts Not Sending

1. **Check webhook URL**: Verify the webhook URL in `google_chat.py` is correct
2. **Check logs**: Review `logs/scheduled_alert.log` for errors
3. **Test manually**: Run `python send_scheduled_alert.py` to test
4. **Check cron**: Verify cron job is set up: `crontab -l`

### Cron Job Not Running

1. **Check cron service**: Ensure cron is running: `systemctl status cron` (Linux)
2. **Check permissions**: Ensure the script is executable: `chmod +x send_scheduled_alert.py`
3. **Check paths**: Verify all paths in the cron job are absolute
4. **Check Python path**: Ensure the virtual environment path is correct

### Webhook Errors

If you see HTTP errors when sending alerts:

1. **Verify webhook URL**: The URL should be valid and active
2. **Check network**: Ensure the server can reach `chat.googleapis.com`
3. **Check authentication**: Verify the webhook token is still valid

## Files

- `google_chat.py`: Google Chat integration module
- `send_scheduled_alert.py`: Scheduled task script
- `setup_cron.sh`: Cron setup script
- `app.py`: Flask app with `/api/send-alert` endpoint
- `templates/index.html`: Frontend with send alert button
- `static/js/main.js`: JavaScript for manual alert sending

## Notes

- The scheduled alert runs for **Model 10** by default (Mortality % > Highest in Last 6 months)
- You can change the default model by editing the cron job or `send_scheduled_alert.py`
- Logs are stored in the `logs/` directory
- Manual alerts can be sent for any model from the web interface

