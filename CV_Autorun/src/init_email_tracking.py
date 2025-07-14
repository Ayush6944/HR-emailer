"""
Initialize email tracking database with required tables
"""

import sqlite3
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_email_tracking_db():
    """Initialize email tracking database with required tables."""
    try:
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        
        # Connect to email tracking database
        with sqlite3.connect('data/email_tracking.db') as conn:
            cursor = conn.cursor()
            
            # Create email_tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    company_name TEXT NOT NULL,
                    hr_email TEXT NOT NULL,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'sent',
                    error_message TEXT,
                    is_followup BOOLEAN DEFAULT 0,
                    template_used TEXT,
                    campaign_id INTEGER
                )
            """)
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_tracking_company ON email_tracking (company_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_tracking_date ON email_tracking (sent_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_tracking_status ON email_tracking (status)')
            
            conn.commit()
            logger.info("Email tracking database initialized successfully")
            
    except Exception as e:
        logger.error(f"Error initializing email tracking database: {str(e)}")
        raise

if __name__ == "__main__":
    init_email_tracking_db() 