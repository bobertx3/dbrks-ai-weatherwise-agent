# send_sms.py
from twilio.rest import Client
from langchain_core.tools import tool
import os

# Twilio credentials (replace with your own or set via environment vars)
SMS_ACCOUNT_SID = os.getenv("SMS_ACCOUNT_SID")
SMS_AUTH_TOKEN = os.getenv("SMS_AUTH_TOKEN")

# 📱 Always send from this number
FROM_NUMBER = "+18773559479"

@tool("send_sms", return_direct=True)
def send_sms(to_number: str, message: str) -> str:
    """
    Sends an SMS message using Twilio.

    Arguments:
      to_number: Recipient phone number in E.164 format (e.g. '+13019085817')
      message:   Text message body (max ~1600 characters)
    """
    try:
        client = Client(SMS_ACCOUNT_SID, SMS_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=FROM_NUMBER,
            to=to_number
        )
        return f"✅ SMS sent to {to_number} (SID={msg.sid})"
    except Exception as e:
        return f"❌ Error sending SMS: {type(e).__name__}: {e}"