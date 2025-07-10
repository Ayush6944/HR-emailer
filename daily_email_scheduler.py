import time
import subprocess
from datetime import datetime, timedelta
import pytz

# Set the timezone to IST
IST = pytz.timezone('Asia/Kolkata')

LOG_FILE = 'scheduler_audit.log'


def seconds_until_next_5am_ist():
    now = datetime.now(IST)
    next_run = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if now >= next_run:
        # If it's already past 5am today, schedule for tomorrow
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
        "--daily-limit", "1251"
    ], cwd="AutoEmailer/CV_Autorun")
    log_audit('Campaign ENDED')

if __name__ == "__main__":
    while True:
        # Always wait until next 5:00 AM IST
        wait_seconds = seconds_until_next_5am_ist()
        print(f"Waiting {wait_seconds/3600:.2f} hours until next run at 5:00 AM IST...")
        time.sleep(wait_seconds)
        print("Starting email campaign at 5:00 AM IST!")
        run_campaign()
        # Wait a minute to avoid tight loop if campaign is very fast
        time.sleep(60) 