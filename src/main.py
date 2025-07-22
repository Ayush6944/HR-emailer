import argparse
import logging
import json
from datetime import datetime, timedelta
from data_manager import DataManager
from email_engine import EmailEngine
from template_manager import TemplateManager
from tracker import EmailTracker
import os
import time
import signal
import sys
from typing import Dict, Any
import sqlite3
import random
import csv

EXHAUSTED_ACCOUNTS_FILE = 'exhausted_accounts.json'
EXHAUSTION_PERIOD_HOURS = 24

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('campaign.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    try:
        config_path = 'config.json'
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found at {config_path}")
            
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Validate required email settings
        if 'email' not in config:
            raise ValueError("Missing 'email' section in configuration")
            
        email_config = config['email']
        
        required_fields = ['smtp_server', 'smtp_port', 'use_tls', 'batch_delay', 'max_retries']
        missing_fields = [field for field in required_fields if field not in email_config]
        
        if missing_fields:
            raise ValueError(f"Missing required email configuration fields: {', '.join(missing_fields)}")
            
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        raise

def save_progress(last_processed_id: int):
    """Save the last processed company ID to a progress file."""
    try:
        with open('campaign_progress.json', 'w') as f:
            json.dump({'last_processed_id': last_processed_id}, f)
    except Exception as e:
        logger.error(f"Error saving progress: {str(e)}")

def load_progress() -> int:
    """Load the last processed company ID from the progress file."""
    try:
        if os.path.exists('campaign_progress.json'):
            with open('campaign_progress.json', 'r') as f:
                return json.load(f).get('last_processed_id', 0)
    except Exception as e:
        logger.error(f"Error loading progress: {str(e)}")
    return 0

def load_exhausted_accounts():
    """Load exhausted accounts and remove those past the cooldown period."""
    now = datetime.now()
    exhausted = {}
    if os.path.exists(EXHAUSTED_ACCOUNTS_FILE):
        with open(EXHAUSTED_ACCOUNTS_FILE, 'r') as f:
            try:
                exhausted = json.load(f)
            except Exception:
                exhausted = {}
    # Remove accounts past cooldown
    to_remove = []
    for email, ts in exhausted.items():
        exhausted_time = datetime.fromisoformat(ts)
        if now - exhausted_time > timedelta(hours=EXHAUSTION_PERIOD_HOURS):
            to_remove.append(email)
    for email in to_remove:
        exhausted.pop(email)
    if to_remove:
        with open(EXHAUSTED_ACCOUNTS_FILE, 'w') as f:
            json.dump(exhausted, f)
    return exhausted

def mark_account_exhausted(email):
    exhausted = load_exhausted_accounts()
    exhausted[email] = datetime.now().isoformat()
    with open(EXHAUSTED_ACCOUNTS_FILE, 'w') as f:
        json.dump(exhausted, f)

def is_gmail_limit_error(error_str):
    return (
        'Daily user sending limit exceeded' in error_str or
        '5.4.5 Daily user sending limit exceeded' in error_str or
        '5.4.5 sending limits' in error_str
    )

def signal_handler(signum, frame):
    """Handle signals to gracefully stop the campaign."""
    logger.info("\nReceived signal to stop. Saving progress...")
    sys.exit(0)

def run_campaign(resume_path: str, batch_size: int = 50, daily_limit: int = 500, background: bool = False):
    """Run the email campaign with round-robin sender accounts."""
    data_manager = None
    email_tracker = None
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Initialize managers
        data_manager = DataManager()
        email_tracker = EmailTracker()  # Initialize email tracker
        config = load_config()
        template_manager = TemplateManager()
        
        # Load all sender accounts (now under 'email_accounts' key)
        accounts_path = os.path.join(os.path.dirname(__file__), 'email_accounts.json')
        with open(accounts_path, 'r') as f:
            accounts_json = json.load(f)
            sender_accounts = [acc for acc in accounts_json['email_accounts'] if acc.get('enabled', True)]
        
        exhausted_accounts = load_exhausted_accounts()

        # Verify resume exists
        if not os.path.exists(resume_path):
            raise FileNotFoundError(f"Resume not found at {resume_path}")
        
        # Load template
        template = template_manager.get_template('job_inquiry')
        # Add resume to template attachments
        template['attachments'] = [resume_path]
        
        # Get companies to process
        companies = data_manager.get_unsent_companies(limit=daily_limit)
        total_companies = len(companies)
        logger.info(f"Starting campaign for {total_companies} companies")
        
        # Load progress
        last_processed_id = load_progress()
        if last_processed_id > 0:
            logger.info(f"Resuming from company ID {last_processed_id}")
            companies = [c for c in companies if c['id'] > last_processed_id]
            logger.info(f"Remaining companies to process: {len(companies)}")
        
        processed_count = 0
        send_log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/send_log.csv'))
        if not os.path.exists(send_log_path):
            with open(send_log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['sender_email', 'recipient_email', 'date_sent', 'status', 'company_name'])
        
        # Round-robin send logic
        num_accounts = len(sender_accounts)
        idx = 0
        while idx < len(companies):
            company = companies[idx]
            # Filter out exhausted accounts
            available_accounts = [acc for acc in sender_accounts if acc['sender_email'] not in exhausted_accounts]
            if not available_accounts:
                logger.error("All sender accounts are exhausted for the day. Stopping campaign.")
                break
            # Use round-robin among available accounts
            account = available_accounts[idx % len(available_accounts)]
            logger.info(f"Sending email to {company['company_name']} ({company['hr_email']}) from {account['sender_email']}")
            try:
                email_body = template_manager.format_template(
                    template,
                    company_name=company['company_name'],
                    hr_email=company['hr_email'],
                    hr_name="HR Manager",
                    position="Software Developer"
                )
                email = {
                    'to_email': company['hr_email'],
                    'subject': f"Application for Software Engineer | Developer at {company['company_name']}",
                    'content': email_body,
                    'company_id': company['id'],
                    'company_name': company['company_name'],
                    'hr_email': company['hr_email'],
                    'position': 'Software Engineer'
                }
                # Build config for this account
                account_config = config['email'].copy()
                account_config.update({
                    'sender_email': account['sender_email'],
                    'sender_password': account['sender_password'],
                    'smtp_server': account.get('smtp_server', account_config.get('smtp_server', 'smtp.gmail.com')),
                    'smtp_port': account.get('smtp_port', account_config.get('smtp_port', 587)),
                    'use_tls': account.get('use_tls', account_config.get('use_tls', True)),
                    'batch_delay': account.get('batch_delay', account_config.get('batch_delay', 20)),
                    'max_retries': account.get('max_retries', account_config.get('max_retries', 2)),
                })
                email_engine = EmailEngine(account_config)
                # Send single email
                result = email_engine.send_batch([email], template)[0]
                company_id = result['company_id']
                success = result['success']
                error = result.get('error')
                if not success and error and is_gmail_limit_error(error):
                    logger.warning(f"Account {account['sender_email']} exhausted (Gmail limit). Marking as exhausted and retrying with another account.")
                    mark_account_exhausted(account['sender_email'])
                    exhausted_accounts = load_exhausted_accounts()  # reload after update
                    continue  # retry this company with a new account
                data_manager.mark_email_sent(
                    company_id,
                    status='sent' if success else 'failed',
                    error_message=None if success else error
                )
                email_tracker.mark_email_sent(
                    company_id,
                    status='sent' if success else 'failed',
                    error_message=None if success else error
                )
                save_progress(company_id)
                processed_count += 1
                logger.info(f"Progress: {processed_count}/{total_companies} companies processed")
                # Log to send_log.csv
                with open(send_log_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        account['sender_email'],
                        email['to_email'],
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'success' if success else 'failed',
                        email['company_name']
                    ])
                    f.flush()
                    os.fsync(f.fileno())
                time.sleep(account_config.get('batch_delay', 1))
                idx += 1
            except Exception as e:
                error_str = str(e)
                if is_gmail_limit_error(error_str):
                    logger.warning(f"Account {account['sender_email']} exhausted (Gmail limit, exception). Marking as exhausted and retrying with another account.")
                    mark_account_exhausted(account['sender_email'])
                    exhausted_accounts = load_exhausted_accounts()
                    continue  # retry this company with a new account
                logger.error(f"Error sending email for company {company['company_name']}: {e}")
                data_manager.mark_email_sent(company['id'], status='failed', error_message=error_str)
                email_tracker.mark_email_sent(company['id'], status='failed', error_message=error_str)
                save_progress(company['id'])
                processed_count += 1
                idx += 1
        
        logger.info(f"Campaign completed. Sent {processed_count} emails.")
        
        # Save final progress and exit
        if processed_count > 0:
            save_progress(companies[-1]['id'] if companies else last_processed_id)
            # Final verification of database updates
            logger.info("Verifying database updates...")
            for company in companies:
                if company['id'] > last_processed_id:
                    # Verify in companies.db
                    with sqlite3.connect('data/companies.db') as conn:
                        cursor = conn.execute("""
                            SELECT status, sent_timestamp 
                            FROM companies 
                            WHERE id = ?
                        """, (company['id'],))
                        result = cursor.fetchone()
                        if result:
                            logger.info(f"Companies DB - ID {company['id']}: status={result[0]}, sent={result[1]}")
                    # Verify in email_tracking.db
                    with sqlite3.connect('data/email_tracking.db') as conn:
                        cursor = conn.execute("""
                            SELECT status, sent_date 
                            FROM sent_emails 
                            WHERE company_id = ?
                        """, (company['id'],))
                        result = cursor.fetchone()
                        if result:
                            logger.info(f"Tracking DB - ID {company['id']}: status={result[0]}, sent={result[1]}")
        logger.info("Campaign completed successfully. Exiting...")
        if background:
            if data_manager:
                data_manager.close()
            if email_tracker:
                email_tracker.close()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("\nCampaign interrupted by user. Cleaning up...")
        if background:
            if data_manager:
                data_manager.close()
            if email_tracker:
                email_tracker.close()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error running campaign: {str(e)}")
        if background:
            if data_manager:
                data_manager.close()
            if email_tracker:
                email_tracker.close()
        sys.exit(1)

if __name__ == '__main__':
    import traceback
    try:
        parser = argparse.ArgumentParser(description='Run email campaign')
        parser.add_argument('--resume', required=True, help='Path to resume file')
        parser.add_argument('--batch-size', type=int, default=50, help='Number of emails to send in each batch')
        parser.add_argument('--daily-limit', type=int, default=500, help='Maximum number of emails to send per day')
        parser.add_argument('--background', action='store_true', help='Run in background mode')
        args = parser.parse_args()
        if args.background:
            # Detach from terminal
            pid = os.fork()
            if pid > 0:
                print(f"Campaign started in background with PID {pid}")
                sys.exit(0)
        run_campaign(args.resume, args.batch_size, args.daily_limit, args.background)
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        logger.error(traceback.format_exc())
        print(f"Fatal error in main: {e}")
        print(traceback.format_exc())
        sys.exit(2) 