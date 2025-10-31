#!/bin/bash
# Script to start the Flask server persistently
# This will keep the server running and restart it if it crashes
# Usage: ./start_server.sh

cd "$(dirname "$0")"
source venv/bin/activate

# Log file for server output
LOG_FILE="/tmp/flask_server.log"

# PID file to track server process
PID_FILE="/tmp/flask_server.pid"

# Function to cleanup on exit
cleanup() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID 2>/dev/null
        fi
        rm -f "$PID_FILE"
    fi
    exit
}

trap cleanup SIGINT SIGTERM

# Start server in a loop - if it crashes, restart it
while true; do
    echo "$(date): Starting Flask server on port 3000..." >> "$LOG_FILE"
    python app.py >> "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > "$PID_FILE"
    
    # Wait for the server process
    wait $SERVER_PID
    EXIT_CODE=$?
    
    # Remove PID file
    rm -f "$PID_FILE"
    
    if [ $EXIT_CODE -ne 0 ] && [ $EXIT_CODE -ne 130 ]; then
        # 130 is SIGINT (Ctrl+C), which is normal shutdown
        echo "$(date): Server crashed with exit code $EXIT_CODE. Restarting in 5 seconds..." >> "$LOG_FILE"
        sleep 5
    else
        echo "$(date): Server stopped normally (exit code: $EXIT_CODE)." >> "$LOG_FILE"
        break
    fi
done

