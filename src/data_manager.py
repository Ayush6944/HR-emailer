"""
Data Manager for handling company data and email tracking
"""

import os
import sqlite3
import pandas as pd
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self):
        """Initialize the data manager with database paths."""
        self.companies_db = 'data/companies.db'
        self.email_tracking_db = 'data/email_tracking.db'
        logger.info("Database initialized successfully")
    
    def _ensure_db_exists(self):
        """Create database and tables if they don't exist."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                cursor = conn.cursor()
                
                # Create companies table with email tracking columns
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS companies (
                        id INTEGER PRIMARY KEY,
                        company_name TEXT NOT NULL,
                        hr_email TEXT,
                        website TEXT,
                        location TEXT,
                        industry TEXT,
                        company_size TEXT,
                        founded_year INTEGER,
                        email_sent INTEGER DEFAULT 0,
                        sent_timestamp DATETIME,
                        status TEXT DEFAULT 'pending',
                        error_message TEXT
                    )
                """)
                
                # Add email_sent column if it doesn't exist
                try:
                    cursor.execute("ALTER TABLE companies ADD COLUMN email_sent INTEGER DEFAULT 0")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
                
                # Add sent_timestamp column if it doesn't exist
                try:
                    cursor.execute("ALTER TABLE companies ADD COLUMN sent_timestamp DATETIME")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
                
                # Add status column if it doesn't exist
                try:
                    cursor.execute("ALTER TABLE companies ADD COLUMN status TEXT DEFAULT 'pending'")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
                
                # Add error_message column if it doesn't exist
                try:
                    cursor.execute("ALTER TABLE companies ADD COLUMN error_message TEXT")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
                
                conn.commit()
                
                # Create sent_emails table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sent_emails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER,
                        company_name TEXT,
                        hr_email TEXT,
                        sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT,
                        error_message TEXT,
                        is_followup BOOLEAN DEFAULT 0
                    )
                """)
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            raise
    
    def load_companies(self, excel_path: str) -> int:
        """Load companies from Excel file into database."""
        try:
            # Ensure the companies table exists
            self._ensure_db_exists()
            # Read Excel file
            df = pd.read_excel(excel_path)
            
            # Check required columns
            required_columns = ['company_name', 'hr_email']
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"Excel file must contain columns: {required_columns}")
            
            # Clean data
            df = df.dropna(subset=['company_name', 'hr_email'])  # Remove rows with missing required fields
            df = df.fillna('')  # Replace other NaN values with empty string
            
            # Clean email addresses
            df['hr_email'] = df['hr_email'].str.strip().str.lower()
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['company_name', 'hr_email'])
            
            # Ensure string type for text columns
            text_columns = ['company_name', 'hr_email', 'website', 'industry', 'location']
            for col in text_columns:
                if col in df.columns:
                    df[col] = df[col].astype(str)
            
            with sqlite3.connect(self.companies_db) as conn:
                # Clear existing data
                conn.execute("DELETE FROM companies")
                conn.execute("DELETE FROM sent_emails")
                
                # Insert new data
                df.to_sql('companies', conn, if_exists='append', index=False)
                
                count = len(df)
                logger.info(f"Successfully loaded {count} companies into database")
                return count
                
        except Exception as e:
            logger.error(f"Error loading companies: {str(e)}")
            raise
    
    def get_emails_sent_today(self) -> int:
        """Get count of emails sent today."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                today = datetime.now().date()
                tomorrow = today + timedelta(days=1)
                
                query = """
                    SELECT COUNT(*) 
                    FROM sent_emails 
                    WHERE date(sent_at) = date('now')
                """
                count = conn.execute(query).fetchone()[0]
                return count
                
        except Exception as e:
            logger.error(f"Error getting emails sent today: {str(e)}")
            return 0
    
    def get_unsent_companies(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get companies that haven't been sent emails yet."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                cursor = conn.cursor()
                query = """
                    SELECT id, company_name, hr_email
                    FROM companies
                    WHERE sent_timestamp IS NULL
                    ORDER BY id
                """
                if limit:
                    query += f" LIMIT {limit}"
                cursor.execute(query)
                companies = []
                for row in cursor.fetchall():
                    companies.append({
                        'id': row[0],
                        'company_name': row[1],
                        'hr_email': row[2],
                        'position':  'Software Engineer'  # Default position if None
                    })
                return companies
        except Exception as e:
            logger.error(f"Error getting unsent companies: {str(e)}")
            raise
    
    def mark_email_sent(self, company_id: int, status: str = 'sent', error_message: Optional[str] = None):
        """Mark an email as sent in both databases."""
        try:
            # Update companies.db
            with sqlite3.connect(self.companies_db) as companies_conn:
                companies_cursor = companies_conn.cursor()
                companies_cursor.execute("""
                    UPDATE companies
                    SET sent_timestamp = CURRENT_TIMESTAMP,
                        status = ?,
                        error_message = ?
                    WHERE id = ?
                """, (status, error_message, company_id))
                companies_conn.commit()

                # Fetch company_name and hr_email for use in sent_emails
                companies_cursor.execute("""
                    SELECT company_name, hr_email FROM companies WHERE id = ?
                """, (company_id,))
                company_row = companies_cursor.fetchone()
                company_name = company_row[0] if company_row else None
                hr_email = company_row[1] if company_row else None

            # Update email_tracking.db
            with sqlite3.connect(self.email_tracking_db) as tracking_conn:
                tracking_cursor = tracking_conn.cursor()
                # First check if record exists
                tracking_cursor.execute("""
                    SELECT id FROM sent_emails WHERE company_id = ?
                """, (company_id,))
                if not tracking_cursor.fetchone():
                    # Insert new record with company_name and hr_email
                    tracking_cursor.execute("""
                        INSERT INTO sent_emails 
                        (company_id, company_name, hr_email, status, error_message, sent_date)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (company_id, company_name, hr_email, status, error_message))
                else:
                    # Update existing record
                    tracking_cursor.execute("""
                        UPDATE sent_emails
                        SET company_name = ?,
                            hr_email = ?,
                            sent_date = CURRENT_TIMESTAMP,
                            status = ?,
                            error_message = ?
                        WHERE company_id = ?
                    """, (company_name, hr_email, status, error_message, company_id))
                tracking_conn.commit()

            # Optionally, verify updates (logging only)
            with sqlite3.connect(self.companies_db) as companies_conn:
                companies_cursor = companies_conn.cursor()
                companies_cursor.execute("""
                    SELECT status, sent_timestamp 
                    FROM companies 
                    WHERE id = ?
                """, (company_id,))
                result = companies_cursor.fetchone()
                if result:
                    logger.info(f"Companies DB - ID {company_id}: status={result[0]}, sent={result[1]}")
            with sqlite3.connect(self.email_tracking_db) as tracking_conn:
                tracking_cursor = tracking_conn.cursor()
                tracking_cursor.execute("""
                    SELECT status, sent_date, company_name, hr_email 
                    FROM sent_emails 
                    WHERE company_id = ?
                """, (company_id,))
                result = tracking_cursor.fetchone()
                if result:
                    logger.info(f"Tracking DB - ID {company_id}: status={result[0]}, sent={result[1]}, company={result[2]}, email={result[3]}")
        except Exception as e:
            logger.error(f"Error marking email sent: {str(e)}")
            raise
    
    def get_sent_emails_report(self) -> pd.DataFrame:
        """Get a report of all sent emails."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                query = """
                    SELECT 
                        c.company_name,
                        c.hr_email,
                        s.sent_at,
                        s.status,
                        s.error_message
                    FROM sent_emails s
                    JOIN companies c ON s.company_id = c.id
                    ORDER BY s.sent_at DESC
                """
                return pd.read_sql_query(query, conn)
                
        except Exception as e:
            logger.error(f"Error generating sent emails report: {str(e)}")
            raise
            
    def mark_companies_as_sent(self, company_names: List[str]) -> None:
        """Mark specific companies as sent in the database."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                cursor = conn.cursor()
                for company_name in company_names:
                    # Get company ID
                    cursor.execute("SELECT id, hr_email FROM companies WHERE company_name = ?", (company_name,))
                    result = cursor.fetchone()
                    if result:
                        company_id, hr_email = result
                        # Mark as sent
                        cursor.execute("""
                            INSERT INTO sent_emails (company_id, hr_email, status)
                            VALUES (?, ?, 'success')
                        """, (company_id, hr_email))
                conn.commit()
                logger.info(f"Marked {len(company_names)} companies as sent")
                
        except Exception as e:
            logger.error(f"Error marking companies as sent: {str(e)}")
            raise

    def mark_companies_as_sent_by_id(self, target_id: int):
        """Mark all companies up to the target ID as sent, but only if they haven't been sent already."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                cursor = conn.cursor()
                # Update only companies that haven't been sent yet
                cursor.execute("""
                    UPDATE companies 
                    SET email_sent = 1,
                        sent_timestamp = CURRENT_TIMESTAMP,
                        status = 'sent'
                    WHERE id <= ? 
                    AND email_sent = 0 
                    AND (sent_timestamp IS NULL OR date(sent_timestamp) != date('now'))
                """, (target_id,))
                conn.commit()
                logger.info(f"Marked companies up to ID {target_id} as sent")
        except Exception as e:
            logger.error(f"Error marking companies as sent: {str(e)}")
            raise

    def get_sent_companies_report(self, date: str = None) -> pd.DataFrame:
        """Get a report of sent companies, optionally filtered by date."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                if date:
                    # Get companies sent on specific date
                    query = """
                        SELECT 
                            id,
                            company_name,
                            hr_email,
                            sent_timestamp,
                            status,
                            error_message
                        FROM companies 
                        WHERE email_sent = 1 
                        AND date(sent_timestamp) = date(?)
                        ORDER BY sent_timestamp DESC
                    """
                    df = pd.read_sql_query(query, conn, params=(date,))
                else:
                    # Get all sent companies
                    query = """
                        SELECT 
                            id,
                            company_name,
                            hr_email,
                            sent_timestamp,
                            status,
                            error_message
                        FROM companies 
                        WHERE email_sent = 1 
                        ORDER BY sent_timestamp DESC
                    """
                    df = pd.read_sql_query(query, conn)
                
                if not df.empty:
                    logger.info(f"Retrieved {len(df)} sent companies")
                else:
                    logger.info("No sent companies found")
                
                return df
                
        except Exception as e:
            logger.error(f"Error getting sent companies report: {str(e)}")
            raise

    def get_sent_companies_summary(self) -> dict:
        """Get a summary of sent emails."""
        try:
            with sqlite3.connect(self.companies_db) as conn:
                cursor = conn.cursor()
                
                # Get total sent count
                cursor.execute("""
                    SELECT COUNT(*) FROM companies 
                    WHERE email_sent = 1
                """)
                total_sent = cursor.fetchone()[0]
                
                # Get today's sent count
                cursor.execute("""
                    SELECT COUNT(*) FROM companies 
                    WHERE email_sent = 1 
                    AND date(sent_timestamp) = date('now')
                """)
                sent_today = cursor.fetchone()[0]
                
                # Get failed emails count
                cursor.execute("""
                    SELECT COUNT(*) FROM companies 
                    WHERE email_sent = 1 
                    AND status = 'failed'
                """)
                failed_count = cursor.fetchone()[0]
                
                # Get last sent email timestamp
                cursor.execute("""
                    SELECT MAX(sent_timestamp) FROM companies 
                    WHERE email_sent = 1
                """)
                last_sent = cursor.fetchone()[0]
                
                summary = {
                    'total_sent': total_sent,
                    'sent_today': sent_today,
                    'failed_count': failed_count,
                    'last_sent': last_sent
                }
                
                logger.info(f"Retrieved sent companies summary: {summary}")
                return summary
                
        except Exception as e:
            logger.error(f"Error getting sent companies summary: {str(e)}")
            raise

    def close(self):
        """Close database connections (no-op, since we store paths)."""
        pass