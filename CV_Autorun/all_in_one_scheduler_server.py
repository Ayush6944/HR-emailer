import time
import subprocess
from datetime import datetime, timedelta
import pytz
import threading
from flask import Flask
import os
import requests
import smtplib
from email.mime.text import MIMEText
import csv
import json

# ===================== CONFIGURATION =====================
SCHEDULE_HOUR = 14  # 2 PM
SCHEDULE_MINUTE = 57  # 57 minutes
IST = pytz.timezone('Asia/Kolkata')
LOG_FILE = 'scheduler_audit.log'
SEND_LOG_FILE = 'data/send_log.csv'
ACCOUNTS_FILE = 'email_accounts.json'
EMAILS_FILE = 'emails_to_send.csv'
EMAIL_SUBJECT = 'Job Inquiry from Automated System'
EMAIL_BODY = 'Dear HR,\n\nI am interested in opportunities at your company.\n\nBest regards,\nYour Name'
# ========================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Email Scheduler Status API"

@app.route('/status')
def status():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-10:]
        return '<br>'.join(lines)
    else:
        return "No audit log found."

@app.route('/email_status')
def email_status():
    if os.path.exists(SEND_LOG_FILE):
        with open(SEND_LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-20:]
        return '<br>'.join(lines)
    else:
        return "No email send log found."

def keep_alive():
    """Keep the server alive by pinging itself every minute"""
    while True:
        try:
            base_url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:10000')
            requests.get(f"{base_url}/", timeout=10)
        except Exception as e:
            print(f"[Keep-Alive] Error pinging server: {e}")
        time.sleep(60)

def seconds_until_next_scheduled_time():
    now = datetime.now(IST)
    next_run = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()

def log_audit(message):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def send_email(account, to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = account['sender_email']
        msg['To'] = to_email
        with smtplib.SMTP(account['smtp_server'], account['smtp_port']) as server:
            server.starttls()
            server.login(account['sender_email'], account['sender_password'])
            server.sendmail(account['sender_email'], [to_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)

def run_campaign():
    log_audit('Campaign STARTED')
    try:
        subprocess.run([
            "python", "src/main.py",
            "--resume", "data/resume.pdf",
            "--batch-size", "50",
            "--daily-limit", "500"
        ], check=True)
    except Exception as e:
        log_audit(f'Campaign ERROR: {e}')
    log_audit('Campaign ENDED')

def scheduler_loop():
    while True:
        wait_seconds = seconds_until_next_scheduled_time()
        print(f"[Scheduler] Waiting {wait_seconds/3600:.2f} hours until next run at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} IST...")
        time.sleep(wait_seconds)
        print(f"[Scheduler] Starting email campaign at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} IST!")
        run_campaign()
        time.sleep(60)

if __name__ == "__main__":
    # Start the keep-alive thread
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    # Start the Flask status server
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port) 