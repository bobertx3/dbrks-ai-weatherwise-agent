import os, re, requests
from langchain_core.tools import tool
from typing import Optional

# ── Env vars ──────────────────────────────────────────────
MAILGUN_API_URL = os.environ.get("MAILGUN_API_URL")       # full endpoint
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")       # e.g. key-xxxxxx
SENDER          = os.environ.get("SENDER")
RECIPIENT_ENV   = os.environ.get("RECIPIENT")
AGENT_NAME   = os.environ.get("AGENT_NAME")

# ── Styles ────────────────────────────────────────────────
BG, INK, RED, BLUE, DIV = "#f5f7fb", "#222", "#e24a4a", "#1e63c6", "#e6edf6"

def _as_list(value: Optional[str]):
    """Split comma/semicolon-separated recipients into a clean list."""
    if not value:
        return []
    return [v.strip() for v in re.split(r"[;,]", value) if v.strip()]

@tool("send_email", return_direct=True)
def send_email(recipient: Optional[str] = None, subject: str = "", message: str = "") -> str:
    """
    Sends a styled HTML email via Mailgun.
    Arguments:
      recipient: (optional) email address(es), comma/semicolon separated.
                 If not provided, falls back to RECIPIENT env var.
      subject:   subject line
      message:   message body (HTML allowed)
    """
    try:
        # --- validate config
        missing = [k for k, v in {
            "MAILGUN_API_URL": MAILGUN_API_URL,
            "MAILGUN_API_KEY": MAILGUN_API_KEY,
            "SENDER": SENDER,
        }.items() if not v]
        if missing:
            return f"❌ Missing required env vars: {', '.join(missing)}"

        # --- choose recipient(s)
        to_list = _as_list(recipient) or _as_list(RECIPIENT_ENV)
        if not to_list:
            return "❌ No recipient provided (argument or RECIPIENT env)."

        # --- plain text + html
        text = re.sub(r"<[^>]+>", "", message.replace("<br/>", "\n").replace("<br>", "\n"))
        html = f"""
        <html><body style='margin:0;padding:0;background:{BG};'>
        <table width='100%' style='background:{BG};'><tr><td align='center' style='padding:24px;'>
        <table width='640' style='max-width:640px;background:#fff;border-radius:14px;box-shadow:0 6px 18px rgba(0,0,0,.06);'>
        <tr><td style='padding:28px 26px;font-family:Segoe UI,Roboto,Arial,sans-serif;color:{INK};font-size:16px;'>
        <div style='font-size:34px;font-weight:800;color:{RED};'>Jackson &amp; Jackson</div>
        <div style='display:inline-block;background:{BLUE};color:#fff;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;margin:6px 0 14px 0;'>UPDATE</div>
        <hr style='border:none;border-top:1px solid {DIV};margin:10px 0 18px 0;'>
        <div>{message}</div>
        <hr style='border:none;border-top:1px solid {DIV};margin:24px 0 12px 0;'>
        <p style='font-size:12px;color:#667;text-align:center;'>© Jackson &amp; Jackson •
        <a href='mailto:{SENDER}' style='color:{BLUE};text-decoration:none;'>{SENDER}</a></p>
        </td></tr></table></td></tr></table></body></html>""".strip()

        # --- send
        data = {
            "from": f"{AGENT_NAME}<{SENDER}>",
            "to": to_list,
            "subject": subject,
            "text": text,
            "html": html,
            "h:Reply-To": SENDER,
        }

        resp = requests.post(MAILGUN_API_URL, auth=("api", MAILGUN_API_KEY), data=data, timeout=20)

        if resp.ok:
            try:
                msg_id = resp.json().get("id", "unknown")
            except Exception:
                msg_id = "unknown"
            return f"✅ Email sent to {', '.join(to_list)} (id={msg_id})"
        else:
            return f"❌ Email error {resp.status_code}: {resp.text[:400]}"

    except Exception as e:
        return f"❌ Error sending email: {type(e).__name__}: {e}"