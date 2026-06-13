import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from time import sleep
import json
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_ADDRESS_PASSWORD = os.environ.get('EMAIL_ADDRESS_PASSWORD')
RECEPIENT_EMAIL_ADDRESS = os.environ.get('RECEPIENT_EMAIL_ADDRESS')


SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

def send_email(recipient_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_ADDRESS_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())            

        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
        
def main():
    EMAIL_CONTENT = {}
    
    with open('email_content.json', 'r') as file:
        EMAIL_CONTENT = json.load(file)
        
    prev_time = None
    
    hours = list(EMAIL_CONTENT.keys())
    
    for i in range(len(EMAIL_CONTENT)):
        current_time = datetime.datetime.now().strftime("%H:%M")
        
        if current_time == hours[i] and current_time != prev_time:
            subject, body = EMAIL_CONTENT[hours[i]]
            send_email(RECEPIENT_EMAIL_ADDRESS, subject, body)
            print(current_time, hours[i], subject, body)
            prev_time = current_time
            
            if i != len(EMAIL_CONTENT)-1:
                next_key = hours[i+1]
                next_time = datetime.datetime.strptime(next_key, "%H:%M")
                prev_time_dt = datetime.datetime.strptime(prev_time, "%H:%M")
                sleep_duration = (next_time - prev_time_dt).total_seconds()
                print(f"Sleeping for {sleep_duration} seconds until next email.")
                sleep(sleep_duration)
            
if __name__ == "__main__":
    main()