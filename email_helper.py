import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_ADDRESS, EMAIL_PASSWORD

def send_email(subject, message):
    """Send email notification via Gmail"""
    
    sender = EMAIL_ADDRESS
    password = EMAIL_PASSWORD
    receiver = EMAIL_ADDRESS  # Send to yourself
    
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = subject
    
    msg.attach(MIMEText(message, 'plain'))
    
    try:
        # Use Gmail SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        
        print("✅ Email notification sent!")
        return True
        
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False