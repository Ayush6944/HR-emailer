import time
import subprocess
from datetime import datetime, timedelta
import pytz
import threading
from flask import Flask
import os

# Set the timezone to IST
IST = pytz.timezone('Asia/Kolkata')
LOG_FILE = 'scheduler_audit.log'

app = Flask(__name__)

@app.route('/')
def home():
    return "Email Scheduler Status API"

@app.route('/status')
def status():
    log_path = LOG_FILE
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-10:]  # last 10 lines
        return '<br>'.join(lines)
    else:
        return "No audit log found."

def seconds_until_next_5am_ist():
    now = datetime.now(IST)
    next_run = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    return (next_run - now).total_seconds()

def log_audit(message):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def run_campaign():
    log_audit('Campaign STARTED')
    subprocess.run([
        "python", "src/main.py",
        "--resume", "data/Ayush.pdf",
        "--batch-size", "20",
        "--daily-limit", "1350"
    ], cwd="AutoEmailer/CV_Autorun")
    log_audit('Campaign ENDED')

def scheduler_loop():
    while True:
        wait_seconds = seconds_until_next_5am_ist()
        print(f"[Scheduler] Waiting {wait_seconds/3600:.2f} hours until next run at 5:00 AM IST...")
        time.sleep(wait_seconds)
        print("[Scheduler] Starting email campaign at 5:00 AM IST!")
        run_campaign()
        time.sleep(60)

if __name__ == "__main__":
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    # Start the Flask status server
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port) 