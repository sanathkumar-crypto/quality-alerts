#!/bin/bash
# Script to help restart Flask app and test webhook

echo "=========================================="
echo "Flask App Restart Helper"
echo "=========================================="
echo ""
echo "1. Make sure your Flask app is stopped (Ctrl+C if running)"
echo "2. Then run: python app.py"
echo ""
echo "When Flask starts, look for these messages:"
echo "  [Flask App] ✅ Loaded .env file from: ..."
echo "  [Flask App] ✅ GOOGLE_CHAT_WEBHOOK_URL loaded (length: 152)"
echo ""
echo "If you see warnings instead, there's a problem loading .env"
echo ""
echo "=========================================="
echo "Testing .env file loading..."
echo "=========================================="

cd "$(dirname "$0")"

python3 -c "
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath('.'))
ENV_FILE = os.path.join(BASE_DIR, '.env')

if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)
    webhook = os.getenv('GOOGLE_CHAT_WEBHOOK_URL', '')
    if webhook:
        print(f'✅ .env file loads correctly')
        print(f'✅ Webhook URL found (length: {len(webhook)})')
    else:
        print('❌ .env file exists but GOOGLE_CHAT_WEBHOOK_URL not found')
else:
    print(f'❌ .env file not found at: {ENV_FILE}')
"

echo ""
echo "=========================================="
echo "If the test above shows ✅, your .env file is correct"
echo "The issue is likely that Flask needs to be restarted"
echo "=========================================="

