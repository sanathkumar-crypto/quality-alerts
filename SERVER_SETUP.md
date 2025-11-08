# Server Setup Guide

## Quick Start

The Flask server is now configured to run persistently. Here are the options:

### Option 1: Use the Start Script (Recommended)

```bash
cd /home/sanath/quality-alerts
./start_server.sh
```

This will:
- Start the server on port 3000
- Automatically restart if it crashes
- Keep running in the background
- Log output to `/tmp/flask_server.log`

### Option 2: Run in Background (One-time)

```bash
cd /home/sanath/quality-alerts
source venv/bin/activate
nohup python app.py > /tmp/flask_server.log 2>&1 &
```

### Option 3: Systemd Service (For Production)

If you want the server to start automatically on boot:

```bash
# Copy service file (requires sudo)
sudo cp quality-alerts.service /etc/systemd/system/

# Enable and start the service
sudo systemctl enable quality-alerts
sudo systemctl start quality-alerts

# Check status
sudo systemctl status quality-alerts

# View logs
sudo journalctl -u quality-alerts -f
```

## Why the Server Stops

The server may stop if:
1. **Debug mode reloader**: Flask's debug mode can cause process issues - now disabled
2. **Terminal closure**: If running in foreground, closing terminal kills it
3. **System reboot**: Server doesn't auto-start on boot (unless using systemd)

## Current Status

Check if server is running:
```bash
ps aux | grep "python.*app.py" | grep quality-alerts | grep -v grep
```

Check server logs:
```bash
tail -f /tmp/flask_server.log
```

Stop the server:
```bash
pkill -f "python.*app.py"
# Or if using start_server.sh:
pkill -f "start_server.sh"
```

## Troubleshooting

If server won't start:
1. Check if port 3000 is already in use: `lsof -i:3000`
2. Check logs: `tail -50 /tmp/flask_server.log`
3. Verify database exists: `ls -lh quality_alerts.db`


