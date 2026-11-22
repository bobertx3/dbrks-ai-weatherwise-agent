from twilio.rest import Client
from langchain_core.tools import tool
import os
import re

# Twilio credentials, set via environment vars. Two supported forms:
#   - API key:  SMS_ACCOUNT_SID="SK...", SMS_AUTH_TOKEN=<API key secret>, SMS_ACCOUNT_ID="AC..."
#   - Account:  SMS_ACCOUNT_SID="AC...", SMS_AUTH_TOKEN=<account Auth Token>
SMS_ACCOUNT_SID = os.getenv("SMS_ACCOUNT_SID")
SMS_AUTH_TOKEN = os.getenv("SMS_AUTH_TOKEN")
SMS_ACCOUNT_ID = os.getenv("SMS_ACCOUNT_ID")  # AC... account SID; recommended with an SK... API key

# 📱 Always send from this number
FROM_NUMBER = "+18773559479"

# Greeting prepended to every SMS the agent sends
SMS_GREETING = "Hi from the WeatherWise Agent."

# Sentence boundary: ". " / "; " / "! " / "? " followed by a capital, digit or symbol.
# Decimals like "48.5°F" never match (no space after the dot).
_SENTENCE_BREAK = re.compile(r"(?<=[.;!?])\s+(?=[A-Z0-9(•\-–—])")


def format_sms(message: str) -> str:
    """Make agent SMS readable on a phone: one idea per line.

    If the agent already used line breaks, keep them (trimmed). Otherwise split a
    run-on paragraph at sentence/clause boundaries.
    """
    text = (message or "").strip()
    if "\n" in text:
        lines = [ln.strip() for ln in text.splitlines()]
    else:
        lines = [part.strip().rstrip(";") for part in _SENTENCE_BREAK.split(text)]
    # collapse runs of blank lines
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


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
      message:   Short multi-line summary, one item per line (see TEXTER format in the
                 system prompt). Run-on text is split into lines automatically.
    """
    try:
        client = _twilio_client()
        msg = client.messages.create(
            body=f"{SMS_GREETING}\n\n{format_sms(message)}",
            from_=FROM_NUMBER,
            to=to_number
        )
        return f"✅ SMS sent to {to_number} (SID={msg.sid})"
    except Exception as e:
        return f"❌ Error sending SMS: {type(e).__name__}: {e}"

# ---------------------------------------------------------------------------
# Networking / "let's connect" text: one SMS with the greeting and LinkedIn link
# ---------------------------------------------------------------------------
# Override with LINKEDIN_URL to point at someone else's profile.
LINKEDIN_URL = os.getenv("LINKEDIN_URL", "https://www.linkedin.com/in/ybbob/")

CONNECT_GREETING = "Hi from the WeatherWise Agent! Great meeting you."


def _e164(number: str) -> str:
    """Normalize US numbers like '3019085817' or '(301) 908-5817' to '+13019085817'."""
    if number.strip().startswith("+"):
        return "+" + "".join(c for c in number if c.isdigit())
    digits = "".join(c for c in number if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return number


@tool("send_connect_sms", return_direct=True)
def send_connect_sms(to_number: str, note: str = "") -> str:
    """
    Sends one networking text: a greeting plus a link to connect on LinkedIn.
    Use ONLY for networking / social requests such as "great meeting you at
    Databricks World Tour / DAIWT NYC", "let's connect", or "send my LinkedIn".
    Do NOT use for shipment, weather, or risk updates (use send_sms for those).

    Arguments:
      to_number: Recipient phone number, E.164 preferred (e.g. '+13019085817')
      note:      Optional short personal line added after the greeting
    """
    to_number = _e164(to_number)
    try:
        client = _twilio_client()
        parts = [CONNECT_GREETING]
        if note and note.strip():
            parts.append(note.strip())
        parts.append(f"Let's connect on LinkedIn:\n{LINKEDIN_URL}")
        msg = client.messages.create(body="\n\n".join(parts), from_=FROM_NUMBER, to=to_number)
        return f"✅ Connect text with LinkedIn link sent to {to_number} (SID={msg.sid})"
    except Exception as e:
        return f"❌ Error sending connect SMS: {type(e).__name__}: {e}"
