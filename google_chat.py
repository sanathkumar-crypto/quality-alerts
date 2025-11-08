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

def get_webhook_urls() -> List[str]:
    """
    Get all Google Chat webhook URLs from environment variables.
    Supports:
    - GOOGLE_CHAT_WEBHOOK_URL: Single URL or comma-separated URLs
    - GOOGLE_CHAT_WEBHOOK_URLS: Comma-separated list of additional URLs (optional)
    
    Returns a list of all unique webhook URLs.
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
    
    webhook_urls = []
    
    # Get primary webhook URL(s) - can be single URL or comma-separated
    primary_url = os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "")
    if primary_url:
        # Split by comma and strip whitespace
        urls = [url.strip() for url in primary_url.split(',') if url.strip()]
        webhook_urls.extend(urls)
        print(f"[Google Chat] Found {len(urls)} webhook URL(s) in GOOGLE_CHAT_WEBHOOK_URL")
    
    # Get additional webhook URLs (optional)
    additional_urls = os.getenv("GOOGLE_CHAT_WEBHOOK_URLS", "")
    if additional_urls:
        # Split by comma and strip whitespace
        urls = [url.strip() for url in additional_urls.split(',') if url.strip()]
        webhook_urls.extend(urls)
        print(f"[Google Chat] Found {len(urls)} additional webhook URL(s) in GOOGLE_CHAT_WEBHOOK_URLS")
    
    # Remove duplicates while preserving order
    unique_urls = []
    seen = set()
    for url in webhook_urls:
        if url and url not in seen:
            unique_urls.append(url)
            seen.add(url)
    
    if unique_urls:
        print(f"[Google Chat] Total unique webhook URLs: {len(unique_urls)}")
    else:
        print("[Google Chat] WARNING: No webhook URLs found in environment!")
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
    
    return unique_urls

# Initialize webhook URLs at module load (but can be reloaded if needed)
GOOGLE_CHAT_WEBHOOK_URLS = get_webhook_urls()

# For backward compatibility, keep the first URL as GOOGLE_CHAT_WEBHOOK_URL
GOOGLE_CHAT_WEBHOOK_URL = GOOGLE_CHAT_WEBHOOK_URLS[0] if GOOGLE_CHAT_WEBHOOK_URLS else ""

# Debug: Check if webhook URLs are loaded (don't print the full URLs for security)
if GOOGLE_CHAT_WEBHOOK_URLS:
    print(f"[Google Chat] {len(GOOGLE_CHAT_WEBHOOK_URLS)} webhook URL(s) loaded")
else:
    print("[Google Chat] WARNING: No webhook URLs configured!")
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


def send_google_chat_message(message: Dict, webhook_urls: Optional[List[str]] = None) -> Dict[str, bool]:
    """
    Send a message to Google Chat using webhook URL(s).
    
    Args:
        message: Dictionary with message content (should have 'text' key)
        webhook_urls: Optional list of webhook URLs (defaults to GOOGLE_CHAT_WEBHOOK_URLS from environment)
    
    Returns:
        Dictionary mapping webhook URL (or index) to success status (True/False)
    """
    if webhook_urls is None:
        # Reload webhook URLs in case .env was loaded after module import
        webhook_urls = get_webhook_urls()
    
    if not webhook_urls:
        error_msg = "Google Chat webhook URL not configured. Please set GOOGLE_CHAT_WEBHOOK_URL environment variable in .env file."
        print(f"[Google Chat] Error: {error_msg}")
        env_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        print(f"[Google Chat] Expected .env file at: {env_file_path}")
        print(f"[Google Chat] .env file exists: {os.path.exists(env_file_path)}")
        raise ValueError(error_msg)
    
    results = {}
    success_count = 0
    
    for idx, webhook_url in enumerate(webhook_urls, 1):
        try:
            print(f"[Google Chat] Sending message to webhook {idx}/{len(webhook_urls)}...")
            response = requests.post(
                webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            print(f"[Google Chat] ✅ Message sent successfully to webhook {idx}: {response.status_code}")
            results[f"webhook_{idx}"] = True
            success_count += 1
        except requests.exceptions.RequestException as e:
            print(f"[Google Chat] ❌ Error sending message to webhook {idx}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[Google Chat] Response: {e.response.text}")
            results[f"webhook_{idx}"] = False
    
    print(f"[Google Chat] Sent to {success_count}/{len(webhook_urls)} webhook(s) successfully")
    
    # Return True if at least one succeeded (for backward compatibility)
    return results


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
            send_results = send_google_chat_message(message)
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
        
        # Check if at least one webhook succeeded
        success_count = sum(1 for success in send_results.values() if success)
        total_webhooks = len(send_results)
        
        if success_count > 0:
            if len(results) == 0:
                message_text = f"Alert sent successfully for {model_id} to {success_count}/{total_webhooks} chat space(s). No hospitals meet the threshold criteria."
            else:
                message_text = f"Alert sent successfully for {model_id} to {success_count}/{total_webhooks} chat space(s). {len(results)} hospitals with alerts."
            return {
                "success": True,
                "message": message_text,
                "hospitals_count": len(results),
                "webhooks_sent": success_count,
                "webhooks_total": total_webhooks
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send alert for {model_id} to any chat space. Check server logs for details.",
                "hospitals_count": len(results),
                "webhooks_sent": 0,
                "webhooks_total": total_webhooks
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

