import time
import subprocess
from datetime import datetime, timedelta
import pytz
import threading
from flask import Flask, send_file, request, redirect, url_for, session, render_template_string
import os
import requests
from typing import Optional
from functools import wraps

# ===================== CONFIGURATION =====================
SCHEDULE_HOUR = 9  # 10 AM (used after first run)
SCHEDULE_MINUTE = 45  # 20 minutes (used after first run)
IST = pytz.timezone('Asia/Kolkata')
LOG_FILE = 'scheduler_audit.log'
# ========================================================

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_this'  # Needed for session management

# Hardcoded credentials
USERNAME = 'ayush'
PASSWORD = 'admin'

# Modern color palette
PRIMARY_COLOR = '#1a237e'  # Indigo
ACCENT_COLOR = '#ffb300'   # Amber
BG_COLOR = '#f5f6fa'       # Light gray
CARD_COLOR = '#fff'
TEXT_COLOR = '#222'

# Base HTML template for reuse
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: ''' + BG_COLOR + '''; margin: 0; }
        .navbar {
            background: ''' + PRIMARY_COLOR + ''';
            padding: 1em 2em;
            display: flex;
            align-items: center;
        }
        .navbar-logo {
            height: 36px;
            margin-right: 1.5em;
            vertical-align: middle;
        }
        .navbar a {
            color: #fff;
            text-decoration: none;
            margin-right: 2em;
            font-weight: 500;
            font-size: 1.1em;
            transition: color 0.2s;
        }
        .navbar a:hover {
            color: ''' + ACCENT_COLOR + ''';
        }
        .container {
            max-width: 700px;
            margin: 3em auto;
            background: ''' + CARD_COLOR + ''';
            border-radius: 10px;
            box-shadow: 0 2px 12px rgba(26,35,126,0.08);
            padding: 2.5em 2.5em;
            text-align: center;
        }
        h1, h2, h3, h4 { color: ''' + PRIMARY_COLOR + '''; }
        p, td, th { color: ''' + TEXT_COLOR + '''; }
        .btn {
            background: ''' + ACCENT_COLOR + ''';
            color: #fff;
            border: none;
            padding: 0.7em 1.5em;
            border-radius: 5px;
            font-size: 1em;
            cursor: pointer;
            margin-top: 1em;
        }
        .btn:hover { background: #ffa000; }
        .logout-link { margin-left: auto; color: #fff; text-decoration: underline; font-size: 1em; }
        .error { color: #c62828; margin-bottom: 1em; }
    </style>
    {% block extra_head %}{% endblock %}
</head>
<body>
    <div class="navbar">
        <a href="/" style="display:flex;align-items:center;"><img src="/static/logo.svg" class="navbar-logo" alt="Logo"></a>
        <a href="/">Home</a>
        <a href="/status">Status Log</a>
        <a href="/dashboard">Dashboard</a>
        <a href="/accounts_status">Accounts Status</a>
        <a href="/download_log">Download Log</a>
        {% if session.get('logged_in') %}
            <a href="/logout" class="logout-link">Logout</a>
        {% endif %}
    </div>
    <div class="container">
        {{ content|safe }}
    </div>
</body>
</html>
'''

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') and request.endpoint not in ('login', 'static'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            error = 'Invalid credentials.'
    login_content = '''
        <h2>Login</h2>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="post">
            <input type="text" name="username" placeholder="Username" required style="padding:0.5em; width:60%; margin-bottom:1em;"><br>
            <input type="password" name="password" placeholder="Password" required style="padding:0.5em; width:60%; margin-bottom:1em;"><br>
            <button class="btn" type="submit">Login</button>
        </form>
    '''
    rendered_content = render_template_string(login_content, error=error)
    return render_template_string(BASE_TEMPLATE, title='Login', session=session, content=rendered_content)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# Protect all routes except login/logout
@app.before_request
def require_login():
    if request.endpoint not in ('login', 'logout', 'static') and not session.get('logged_in'):
        return redirect(url_for('login'))

last_run_info: dict[str, Optional[str]] = {'start': None, 'end': None, 'error': None}

@app.route('/', methods=['GET', 'POST'])
def home():
    # Calculate next run time
    now = datetime.now(IST)
    next_run = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
    if now >= next_run:
        next_run += timedelta(days=1)
    seconds_left = int((next_run - now).total_seconds())
    home_content = '''
        <h1>Welcome to the Email Campaign Scheduler</h1>
        <div id="timer-container" style="margin:2em 0;">
            <h2 style="color:#1a237e;">Next Run In:</h2>
            <div id="countdown" style="font-size:2.5em;font-weight:bold;color:#ffb300;background:#fff3e0;padding:0.7em 2em;border-radius:12px;display:inline-block;box-shadow:0 2px 8px rgba(26,35,126,0.06);margin-bottom:1em;"></div>
            <div style="color:#888;font-size:1em;margin-top:0.5em;">Scheduled for: <b>{{ next_run_str }}</b> (IST)</div>
        </div>
        <hr style="margin:2em 0;">
        <p><b>Download your full email send log as a CSV file:</b><br>
        <a href="/download_log" style="color:#2980b9; text-decoration:underline;">Download send_log.csv</a></p>
        <script>
            function startCountdown(seconds) {
                function pad(n) { return n < 10 ? '0'+n : n; }
                function update() {
                    if (seconds < 0) return;
                    var h = Math.floor(seconds/3600);
                    var m = Math.floor((seconds%3600)/60);
                    var s = seconds%60;
                    document.getElementById('countdown').textContent = pad(h)+":"+pad(m)+":"+pad(s);
                    seconds--;
                    if (seconds >= 0) setTimeout(update, 1000);
                }
                update();
            }
            startCountdown({{ seconds_left }});
        </script>
    '''
    rendered_content = render_template_string(
        home_content,
        next_run_str=next_run.strftime('%Y-%m-%d %H:%M:%S'),
        seconds_left=seconds_left
    )
    return render_template_string(BASE_TEMPLATE, title='Home', session=session, content=rendered_content)

@app.route('/status')
@login_required
def status():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-10:]
        status_content = '<h2>Status Log (Last 10 Entries)</h2>' + ''.join(f'<div style="text-align:left;color:#222;">{line.strip()}</div>' for line in lines)
    else:
        status_content = '<h2>Status Log</h2><p>No audit log found.</p>'
    rendered_content = render_template_string(status_content)
    return render_template_string(BASE_TEMPLATE, title='Status Log', session=session, content=rendered_content)

@app.route('/dashboard')
@login_required
def dashboard():
    import sqlite3
    from datetime import datetime, timedelta
    db_path = os.path.join(os.path.dirname(__file__), 'data/companies.db')
    total_sent = 0
    total_pending = 0
    last_7_days = []
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM companies WHERE sent_timestamp IS NOT NULL")
            total_sent = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM companies WHERE sent_timestamp IS NULL")
            total_pending = cursor.fetchone()[0]
            today = datetime.now().date()
            for i in range(6, -1, -1):
                day = today - timedelta(days=i)
                cursor.execute("SELECT COUNT(*) FROM companies WHERE date(sent_timestamp) = ?", (day.isoformat(),))
                count = cursor.fetchone()[0]
                last_7_days.append({'date': day.strftime('%Y-%m-%d'), 'count': count})
    except Exception as e:
        error_html = f"<h2>Error loading dashboard: {e}</h2>"
        rendered_content = render_template_string(error_html)
        return render_template_string(BASE_TEMPLATE, title='Dashboard', session=session, content=rendered_content)
    chart_labels = [d['date'] for d in last_7_days]
    chart_data = [d['count'] for d in last_7_days]
    dashboard_content = '''
        <h1>Email Campaign Dashboard</h1>
        <div style="display:flex;justify-content:space-around;flex-wrap:wrap;margin-bottom:2em;">
            <div style="background:#e3e6fd;padding:1.5em 2em;border-radius:10px;min-width:200px;margin:1em;">
                <h2 style="margin:0;color:#1a237e;">{{ total_sent }}</h2>
                <p style="margin:0;color:#222;">Total Sent Emails</p>
            </div>
            <div style="background:#fff3e0;padding:1.5em 2em;border-radius:10px;min-width:200px;margin:1em;">
                <h2 style="margin:0;color:#ffb300;">{{ total_pending }}</h2>
                <p style="margin:0;color:#222;">Total Pending Emails</p>
            </div>
        </div>
        <div style="background:#fff;padding:2em 1em;border-radius:10px;box-shadow:0 2px 8px rgba(26,35,126,0.06);margin-bottom:2em;">
            <h3 style="color:#1a237e;">Emails Sent in the Last 7 Days</h3>
            <canvas id="sentChart" width="600" height="250"></canvas>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            const ctx = document.getElementById('sentChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: {{ chart_labels|tojson }},
                    datasets: [{
                        label: 'Emails Sent',
                        data: {{ chart_data|tojson }},
                        backgroundColor: '#1a237e',
                        borderRadius: 6,
                    }]
                },
                options: {
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: { grid: { display: false } },
                        y: { beginAtZero: true, grid: { color: '#e3e6fd' } }
                    }
                }
            });
        </script>
    '''
    rendered_content = render_template_string(
        dashboard_content,
        total_sent=total_sent,
        total_pending=total_pending,
        chart_labels=chart_labels,
        chart_data=chart_data
    )
    return render_template_string(BASE_TEMPLATE, title='Dashboard', session=session, content=rendered_content)

@app.route('/download_log')
@login_required
def download_log():
    log_path = os.path.join(os.path.dirname(__file__), 'data/send_log.csv')
    if not os.path.exists(log_path):
        download_content = '<h2>send_log.csv not found.</h2>'
        rendered_content = render_template_string(download_content)
        return render_template_string(BASE_TEMPLATE, title='Download Log', session=session, content=rendered_content), 404
    download_content = '''
        <h2>Download Send Log</h2>
        <p>Your full email send log is available for download below:</p>
        <a href="/download_log_file" class="btn">Download send_log.csv</a>
    '''
    rendered_content = render_template_string(download_content)
    return render_template_string(BASE_TEMPLATE, title='Download Log', session=session, content=rendered_content)

@app.route('/download_log_file')
@login_required
def download_log_file():
    log_path = os.path.join(os.path.dirname(__file__), 'data/send_log.csv')
    return send_file(log_path, as_attachment=True, download_name='send_log.csv')

@app.route('/accounts_status')
@login_required
def accounts_status():
    import json
    import sqlite3
    accounts_path = os.path.join(os.path.dirname(__file__), 'src/email_accounts.json')
    exhausted_path = os.path.join(os.path.dirname(__file__), 'exhausted_accounts.json')
    db_path = os.path.join(os.path.dirname(__file__), 'data/companies.db')
    with open(accounts_path, 'r') as f:
        accounts_json = json.load(f)
        sender_accounts = [acc for acc in accounts_json['email_accounts']]
    exhausted_accounts = set()
    if os.path.exists(exhausted_path):
        with open(exhausted_path, 'r') as f:
            try:
                exhausted_accounts = set(json.load(f).keys())
            except Exception:
                exhausted_accounts = set()
    sent_counts = {}
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for acc in sender_accounts:
                email = acc['sender_email']
                cursor.execute(
                    "SELECT COUNT(*) FROM companies WHERE sent_timestamp IS NOT NULL AND sender_email=?",
                    (email,)
                )
                sent_counts[email] = cursor.fetchone()[0]
    except Exception:
        for acc in sender_accounts:
            sent_counts[acc['sender_email']] = 'N/A'
    table_html = '''
        <h2>Sender Accounts Status</h2>
        <table style="width:100%;border-collapse:collapse;margin-top:2em;">
            <tr style="background:#e3e6fd;">
                <th style="padding:0.7em;">Sender Email</th>
                <th style="padding:0.7em;">Status</th>
                <th style="padding:0.7em;">Total Emails Sent</th>
            </tr>
            {% for acc in accounts %}
            <tr style="background:{{ '#fff' if loop.index0%2==0 else '#f5f6fa' }};">
                <td style="padding:0.7em;">{{ acc['sender_email'] }}</td>
                <td style="padding:0.7em;">
                    {% if acc['sender_email'] in exhausted %}
                        <span style="color:#c62828;font-weight:bold;">Exhausted</span>
                    {% else %}
                        <span style="color:#388e3c;font-weight:bold;">Active</span>
                    {% endif %}
                </td>
                <td style="padding:0.7em;">{{ sent_counts[acc['sender_email']] }}</td>
            </tr>
            {% endfor %}
        </table>
    '''
    rendered_content = render_template_string(
        table_html,
        accounts=sender_accounts,
        exhausted=exhausted_accounts,
        sent_counts=sent_counts
    )
    return render_template_string(BASE_TEMPLATE, title='Accounts Status', session=session, content=rendered_content)

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
            "--batch-size", "25",
            "--daily-limit", "1250"
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