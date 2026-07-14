import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = "localhost"
SMTP_PORT = 1025
FROM_ADDRESS = "it-security@phishguard-sim.local"


def send_email(to_address, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_ADDRESS
    msg["To"] = to_address

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.sendmail(FROM_ADDRESS, to_address, msg.as_string())