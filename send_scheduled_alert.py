#!/usr/bin/env python3
"""
Scheduled task to send quality alerts to Google Chat every Monday at 9am.
This script can be run via cron or systemd timer.

Usage:
    python send_scheduled_alert.py [model_id]

Default model: model10
"""

import sys
import os
from datetime import datetime
from google_chat import send_model_alert

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main function to send scheduled alert."""
    # Default to model10 if not specified
    model_id = sys.argv[1] if len(sys.argv) > 1 else "model10"
    
    print(f"[Scheduled Alert] Starting scheduled alert for {model_id}")
    print(f"[Scheduled Alert] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        result = send_model_alert(model_id)
        
        if result['success']:
            print(f"[Scheduled Alert] ✅ Success: {result['message']}")
            print(f"[Scheduled Alert] Hospitals with alerts: {result['hospitals_count']}")
            sys.exit(0)
        else:
            print(f"[Scheduled Alert] ❌ Failed: {result['message']}")
            sys.exit(1)
    
    except Exception as e:
        print(f"[Scheduled Alert] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

