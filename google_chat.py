"""
Google Chat integration for sending alert messages.
"""

import os
import requests
import json
from typing import List, Dict, Optional
from datetime import datetime
from models import calculate_model_results

# Try to load environment variables from .env file
# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, '.env')

try:
    from dotenv import load_dotenv
    # Try to load from project root directory
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE)
        print(f"[Google Chat] Loaded .env file from: {ENV_FILE}")
    else:
        # Fallback: try current directory
        load_dotenv()
        print(f"[Google Chat] Attempted to load .env from current directory")
except ImportError:
    # python-dotenv not installed, skip loading .env file
    print("[Google Chat] python-dotenv not installed, skipping .env file loading")
except Exception as e:
    print(f"[Google Chat] Error loading .env file: {e}")

def get_webhook_url() -> str:
    """
    Get the Google Chat webhook URL from environment variable.
    This function ensures the .env file is loaded before reading the value.
    """
    # Always try to load .env file first to ensure it's loaded
    try:
        from dotenv import load_dotenv
        env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_file_path):
            load_dotenv(env_file_path, override=True)
            print(f"[Google Chat] Loaded .env from: {env_file_path}")
        else:
            # Try current directory
            load_dotenv(override=True)
            print(f"[Google Chat] Attempted to load .env from current directory")
    except ImportError:
        print("[Google Chat] python-dotenv not installed")
    except Exception as e:
        print(f"[Google Chat] Error loading .env: {e}")
    
    webhook_url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "")
    
    if webhook_url:
        print(f"[Google Chat] Webhook URL found (length: {len(webhook_url)})")
    else:
        print("[Google Chat] WARNING: GOOGLE_CHAT_WEBHOOK_URL not found in environment!")
        env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        print(f"[Google Chat] .env file path: {env_file_path}")
        print(f"[Google Chat] .env file exists: {os.path.exists(env_file_path)}")
        if os.path.exists(env_file_path):
            # Try reading the file directly to debug
            try:
                with open(env_file_path, 'r') as f:
                    content = f.read()
                    if 'GOOGLE_CHAT_WEBHOOK_URL' in content:
                        print("[Google Chat] .env file contains GOOGLE_CHAT_WEBHOOK_URL")
                    else:
                        print("[Google Chat] .env file does NOT contain GOOGLE_CHAT_WEBHOOK_URL")
            except Exception as e:
                print(f"[Google Chat] Error reading .env file: {e}")
    
    return webhook_url

# Initialize webhook URL at module load (but can be reloaded if needed)
GOOGLE_CHAT_WEBHOOK_URL = get_webhook_url()

# Debug: Check if webhook URL is loaded (don't print the full URL for security)
if GOOGLE_CHAT_WEBHOOK_URL:
    print(f"[Google Chat] Webhook URL loaded (length: {len(GOOGLE_CHAT_WEBHOOK_URL)} characters)")
else:
    print("[Google Chat] WARNING: GOOGLE_CHAT_WEBHOOK_URL not set!")
    print(f"[Google Chat] Checked .env file at: {ENV_FILE}")
    print(f"[Google Chat] .env file exists: {os.path.exists(ENV_FILE)}")


def format_model_10_alert_message(results: List[Dict]) -> Dict:
    """
    Format alert message for Model 10 with required information:
    - List of hospitals selected for alert
    - This month's mortality rate
    - Last 6 months mortality rate
    - Absolute number of deaths this month
    """
    if not results:
        today = datetime.now()
        current_period = today.strftime("%B %Y")
        return {
            "text": f"✅ *Quality Alert - Model 10*\n*Period:* {current_period}\n*Alert Date:* {today.strftime('%Y-%m-%d %H:%M:%S')}\n\nNo hospital has a mortality rate that meets the set threshold."
        }
    
    today = datetime.now()
    current_period = today.strftime("%B %Y")
    
    # Build the message
    message_parts = [
        f"🚨 *Quality Alert - Model 10*",
        f"*Period:* {current_period}",
        f"*Alert Date:* {today.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"*Hospitals with Alerts: {len(results)}*",
        ""
    ]
    
    # Add details for each hospital
    for idx, result in enumerate(results, 1):
        hospital_name = result.get('hospital_name', 'Unknown')
        current_mortality = result.get('mortality_rate', 0.0)
        current_deaths = result.get('deaths', 0)
        threshold = result.get('threshold', 0.0)
        last_6_months = result.get('last_6_months_mortality', [])
        
        message_parts.append(f"*{idx}. {hospital_name}*")
        message_parts.append(f"   • This Month Mortality Rate: *{current_mortality:.2f}%*")
        message_parts.append(f"   • This Month Deaths: *{current_deaths}*")
        message_parts.append(f"   • Threshold: {threshold:.2f}%")
        
        # Add last 6 months mortality rates
        if last_6_months:
            months_str = ", ".join([f"{m['period']}: {m['mortality_rate']:.2f}%" for m in last_6_months])
            message_parts.append(f"   • Last 6 Months: {months_str}")
        
        message_parts.append("")
    
    # Add summary
    total_deaths = sum(r.get('deaths', 0) for r in results)
    avg_mortality = sum(r.get('mortality_rate', 0.0) for r in results) / len(results) if results else 0.0
    
    message_parts.append("---")
    message_parts.append(f"*Summary:*")
    message_parts.append(f"• Total Hospitals with Alerts: {len(results)}")
    message_parts.append(f"• Total Deaths This Month: {total_deaths}")
    message_parts.append(f"• Average Mortality Rate: {avg_mortality:.2f}%")
    
    return {
        "text": "\n".join(message_parts)
    }


