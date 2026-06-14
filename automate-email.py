import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from time import sleep
import json
import datetime
import os
from zoneinfo import ZoneInfo
import streamlit as st
from dotenv import load_dotenv

IST = ZoneInfo("Asia/Kolkata")

load_dotenv()

try:
    STREAMLIT_SECRETS = dict(st.secrets)
except Exception:
    STREAMLIT_SECRETS = {}

def get_secret(key):
    # Prefer Streamlit secrets, then environment variables (.env or OS env)
    value = STREAMLIT_SECRETS.get(key)
    if value:
        return value, "Streamlit secrets"

    value = os.getenv(key)
    if value:
        return value, ".env / environment"

    return None, "missing"

EMAIL_ADDRESS, EMAIL_ADDRESS_SOURCE = get_secret("EMAIL_ADDRESS")
EMAIL_ADDRESS_PASSWORD, EMAIL_ADDRESS_PASSWORD_SOURCE = get_secret("EMAIL_ADDRESS_PASSWORD")
RECEPIENT_EMAIL_ADDRESS, RECEPIENT_EMAIL_ADDRESS_SOURCE = get_secret("RECEPIENT_EMAIL_ADDRESS")

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
LOG_FILE = "email_run.log"


def load_log_entries():
    if not os.path.exists(LOG_FILE):
        return []

    with open(LOG_FILE, "r", encoding="utf-8") as file:
        return [line.rstrip("\n") for line in file if line.strip()]


def append_log_entry(message):
    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(message + "\n")

