"""
Google Chat integration for sending alert messages.
"""

import requests
import json
from typing import List, Dict, Optional
from datetime import datetime
from models import calculate_model_results


# Google Chat webhook URL
GOOGLE_CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAQAqw1Odpo/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=vPNrkZqIbX29ZpG-wsIDkebvJjrhZdC7cfhi-0DdjR4"


def format_model_10_alert_message(results: List[Dict]) -> Dict:
    """
    Format alert message for Model 10 with required information:
    - List of hospitals selected for alert
    - This month's mortality rate
    - Last 6 months mortality rate
    - Absolute number of deaths this month
    """
    if not results:
        return {
            "text": "✅ *Quality Alert - Model 10*\n\nNo hospitals triggered alerts this week."
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
        model_name = model_id.replace('model', 'Model ')
        return {
            "text": f"✅ *Quality Alert - {model_name}*\n\nNo hospitals triggered alerts."
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
        webhook_url: Optional webhook URL (defaults to GOOGLE_CHAT_WEBHOOK_URL)
    
    Returns:
        True if successful, False otherwise
    """
    if webhook_url is None:
        webhook_url = GOOGLE_CHAT_WEBHOOK_URL
    
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
        results = calculate_model_results(model_id)
        print(f"[Google Chat] Found {len(results)} hospitals with alerts")
        
        # Format message based on model
        if model_id == "model10":
            message = format_model_10_alert_message(results)
        else:
            message = format_generic_alert_message(model_id, results)
        
        # Send message
        success = send_google_chat_message(message, webhook_url)
        
        if success:
            return {
                "success": True,
                "message": f"Alert sent successfully for {model_id}. {len(results)} hospitals with alerts.",
                "hospitals_count": len(results)
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send alert for {model_id}.",
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

