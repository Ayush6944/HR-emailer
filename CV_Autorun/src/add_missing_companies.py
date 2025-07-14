import sqlite3
import logging
import pandas as pd
from datetime import datetime
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_missing_companies():
    """Add companies from companies.db that are missing in email_tracking.db."""
    try:
        # Connect to both databases
        with sqlite3.connect('data/companies.db') as companies_conn, \
             sqlite3.connect('data/email_tracking.db') as tracking_conn:
            
            companies_cursor = companies_conn.cursor()
            tracking_cursor = tracking_conn.cursor()
            
            # 1. Get all sent companies from companies.db
            companies_cursor.execute("""
                SELECT id, company_name, hr_email, sent_timestamp, status, error_message
                FROM companies
                WHERE sent_timestamp IS NOT NULL
                AND id >= 205  -- Only get the missing companies
            """)
            sent_companies = pd.DataFrame(companies_cursor.fetchall(), 
                                       columns=['id', 'company_name', 'hr_email', 'sent_timestamp', 'status', 'error_message'])
            
            # 2. Get existing companies from email_tracking.db
            tracking_cursor.execute("""
                SELECT company_name, hr_email
                FROM sent_emails
            """)
            existing_companies = pd.DataFrame(tracking_cursor.fetchall(),
                                           columns=['company_name', 'hr_email'])
            
            # 3. Add missing companies to email_tracking.db
            logger.info("Adding missing companies to email_tracking.db...")
            added_count = 0
            
            for _, company in sent_companies.iterrows():
                # Check if company already exists
                exists = existing_companies[
                    (existing_companies['company_name'].str.strip().str.lower() == company['company_name'].strip().lower()) &
                    (existing_companies['hr_email'].str.strip().str.lower() == company['hr_email'].strip().lower())
                ].empty
                
                if exists:
                    tracking_cursor.execute("""
                        INSERT INTO sent_emails 
                        (company_id, company_name, hr_email, sent_date, status, error_message, is_followup)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        company['id'],
                        company['company_name'],
                        company['hr_email'],
                        company['sent_timestamp'],
                        company['status'],
                        company['error_message'],
                        False  # Default is_followup to False
                    ))
                    added_count += 1
            
            tracking_conn.commit()
            
            # 4. Report results
            logger.info("Add complete. Results:")
            print(f"\nTotal companies processed: {len(sent_companies)}")
            print(f"Successfully added: {added_count}")
            
            if added_count < len(sent_companies):
                print(f"\nSkipped {len(sent_companies) - added_count} companies (already exist in tracking.db)")
            
            # 5. Verify final counts
            companies_cursor.execute("""
                SELECT COUNT(*) FROM companies 
                WHERE sent_timestamp IS NOT NULL
            """)
            companies_count = companies_cursor.fetchone()[0]
            
            tracking_cursor.execute("SELECT COUNT(*) FROM sent_emails")
            tracking_count = tracking_cursor.fetchone()[0]
            
            print(f"\nFinal counts:")
            print(f"Companies.db sent emails: {companies_count}")
            print(f"Email tracking.db sent emails: {tracking_count}")
            
            if companies_count == tracking_count:
                print("\nDatabases are now fully synchronized!")
            else:
                print("\nWarning: Databases still have different counts!")
                print("Please run analyze_databases.py to see the differences.")
            
    except Exception as e:
        logger.error(f"Error adding missing companies: {str(e)}")
        raise

if __name__ == '__main__':
    add_missing_companies() 