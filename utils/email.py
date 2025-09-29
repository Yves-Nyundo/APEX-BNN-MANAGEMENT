import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from config import Config
import os

def send_pdf_email(recipient, subject, body, pdf_bytes, filename):
    msg = MIMEMultipart()
    msg['From'] = Config.MAIL_DEFAULT_SENDER
    msg['To'] = recipient
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename={filename}')
    msg.attach(part)

    try:
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
        server.starttls()
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(Config.MAIL_USERNAME, recipient, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False