def format_generic_alert_message(model_id: str, results: List[Dict]) -> Dict:
    """
    Format alert message for any model.
    """
    if not results:
        today = datetime.now()
        current_period = today.strftime("%B %Y")
        model_name = model_id.replace('model', 'Model ')
        return {
            "text": f"✅ *Quality Alert - {model_name}*\n*Period:* {current_period}\n*Alert Date:* {today.strftime('%Y-%m-%d %H:%M:%S')}\n\nNo hospital has a mortality rate that meets the set threshold."
        }
    
    today = datetime.now()
    current_period = today.strftime("%B %Y")
    model_name = model_id.replace('model', 'Model ')
    
    # Build the message
    message_parts = [
        f"🚨 *Quality Alert - {model_name}*",
        f"*Period:* {current_period}",
        f"*Alert Date:* {today.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"*Hospitals with Alerts: {len(results)}*",
        ""
    ]
    
    # Add details for each hospital
    for idx, result in enumerate(results, 1):
        hospital_name = result.get('hospital_name', 'Unknown')
        current_mortality = result.get('mortality_rate', 0.0)
        current_deaths = result.get('deaths', 0)
        threshold = result.get('threshold', 0.0)
        smr = result.get('smr')
        last_6_months = result.get('last_6_months_mortality', [])
        
        message_parts.append(f"*{idx}. {hospital_name}*")
        message_parts.append(f"   • This Month Mortality Rate: *{current_mortality:.2f}%*")
        message_parts.append(f"   • This Month Deaths: *{current_deaths}*")
        message_parts.append(f"   • Threshold: {threshold:.2f}%")
        
        if smr is not None:
            message_parts.append(f"   • SMR: {smr:.2f}")
        
        # Add last 6 months mortality rates
        if last_6_months:
            months_str = ", ".join([f"{m['period']}: {m['mortality_rate']:.2f}%" for m in last_6_months])
            message_parts.append(f"   • Last 6 Months: {months_str}")
        
        message_parts.append("")
    
    # Add summary
    total_deaths = sum(r.get('deaths', 0) for r in results)
    avg_mortality = sum(r.get('mortality_rate', 0.0) for r in results) / len(results) if results else 0.0
    
    message_parts.append("---")
    message_parts.append(f"*Summary:*")
    message_parts.append(f"• Total Hospitals with Alerts: {len(results)}")
    message_parts.append(f"• Total Deaths This Month: {total_deaths}")
    message_parts.append(f"• Average Mortality Rate: {avg_mortality:.2f}%")
    
    return {
        "text": "\n".join(message_parts)
    }


def send_google_chat_message(message: Dict, webhook_url: Optional[str] = None) -> bool:
    """
    Send a message to Google Chat using the webhook URL.
    
    Args:
        message: Dictionary with message content (should have 'text' key)
        webhook_url: Optional webhook URL (defaults to GOOGLE_CHAT_WEBHOOK_URL from environment)
    
    Returns:
        True if successful, False otherwise
    """
    if webhook_url is None:
        # Reload webhook URL in case .env was loaded after module import
        webhook_url = get_webhook_url()
    
    if not webhook_url:
        error_msg = "Google Chat webhook URL not configured. Please set GOOGLE_CHAT_WEBHOOK_URL environment variable in .env file."
        print(f"[Google Chat] Error: {error_msg}")
        env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        print(f"[Google Chat] Expected .env file at: {env_file_path}")
        print(f"[Google Chat] .env file exists: {os.path.exists(env_file_path)}")
        raise ValueError(error_msg)
    
    try:
        response = requests.post(
            webhook_url,
            json=message,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()
        print(f"[Google Chat] Message sent successfully: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[Google Chat] Error sending message: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[Google Chat] Response: {e.response.text}")
        return False


def send_model_alert(model_id: str = "model10", webhook_url: Optional[str] = None) -> Dict:
    """
    Calculate model results and send alert to Google Chat.
    
    Args:
        model_id: Model ID to calculate (default: "model10")
        webhook_url: Optional webhook URL
    
    Returns:
        Dictionary with success status and message
    """
    try:
        print(f"[Google Chat] Calculating results for {model_id}...")
        # Apply death increase filter for Google Chat alerts (only send if increase >= 2)
        results = calculate_model_results(model_id, apply_death_increase_filter=True)
        print(f"[Google Chat] Found {len(results)} hospitals with alerts (after applying death increase filter)")
        
        # Format message based on model
        if model_id == "model10":
            message = format_model_10_alert_message(results)
        else:
            message = format_generic_alert_message(model_id, results)
        
        # Send message (always send, even if no hospitals meet criteria)
        try:
            success = send_google_chat_message(message, webhook_url)
        except ValueError as ve:
            # Webhook URL not configured
            error_msg = str(ve)
            print(f"[Google Chat] ValueError when sending message: {error_msg}")
            return {
                "success": False,
                "message": error_msg,
                "hospitals_count": len(results)
            }
        except Exception as send_error:
            # Other errors when sending
            error_msg = f"Error sending message to Google Chat: {str(send_error)}"
            print(f"[Google Chat] Exception when sending message: {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": error_msg,
                "hospitals_count": len(results)
            }
        
        if success:
            if len(results) == 0:
                message_text = f"Alert sent successfully for {model_id}. No hospitals meet the threshold criteria."
            else:
                message_text = f"Alert sent successfully for {model_id}. {len(results)} hospitals with alerts."
            return {
                "success": True,
                "message": message_text,
                "hospitals_count": len(results)
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send alert for {model_id}. Check server logs for details.",
                "hospitals_count": len(results)
            }
    
    except Exception as e:
        error_msg = f"Error sending alert for {model_id}: {str(e)}"
        print(f"[Google Chat] {error_msg}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": error_msg,
            "hospitals_count": 0
        }

