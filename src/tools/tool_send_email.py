# send_email.py
import boto3, re
from langchain_core.tools import tool

AWS_REGION = "us-east-1"
AWS_ACCESS_KEY = "AKIAYS2NRPZA23IURJ67"
AWS_SECRET_KEY = "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"
SENDER = "robert@datakafe.com"
BG, INK, RED, BLUE, DIV = "#f5f7fb", "#222", "#e24a4a", "#1e63c6", "#e6edf6"

@tool("send_email", return_direct=True)
def send_email(recipient: str, subject: str, message: str) -> str:
    """
    Sends a styled HTML email using AWS SES.
    Arguments:
      recipient: Target email address (must be verified in SES sandbox)
      subject: Email subject line
      message: Email body text (HTML allowed)
    """
    try:
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
        <p style='font-size:12px;color:#667;text-align:center;'>© Jackson &amp; Jackson • Sent via AWS SES •
        <a href='mailto:{SENDER}' style='color:{BLUE};text-decoration:none;'>{SENDER}</a></p>
        </td></tr></table></td></tr></table></body></html>"""

        ses = boto3.client("ses",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY
        )

        resp = ses.send_email(
            Source=SENDER,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Html": {"Data": html},
                    "Text": {"Data": text},
                },
            },
        )
        return f"✅ Email sent to {recipient} (MessageId={resp['MessageId']})"
    except Exception as e:
        return f"❌ Error sending email: {type(e).__name__}: {e}"