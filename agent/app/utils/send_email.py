import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header


def _clean_text(text: str) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("\xa0", " ")
        .replace("\u00a0", " ")
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
    )


def send_email(to_email, subject, body):
    to_email = _clean_text(to_email)
    gmail_user = _clean_text(os.getenv("GMAIL_USER"))
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        raise ValueError("Missing GMAIL_USER or GMAIL_APP_PASSWORD environment variables")

    clean_subject = _clean_text(subject)
    clean_body = _clean_text(body)

    msg = MIMEText(clean_body, _subtype="plain", _charset="utf-8")
    msg["From"] = gmail_user
    msg["To"] = to_email
    msg["Subject"] = Header(clean_subject, "utf-8").encode()

    try:
        print(f"📧 SMTP CONNECT → {gmail_user}")
        print(f"📧 CLEAN TO → {repr(to_email)}")
        print(f"📧 BODY PREVIEW → {repr(clean_body[:200])}")

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.sendmail(
                gmail_user,
                [to_email],
                msg.as_bytes().decode("utf-8", errors="ignore")
            )

        print("✅ SMTP EMAIL SENT")

    except Exception as e:
        print("❌ SMTP ERROR:", str(e))
        raise

    return "Email sent"