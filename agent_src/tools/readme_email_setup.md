# 📧 AWS SES Setup (for Databricks Agent Email Tool)

## 1. Verify Your Email Identity
- Go to [AWS SES Console](https://us-east-1.console.aws.amazon.com/ses/home?region=us-east-1#/verified-identities).  
- Click **“Create Identity” → “Email address”** and enter your sender (e.g. `robert@datakafe.com`).  
- Confirm via the verification email.  
> 🔹 In sandbox mode, verify **both sender and recipient** emails.  
> To move to production: [Request Production Access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html)

---

## 2. Create IAM Credentials
- In [IAM Console](https://console.aws.amazon.com/iamv2/home#/users), create a user (e.g. `databricks-ses-agent`).  
- Attach the policy:  
  ```
  AmazonSESFullAccess
  ```
- Download your:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`

---

## 3. Configure in Databricks
Store credentials securely using **Databricks Secrets**:
```python
AWS_REGION = "us-east-1"
AWS_ACCESS_KEY = dbutils.secrets.get("aws", "ses_access_key")
AWS_SECRET_KEY = dbutils.secrets.get("aws", "ses_secret_key")
```
> Docs: [Databricks Secrets](https://docs.databricks.com/en/security/secrets/secrets.html)

---

## 4. Send a Test Email
```python
import boto3
ses = boto3.client("ses",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY)

resp = ses.send_email(
    Source="robert@datakafe.com",
    Destination={"ToAddresses": ["robert@datakafe.com"]},
    Message={
        "Subject": {"Data": "SES Test Email"},
        "Body": {"Text": {"Data": "This is a test email sent via AWS SES!"}},
    })
print("✅ Sent:", resp["MessageId"])
```

---

## 5. References
- 📘 [AWS SES Developer Guide](https://docs.aws.amazon.com/ses/latest/dg/Welcome.html)  
- 🔐 [Managing Access to SES](https://docs.aws.amazon.com/ses/latest/dg/control-user-access.html)  
- 🧰 [boto3 SES Docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ses.html)

---
© 2025 — *Authored by Robert “Bobby” Leach*
