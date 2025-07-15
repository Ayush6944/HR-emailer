import time
import subprocess
from datetime import datetime, timedelta
import pytz
import threading
from flask import Flask, send_file
import os
import requests
from typing import Optional

# ===================== CONFIGURATION =====================
SCHEDULE_HOUR = 17  # 10 AM (used after first run)
SCHEDULE_MINUTE = 46  # 20 minutes (used after first run)
IST = pytz.timezone('Asia/Kolkata')
LOG_FILE = 'scheduler_audit.log'
# ========================================================

app = Flask(__name__)

last_run_info: dict[str, Optional[str]] = {'start': None, 'end': None, 'error': None}

@app.route('/')
def home():
    return '''
    <html>
    <head>
        <title>Email Campaign Scheduler</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f7f7f7; margin: 0; }
            .navbar {
                background: #2c3e50;
                padding: 1em 2em;
                display: flex;
                align-items: center;
            }
            .navbar a {
                color: #ecf0f1;
                text-decoration: none;
                margin-right: 2em;
                font-weight: bold;
                font-size: 1.1em;
                transition: color 0.2s;
            }
            .navbar a:hover {
                color: #f39c12;
            }
            .container {
                max-width: 600px;
                margin: 3em auto;
                background: #fff;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(44,62,80,0.08);
                padding: 2em 2.5em;
                text-align: center;
            }
            h1 { color: #2c3e50; }
            p { color: #555; }
        </style>
    </head>
    <body>
        <div class="navbar">
            <a href="/">Home</a>
            <a href="/status">Status Log</a>
            <a href="/dashboard">Dashboard</a>
            <a href="/download_log">Download Log</a>
        </div>
        <div class="container">
            <h1>Welcome to the Email Campaign Scheduler</h1>
            <p>Use the navigation bar above to view campaign status, logs, and analytics.</p>
            <p style="color:#888; font-size:0.95em;">Server is running and ready to manage your automated email campaigns.</p>
            <hr style="margin:2em 0;">
            <p><b>Download your full email send log as a CSV file:</b><br>
            <a href="/download_log" style="color:#2980b9; text-decoration:underline;">Download send_log.csv</a></p>
            <h4>created By - Ayush Srivastava visit-<a href="https://portfolio-ayush6944s-projects.vercel.app/">here</a></h4>
        </div>
    </body>
    </html>
    '''

@app.route('/status')
def status():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-10:]
        return '<br>'.join(lines)
    else:
        return "No audit log found."

@app.route('/dashboard')
def dashboard():
    import sqlite3
    from datetime import datetime, timedelta
    db_path = os.path.join(os.path.dirname(__file__), 'data/companies.db')
    total_sent = 0
    total_pending = 0
    last_3_days = []
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # Total sent
            cursor.execute("SELECT COUNT(*) FROM companies WHERE sent_timestamp IS NOT NULL")
            total_sent = cursor.fetchone()[0]
            # Total pending
            cursor.execute("SELECT COUNT(*) FROM companies WHERE sent_timestamp IS NULL")
            total_pending = cursor.fetchone()[0]
            # Last 3 days sent
            today = datetime.now().date()
            for i in range(3):
                day = today - timedelta(days=i)
                cursor.execute("SELECT COUNT(*) FROM companies WHERE date(sent_timestamp) = ?", (day.isoformat(),))
                count = cursor.fetchone()[0]
                last_3_days.append({'date': day.strftime('%Y-%m-%d'), 'count': count})
    except Exception as e:
        return f"<h2>Error loading dashboard: {e}</h2>"
    html = f"""
    <html>
    <head><title>Email Campaign Dashboard</title></head>
    <body>
        <h1>Email Campaign Dashboard</h1>
        <p><b>Total Sent Emails:</b> {total_sent}</p>
        <p><b>Total Pending Emails:</b> {total_pending}</p>
        <h2>Last 3 Days Email Sent</h2>
        <table border='1' cellpadding='5'>
            <tr><th>Date</th><th>Emails Sent</th></tr>
            {''.join(f'<tr><td>{d["date"]}</td><td>{d["count"]}</td></tr>' for d in last_3_days)}
        </table>
    </body>
    </html>
    """
    return html

@app.route('/download_log')
def download_log():
    import os
    log_path = os.path.join(os.path.dirname(__file__), 'data/send_log.csv')
    if not os.path.exists(log_path):
        return '<h2>send_log.csv not found.</h2>', 404
    return send_file(log_path, as_attachment=True, download_name='send_log.csv')

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

def run_campaign():
    last_run_info['start'] = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    last_run_info['error'] = None
    log_audit('Campaign STARTED')
    try:
        subprocess.run([
            "python", "src/main.py",
            "--resume", "data/Ayush_Srivastava.pdf",
            "--batch-size", "5",
            "--daily-limit", "751"
        ], check=True)
    except Exception as e:
        last_run_info['error'] = str(e)
        log_audit(f'Campaign ERROR: {e}')
    last_run_info['end'] = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    log_audit('Campaign ENDED')

def scheduler_loop():
    while True:
        wait_seconds = seconds_until_next_scheduled_time()
        print(f"[Scheduler] Waiting {wait_seconds/3600:.2f} hours until next run at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} IST...")
        time.sleep(wait_seconds)
        print(f"[Scheduler] Starting campaign at {datetime.now(IST).strftime('%H:%M:%S')} IST!")
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