def format_duration(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m {remaining_seconds}s"
    if minutes:
        return f"{minutes}m {remaining_seconds}s"
    return f"{remaining_seconds}s"

def send_email(recipient_email, subject, body, log_fn=None):
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

        if log_fn:
            log_fn(f"Email sent successfully to {recipient_email} with subject: {subject}")
        return True
    except Exception as e:
        if log_fn:
            log_fn(f"Error sending email to {recipient_email} with subject {subject}: {e}")
        return False

def parse_schedule(email_content):
    schedule = []

    for scheduled_time, payload in sorted(email_content.items()):
        if not isinstance(payload, (list, tuple)) or len(payload) != 2:
            raise ValueError(f"Invalid email content for {scheduled_time}. Expected [subject, body].")

        subject, body = payload
        time_value = datetime.datetime.strptime(scheduled_time, "%H:%M").time()
        schedule.append((scheduled_time, time_value, subject, body))

    return schedule

def wait_for_target(target_datetime, subject, scheduled_time, status_box, countdown_box, log_fn):
    while True:
        now = datetime.datetime.now(IST)

        if now.strftime("%H:%M") == scheduled_time:
            countdown_box.metric("Countdown to next mail", "Now", f"Scheduled {scheduled_time}")
            status_box.info(f"Sending '{subject}' now.")
            return

        seconds_remaining = int((target_datetime - now).total_seconds())

        if seconds_remaining <= 0:
            countdown_box.metric("Countdown to next mail", "Now", f"Scheduled {scheduled_time}")
            status_box.info(f"Sending '{subject}' now.")
            return

        countdown_box.metric(
            "Countdown to next mail",
            format_duration(seconds_remaining),
            f"Next mail at {scheduled_time}",
        )
        status_box.write(f"Connected and working. Waiting to send '{subject}' at {scheduled_time}.")
        sleep(1)
        
def main():
    st.set_page_config(page_title="Automated Email Scheduler", layout="wide")
    st.title("Automated Email Scheduler")
    st.caption("Live connection status, sent-mail logs, and countdown updates appear here while the app is running.")

    if "scheduler_started_at" not in st.session_state:
        st.session_state["scheduler_started_at"] = datetime.datetime.now(IST)
    scheduler_started_at = st.session_state["scheduler_started_at"]

    EMAIL_CONTENT = {}
    log_entries = load_log_entries()
    status_box = st.empty()
    countdown_box = st.empty()
    log_box = st.empty()

    def render_logs():
        recent_logs = log_entries[-40:]
        log_box.code("\n".join(recent_logs) if recent_logs else "Waiting for events...", language="text")

    def add_log(message):
        timestamp = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z")
        entry = f"[{timestamp}] {message}"
        log_entries.append(entry)
        append_log_entry(entry)
        del log_entries[:-80]
        render_logs()

    def render_secret_status():
        secret_status = {
            "EMAIL_ADDRESS": EMAIL_ADDRESS_SOURCE,
            "EMAIL_ADDRESS_PASSWORD": EMAIL_ADDRESS_PASSWORD_SOURCE,
            "RECEPIENT_EMAIL_ADDRESS": RECEPIENT_EMAIL_ADDRESS_SOURCE,
        }
        status_lines = [f"{key}: {source}" for key, source in secret_status.items()]
        st.info("Secret loading source\n\n" + "\n".join(status_lines))

    with open('email_content.json', 'r') as file:
        EMAIL_CONTENT = json.load(file)

    required_secrets = {
        "EMAIL_ADDRESS": EMAIL_ADDRESS,
        "EMAIL_ADDRESS_PASSWORD": EMAIL_ADDRESS_PASSWORD,
        "RECEPIENT_EMAIL_ADDRESS": RECEPIENT_EMAIL_ADDRESS,
    }
    missing_secrets = [name for name, value in required_secrets.items() if not value]
    if missing_secrets:
        st.error(
            "Missing required secrets: " + ", ".join(missing_secrets)
            + ". Add them in Streamlit Cloud Secrets or a local .streamlit/secrets.toml file."
        )
        st.stop()

    try:
        schedule = parse_schedule(EMAIL_CONTENT)
    except ValueError as error:
        st.error(str(error))
        st.stop()

    if not schedule:
        st.warning("No scheduled emails found in email_content.json.")
        st.stop()

    render_secret_status()
    st.success(f"Scheduler started at: {scheduler_started_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    status_box.write("Connected. Secrets loaded and scheduler is running.")
    st.write(f"Scheduled emails: {len(schedule)}")
    add_log(f"Scheduler started successfully at {scheduler_started_at.strftime('%Y-%m-%d %H:%M:%S %Z')}.")

    now = datetime.datetime.now(IST)
    current_date = now.date()
    start_index = None

    for index, (scheduled_time, _, subject, _) in enumerate(schedule):
        if scheduled_time >= now.strftime("%H:%M"):
            start_index = index
            break

    if start_index is None:
        start_index = 0
        current_date = current_date + datetime.timedelta(days=1)

    sent_count = 0
    render_logs()

    while True:
        for offset in range(len(schedule)):
            index = (start_index + offset) % len(schedule)
            scheduled_time, time_value, subject, body = schedule[index]
            target_date = current_date if (start_index + offset) < len(schedule) else current_date + datetime.timedelta(days=1)
            target_datetime = datetime.datetime.combine(target_date, time_value, tzinfo=IST)

            if target_datetime <= datetime.datetime.now(IST) and datetime.datetime.now(IST).strftime("%H:%M") != scheduled_time:
                continue

            next_mail_label = f"{scheduled_time} - {subject}"
            st.write(f"Next mail: {next_mail_label}")
            add_log(f"Next scheduled mail: {next_mail_label}")
            wait_for_target(target_datetime, subject, scheduled_time, status_box, countdown_box, add_log)

            if send_email(RECEPIENT_EMAIL_ADDRESS, subject, body, add_log):
                sent_count += 1
                st.write(f"Sent mails: {sent_count}")
                status_box.write(f"Sent '{subject}' to {RECEPIENT_EMAIL_ADDRESS}.")
                add_log(f"Sent '{subject}' to {RECEPIENT_EMAIL_ADDRESS}.")

        current_date = current_date + datetime.timedelta(days=1)
        start_index = 0
            
if __name__ == "__main__":
    main()