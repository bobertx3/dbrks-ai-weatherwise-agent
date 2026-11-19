from twilio.rest import Client
from langchain_core.tools import tool
import os

# Twilio credentials, set via environment vars. Two supported forms:
#   - API key:  SMS_ACCOUNT_SID="SK...", SMS_AUTH_TOKEN=<API key secret>, SMS_ACCOUNT_ID="AC..."
#   - Account:  SMS_ACCOUNT_SID="AC...", SMS_AUTH_TOKEN=<account Auth Token>
SMS_ACCOUNT_SID = os.getenv("SMS_ACCOUNT_SID")
SMS_AUTH_TOKEN = os.getenv("SMS_AUTH_TOKEN")
SMS_ACCOUNT_ID = os.getenv("SMS_ACCOUNT_ID")  # AC... account SID; recommended with an SK... API key

# 📱 Always send from this number
FROM_NUMBER = "+18773559479"

# Greeting prepended to every SMS the agent sends
SMS_GREETING = "Hi from the WeatherWise Agent. Welcome to DAIWT NYC!"

def _twilio_client() -> Client:
    """Same selection as tests/manually_test_tools.ipynb."""
    if (SMS_ACCOUNT_SID or "").startswith("SK") and SMS_ACCOUNT_ID:
        return Client(SMS_ACCOUNT_SID, SMS_AUTH_TOKEN, SMS_ACCOUNT_ID)
    # AC... SID + Auth Token, or an SK... key on its own (also accepted by Twilio's client).
    return Client(SMS_ACCOUNT_SID, SMS_AUTH_TOKEN)


@tool("send_sms", return_direct=True)
def send_sms(to_number: str, message: str) -> str:
    """
    Sends an SMS message using Twilio.

    Arguments:
      to_number: Recipient phone number in E.164 format (e.g. '+13019085817')
      message:   Text message body (max ~1600 characters)
    """
    try:
        client = _twilio_client()
        msg = client.messages.create(
            body=f"{SMS_GREETING}\n{message}",
            from_=FROM_NUMBER,
            to=to_number
        )
        return f"✅ SMS sent to {to_number} (SID={msg.sid})"
    except Exception as e:
        return f"❌ Error sending SMS: {type(e).__name__}: {e}"