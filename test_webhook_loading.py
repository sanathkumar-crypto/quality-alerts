#!/usr/bin/env python3
"""
Test script to verify webhook URL loading.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Testing Webhook URL Loading")
print("=" * 60)

# Test 1: Direct load_dotenv
print("\n1. Testing direct load_dotenv...")
try:
    from dotenv import load_dotenv
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ENV_FILE = os.path.join(BASE_DIR, '.env')
    print(f"   .env file path: {ENV_FILE}")
    print(f"   .env file exists: {os.path.exists(ENV_FILE)}")
    
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE, override=True)
        webhook_url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "")
        if webhook_url:
            print(f"   ✅ Webhook URL loaded (length: {len(webhook_url)})")
        else:
            print("   ❌ Webhook URL NOT loaded")
    else:
        print("   ❌ .env file not found")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Import google_chat module
print("\n2. Testing google_chat module import...")
try:
    from google_chat import get_webhook_url, GOOGLE_CHAT_WEBHOOK_URL
    print(f"   Module-level GOOGLE_CHAT_WEBHOOK_URL length: {len(GOOGLE_CHAT_WEBHOOK_URL)}")
    
    # Call the function
    url = get_webhook_url()
    if url:
        print(f"   ✅ get_webhook_url() returned URL (length: {len(url)})")
    else:
        print("   ❌ get_webhook_url() returned empty string")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Test send_model_alert function
print("\n3. Testing send_model_alert function (dry run)...")
try:
    from google_chat import send_model_alert
    print("   Function imported successfully")
    # Don't actually send, just test that it can be called
    print("   ✅ send_model_alert function is available")
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)

