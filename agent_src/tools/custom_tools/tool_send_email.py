import os, re, requests, html as _html
from langchain_core.tools import tool
from typing import Optional

# ── Env vars ──────────────────────────────────────────────
MAILGUN_API_URL = os.environ.get("MAILGUN_API_URL")       # full endpoint
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")       # e.g. key-xxxxxx
SENDER          = os.environ.get("SENDER")
RECIPIENT_ENV   = os.environ.get("RECIPIENT")
AGENT_NAME   = os.environ.get("AGENT_NAME")

# ── Styles (mirror the app: navy page, teal + coral accents) ──
PAGE, PANEL, INK, SOFT, TEAL, CORAL, LINE = "#0a1017", "#ffffff", "#1b2733", "#5b6f82", "#2bb3a8", "#f2725e", "#e3e9ef"
FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "WeatherWise Agent")
FONT = "-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"

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
        <html><body style='margin:0;padding:0;background:#eef2f6;'>
        <table width='100%' cellpadding='0' cellspacing='0' style='background:#eef2f6;'><tr><td align='center' style='padding:24px 12px;'>
        <table width='640' cellpadding='0' cellspacing='0' style='max-width:640px;width:100%;border-radius:12px;overflow:hidden;border:1px solid {LINE};'>
        <tr><td style='background:{PAGE};padding:16px 22px;font-family:{FONT};'>
          <span style='display:inline-block;width:26px;height:26px;line-height:26px;text-align:center;border-radius:7px;background:{CORAL};color:{PAGE};font-weight:800;font-size:14px;vertical-align:middle;'>W</span>
          <span style='color:#dbe4ec;font-size:15px;font-weight:700;vertical-align:middle;margin-left:8px;'>MedTech WeatherWise Agent</span>
          <span style='float:right;margin-top:3px;color:{CORAL};border:1px solid {CORAL};border-radius:999px;padding:2px 9px;font-size:10px;font-weight:700;letter-spacing:.12em;'>ESCALATION</span>
          <div style='height:2px;background:{TEAL};margin-top:14px;width:48px;border-radius:2px;'></div>
        </td></tr>
        <tr><td style='background:{PANEL};padding:22px 24px;font-family:{FONT};color:{INK};font-size:15px;line-height:1.55;'>
          <div style='font-size:18px;font-weight:700;margin:0 0 12px 0;'>{_html.escape(subject)}</div>
          <div>{message}</div>
        </td></tr>
        <tr><td style='background:#f7f9fb;border-top:1px solid {LINE};padding:12px 24px;font-family:{FONT};font-size:11.5px;color:{SOFT};'>
          Sent by the WeatherWise agent · Temperature-controlled logistics · Synthetic demo data
        </td></tr>
        </table></td></tr></table></body></html>""".strip()

        # --- send
        data = {
            "from": f"{FROM_NAME} <{SENDER}>",
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