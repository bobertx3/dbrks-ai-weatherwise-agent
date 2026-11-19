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
def send_email(recipient: Optional[str] = None, subject: str = "", message: str = "",
               summary: str = "", call_to_action: str = "") -> str:
    """
    Sends a short, styled escalation email via Mailgun. Layout, top to bottom:
    subject heading, `summary`, a yellow `call_to_action` box, then `message` as details.
    Arguments:
      recipient:      (optional) email address(es), comma/semicolon separated.
                      If not provided, falls back to RECIPIENT env var.
      subject:        subject line (also the heading), under ~70 characters
      summary:        1–2 plain sentences: what is at risk and what happens next
      call_to_action: (optional) who to call, e.g. "Call Felix Romero (CardioNova) at +1-602-555-0144"
      message:        concise details (HTML allowed): one line per shipment, then up to 3 next steps
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
        body_all = "\n\n".join(x for x in [summary, call_to_action, message] if x and x.strip())
        text = re.sub(r"<[^>]+>", "", body_all.replace("<br/>", "\n").replace("<br>", "\n"))
        cta = (
            f"<div style='margin:14px 0 4px;background:#fff4c2;border:1px solid #f0d36b;border-left:4px solid #e6ab4b;"
            f"border-radius:8px;padding:10px 12px;font-weight:600;color:#3d2f00;'>&#128222; {_html.escape(call_to_action)}</div>"
            if call_to_action and call_to_action.strip() else ""
        )
        summ = f"<div style='font-size:15px;line-height:1.5;margin:0;'>{summary}</div>" if summary and summary.strip() else ""
        details = (
            f"<div style='margin-top:16px;padding-top:12px;border-top:1px solid {LINE};font-size:13.5px;line-height:1.5;color:#33414e;'>"
            f"<div style='font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{SOFT};margin-bottom:6px;'>Details</div>"
            f"{message}</div>"
            if message and message.strip() else ""
        )
        html = f"""
        <html><body style='margin:0;padding:0;background:#eef2f6;'>
        <table width='100%' cellpadding='0' cellspacing='0' style='background:#eef2f6;'><tr><td align='center' style='padding:18px 10px;'>
        <table width='600' cellpadding='0' cellspacing='0' style='max-width:600px;width:100%;border-radius:10px;overflow:hidden;border:1px solid {LINE};'>
        <tr><td style='background:{PAGE};padding:11px 18px;font-family:{FONT};'>
          <span style='display:inline-block;width:22px;height:22px;line-height:22px;text-align:center;border-radius:6px;background:{CORAL};color:{PAGE};font-weight:800;font-size:12px;vertical-align:middle;'>W</span>
          <span style='color:#dbe4ec;font-size:13.5px;font-weight:700;vertical-align:middle;margin-left:7px;'>MedTech WeatherWise Agent</span>
          <span style='float:right;margin-top:2px;color:{CORAL};border:1px solid {CORAL};border-radius:999px;padding:1px 8px;font-size:9.5px;font-weight:700;letter-spacing:.12em;'>ESCALATION</span>
        </td></tr>
        <tr><td style='background:{PANEL};padding:16px 20px 18px;font-family:{FONT};color:{INK};'>
          <div style='font-size:17px;font-weight:700;line-height:1.3;margin:0 0 8px 0;'>{_html.escape(subject)}</div>
          {summ}{cta}{details}
        </td></tr>
        <tr><td style='background:#f7f9fb;border-top:1px solid {LINE};padding:9px 20px;font-family:{FONT};font-size:11px;color:{SOFT};'>
          Sent by the WeatherWise agent · Synthetic demo data
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