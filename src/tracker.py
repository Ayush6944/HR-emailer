"""
Email Tracker for monitoring campaign performance and email delivery status
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import os

class EmailTracker:
    """Tracks email campaigns, delivery status, and performance metrics"""
    
    def __init__(self, db_file: str = "data/email_tracking.db"):
        self.logger = logging.getLogger(__name__)
        self.db_file = db_file
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        self.logger.info(f"Email tracker initialized with database: {db_file}")
        self.verify_database_setup()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_file) as conn:
            # Campaigns table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    template_used TEXT,
                    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_date TIMESTAMP,
                    total_companies INTEGER DEFAULT 0,
                    total_sent INTEGER DEFAULT 0,
                    total_failed INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            # Sent emails table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sent_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    company_id INTEGER,
                    company_name TEXT NOT NULL,
                    hr_email TEXT NOT NULL,
                    template_used TEXT,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    is_followup BOOLEAN DEFAULT 0,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
            
            # Scheduled campaigns table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    template_used TEXT,
                    scheduled_time TIMESTAMP NOT NULL,
                    config_json TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            # Performance metrics table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER,
                    metric_date DATE,
                    emails_sent INTEGER DEFAULT 0,
                    emails_failed INTEGER DEFAULT 0,
                    bounce_rate REAL DEFAULT 0.0,
                    avg_send_time REAL DEFAULT 0.0,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sent_emails_campaign ON sent_emails (campaign_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sent_emails_date ON sent_emails (sent_date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sent_emails_status ON sent_emails (status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_campaigns_date ON campaigns (start_date)')
            
            conn.commit()
    
    def verify_database_setup(self):
        """Verify that all required tables exist and are properly configured"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                # Check if all required tables exist
                required_tables = ['campaigns', 'sent_emails', 'scheduled_campaigns', 'performance_metrics']
                for table in required_tables:
                    cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                    if not cursor.fetchone():
                        self.logger.error(f"Required table '{table}' not found in database")
                        raise RuntimeError(f"Database schema not properly initialized: missing table '{table}'")
                
                # Verify scheduled_campaigns table structure
                cursor = conn.execute("PRAGMA table_info(scheduled_campaigns)")
                columns = {row[1]: row[2] for row in cursor.fetchall()}
                required_columns = {
                    'id': 'INTEGER',
                    'name': 'TEXT',
                    'template_used': 'TEXT',
                    'scheduled_time': 'TIMESTAMP',
                    'config_json': 'TEXT',
                    'created_date': 'TIMESTAMP',
                    'status': 'TEXT'
                }
                for col, type_ in required_columns.items():
                    if col not in columns:
                        self.logger.error(f"Required column '{col}' not found in scheduled_campaigns table")
                        raise RuntimeError(f"Database schema not properly initialized: missing column '{col}'")
                
                self.logger.info("Database schema verification completed successfully")
        except Exception as e:
            self.logger.error(f"Database verification failed: {str(e)}")
            raise
    
    def start_campaign(self, name: str, template_used: str, total_companies: int) -> int:
        """Start tracking a new campaign"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.execute('''
                    INSERT INTO campaigns (name, template_used, total_companies, status)
                    VALUES (?, ?, ?, 'active')
                ''', (name, template_used, total_companies))
                
                campaign_id = cursor.lastrowid
                conn.commit()
                
                self.logger.info(f"Started tracking campaign '{name}' with ID {campaign_id}")
                return campaign_id
                
        except sqlite3.IntegrityError:
            # Campaign name already exists, get existing ID
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.execute('SELECT id FROM campaigns WHERE name = ?', (name,))
                result = cursor.fetchone()
                if result:
                    self.logger.warning(f"Campaign '{name}' already exists, using existing ID {result[0]}")
                    return result[0]
                else:
                    raise
        except Exception as e:
            self.logger.error(f"Error starting campaign tracking: {str(e)}")
            raise
    
    def track_email(self, campaign_id: int, company_id: Optional[int], 
                   company_name: str, hr_email: str, template_used: str, 
                   status: str, error_message: Optional[str] = None, 
                   is_followup: bool = False):
        """Track individual email sending result"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute('''
                    INSERT INTO sent_emails 
                    (campaign_id, company_id, company_name, hr_email, template_used, 
                     status, error_message, is_followup)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (campaign_id, company_id, company_name, hr_email, template_used, 
                     status, error_message, is_followup))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Error tracking email to {hr_email}: {str(e)}")
    
    def complete_campaign(self, campaign_id: int, total_sent: int, 
                         total_failed: int, success_rate: float):
        """Mark campaign as completed and update final statistics"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                conn.execute('''
                    UPDATE campaigns 
                    SET end_date = CURRENT_TIMESTAMP, 
                        total_sent = ?, 
                        total_failed = ?, 
                        success_rate = ?,
                        status = 'completed'
                    WHERE id = ?
                ''', (total_sent, total_failed, success_rate, campaign_id))
                
                conn.commit()
                
                self.logger.info(f"Completed campaign {campaign_id}: {total_sent} sent, {total_failed} failed")
                
        except Exception as e:
            self.logger.error(f"Error completing campaign {campaign_id}: {str(e)}")
    
    def schedule_campaign(self, campaign_config: Dict):
        """Store scheduled campaign configuration"""
        try:
            import json
            
            # Create a copy of the config to avoid modifying the original
            config_copy = campaign_config.copy()
            
            # Convert datetime to ISO format string
            if 'scheduled_time' in config_copy and isinstance(config_copy['scheduled_time'], datetime):
                config_copy['scheduled_time'] = config_copy['scheduled_time'].isoformat()
            
            self.logger.info(f"Scheduling campaign: {config_copy['name']} for {config_copy['scheduled_time']}")
            
            with sqlite3.connect(self.db_file) as conn:
                # First verify the campaign doesn't already exist
                cursor = conn.execute('SELECT id FROM scheduled_campaigns WHERE name = ?', (config_copy['name'],))
                if cursor.fetchone():
                    self.logger.warning(f"Campaign '{config_copy['name']}' already exists in schedule")
                    return
                
                # Insert the new campaign
                cursor = conn.execute('''
                    INSERT INTO scheduled_campaigns 
                    (name, template_used, scheduled_time, config_json)
                    VALUES (?, ?, ?, ?)
                ''', (
                    config_copy['name'],
                    config_copy.get('template', 'default'),
                    config_copy['scheduled_time'],
                    json.dumps(config_copy)
                ))
                
                campaign_id = cursor.lastrowid
                conn.commit()
                
                self.logger.info(f"Campaign scheduled successfully with ID: {campaign_id}")
                
        except Exception as e:
            self.logger.error(f"Error scheduling campaign: {str(e)}")
            raise
    
    def get_campaign_stats(self, campaign_name: Optional[str] = None) -> Dict:
        """Get comprehensive campaign statistics"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                if campaign_name:
                    # Stats for specific campaign
                    query = '''
                        SELECT 
                            COUNT(*) as total_sent,
                            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                            SUM(CASE WHEN is_followup = 1 THEN 1 ELSE 0 END) as followups
                        FROM sent_emails se
                        JOIN campaigns c ON se.campaign_id = c.id
                        WHERE c.name = ?
                    '''
                    result = conn.execute(query, (campaign_name,)).fetchone()
                else:
                    # Overall stats
                    query = '''
                        SELECT 
                            COUNT(*) as total_sent,
                            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                            SUM(CASE WHEN is_followup = 1 THEN 1 ELSE 0 END) as followups
                        FROM sent_emails
                    '''
                    result = conn.execute(query).fetchone()
                
                # Get campaign count
                campaign_count_query = '''
                    SELECT COUNT(DISTINCT name) FROM campaigns
                ''' + (f" WHERE name = '{campaign_name}'" if campaign_name else "")
                
                campaign_count = conn.execute(campaign_count_query).fetchone()[0]
                
                # Get recent campaigns
                recent_campaigns_query = '''
                    SELECT name, start_date, total_sent, success_rate
                    FROM campaigns
                    WHERE status = 'completed'
                    ORDER BY start_date DESC
                    LIMIT 5
                '''
                recent_campaigns = conn.execute(recent_campaigns_query).fetchall()
                
                total_sent = result[0] if result[0] else 0
                successful = result[1] if result[1] else 0
                failed = result[2] if result[2] else 0
                followups = result[3] if result[3] else 0
                
                success_rate = (successful / total_sent * 100) if total_sent > 0 else 0
                
                return {
                    'total_sent': total_sent,
                    'total_successful': successful,
                    'total_failed': failed,
                    'total_followups': followups,
                    'success_rate': success_rate,
                    'total_campaigns': campaign_count,
                    'recent_campaigns': [
                        {
                            'name': row[0],
                            'date': row[1],
                            'sent': row[2],
                            'success_rate': row[3]
                        } for row in recent_campaigns
                    ]
                }
                
        except Exception as e:
            self.logger.error(f"Error getting campaign stats: {str(e)}")
            return {
                'total_sent': 0,
                'total_successful': 0,
                'total_failed': 0,
                'total_followups': 0,
                'success_rate': 0,
                'total_campaigns': 0,
                'recent_campaigns': []
            }
    
    def get_detailed_campaign_data(self, campaign_name: Optional[str] = None) -> Dict:
        """Get detailed data for campaign reporting"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                # Campaign summary
                if campaign_name:
                    summary_query = '''
                        SELECT * FROM campaigns WHERE name = ?
                    '''
                    summary = conn.execute(summary_query, (campaign_name,)).fetchone()
                else:
                    summary_query = '''
                        SELECT 
                            'All Campaigns' as name,
                            MIN(start_date) as start_date,
                            MAX(end_date) as end_date,
                            SUM(total_companies) as total_companies,
                            SUM(total_sent) as total_sent,
                            SUM(total_failed) as total_failed,
                            AVG(success_rate) as success_rate
                        FROM campaigns
                    '''
                    summary = conn.execute(summary_query).fetchone()
                
                # Email details
                if campaign_name:
                    emails_query = '''
                        SELECT se.company_name, se.hr_email, se.sent_date, 
                               se.status, se.is_followup, se.error_message
                        FROM sent_emails se
                        JOIN campaigns c ON se.campaign_id = c.id
                        WHERE c.name = ?
                        ORDER BY se.sent_date DESC
                    '''
                    emails = conn.execute(emails_query, (campaign_name,)).fetchall()
                else:
                    emails_query = '''
                        SELECT se.company_name, se.hr_email, se.sent_date, 
                               se.status, se.is_followup, se.error_message, c.name as campaign_name
                        FROM sent_emails se
                        JOIN campaigns c ON se.campaign_id = c.id
                        ORDER BY se.sent_date DESC
                        LIMIT 1000
                    '''
                    emails = conn.execute(emails_query).fetchall()
                
                # Failed emails
                if campaign_name:
                    failed_query = '''
                        SELECT se.company_name, se.hr_email, se.error_message, se.sent_date
                        FROM sent_emails se
                        JOIN campaigns c ON se.campaign_id = c.id
                        WHERE c.name = ? AND se.status = 'failed'
                        ORDER BY se.sent_date DESC
                    '''
                    failed_emails = conn.execute(failed_query, (campaign_name,)).fetchall()
                else:
                    failed_query = '''
                        SELECT se.company_name, se.hr_email, se.error_message, 
                               se.sent_date, c.name as campaign_name
                        FROM sent_emails se
                        JOIN campaigns c ON se.campaign_id = c.id
                        WHERE se.status = 'failed'
                        ORDER BY se.sent_date DESC
                        LIMIT 500
                    '''
                    failed_emails = conn.execute(failed_query).fetchall()
                
                return {
                    'summary': dict(zip([desc[0] for desc in conn.description], summary)) if summary else {},
                    'emails': [
                        dict(zip([desc[0] for desc in conn.description], email)) 
                        for email in emails
                    ],
                    'failed_emails': [
                        dict(zip([desc[0] for desc in conn.description], email)) 
                        for email in failed_emails
                    ]
                }
                
        except Exception as e:
            self.logger.error(f"Error getting detailed campaign data: {str(e)}")
            return {'summary': {}, 'emails': [], 'failed_emails': []}
    
    def get_performance_trends(self, days: int = 30) -> Dict:
        """Get performance trends over specified number of days"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                query = '''
                    SELECT 
                        DATE(sent_date) as date,
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM sent_emails
                    WHERE sent_date >= date('now', '-{} days')
                    GROUP BY DATE(sent_date)
                    ORDER BY date DESC
                '''.format(days)
                
                results = conn.execute(query).fetchall()
                
                trends = []
                for row in results:
                    date, total, successful, failed = row
                    success_rate = (successful / total * 100) if total > 0 else 0
                    trends.append({
                        'date': date,
                        'total_sent': total,
                        'successful': successful,
                        'failed': failed,
                        'success_rate': success_rate
                    })
                
                return {
                    'trends': trends,
                    'period_days': days
                }
                
        except Exception as e:
            self.logger.error(f"Error getting performance trends: {str(e)}")
            return {'trends': [], 'period_days': days}
    
    def get_template_performance(self) -> Dict:
        """Get performance statistics by template"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                query = '''
                    SELECT 
                        template_used,
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM sent_emails
                    WHERE template_used IS NOT NULL
                    GROUP BY template_used
                    ORDER BY total_sent DESC
                '''
                
                results = conn.execute(query).fetchall()
                
                template_stats = []
                for row in results:
                    template, total, successful, failed = row
                    success_rate = (successful / total * 100) if total > 0 else 0
                    template_stats.append({
                        'template': template,
                        'total_sent': total,
                        'successful': successful,
                        'failed': failed,
                        'success_rate': success_rate
                    })
                
                return {'template_performance': template_stats}
                
        except Exception as e:
            self.logger.error(f"Error getting template performance: {str(e)}")
            return {'template_performance': []}
    
    def cleanup_old_data(self, days_old: int = 30) -> int:
        """Clean up old campaign data older than specified days"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                # Delete old sent emails
                cursor = conn.execute('''
                    DELETE FROM sent_emails 
                    WHERE sent_date < date('now', '-{} days')
                '''.format(days_old))
                
                deleted_emails = cursor.rowcount
                
                # Delete old completed campaigns (keep campaign record but remove detailed emails)
                conn.execute('''
                    DELETE FROM campaigns 
                    WHERE status = 'completed' 
                    AND end_date < date('now', '-{} days')
                '''.format(days_old * 2))  # Keep campaigns longer than emails
                
                conn.commit()
                
                self.logger.info(f"Cleaned up {deleted_emails} old email records")
                return deleted_emails
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {str(e)}")
            return 0
    
    def export_analytics(self, output_file: str):
        """Export comprehensive analytics to Excel"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                # Campaign summary
                campaigns_df = pd.read_sql_query('SELECT * FROM campaigns ORDER BY start_date DESC', conn)
                
                # Email details
                emails_df = pd.read_sql_query('''
                    SELECT se.*, c.name as campaign_name 
                    FROM sent_emails se 
                    JOIN campaigns c ON se.campaign_id = c.id 
                    ORDER BY se.sent_date DESC
                ''', conn)
                
                # Performance trends
                trends_df = pd.read_sql_query('''
                    SELECT 
                        DATE(sent_date) as date,
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM sent_emails
                    GROUP BY DATE(sent_date)
                    ORDER BY date DESC
                ''', conn)
                
                # Template performance
                template_df = pd.read_sql_query('''
                    SELECT 
                        template_used,
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM sent_emails
                    WHERE template_used IS NOT NULL
                    GROUP BY template_used
                ''', conn)
            
            # Export to Excel
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                campaigns_df.to_excel(writer, sheet_name='Campaigns', index=False)
                emails_df.to_excel(writer, sheet_name='Email Details', index=False)
                trends_df.to_excel(writer, sheet_name='Daily Trends', index=False)
                template_df.to_excel(writer, sheet_name='Template Performance', index=False)
            
            self.logger.info(f"Analytics exported to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting analytics: {str(e)}")
            return False
    
    def mark_email_sent(self, company_id: int, status: str = 'sent', error_message: Optional[str] = None):
        """Mark an email as sent in the tracking database."""
        try:
            # First get company details from companies.db
            companies_conn = sqlite3.connect("data/companies.db")
            cursor = companies_conn.execute("""
                SELECT company_name, hr_email FROM companies WHERE id = ?
            """, (company_id,))
            company_details = cursor.fetchone()
            companies_conn.close()
            
            if not company_details:
                self.logger.error(f"Company {company_id} not found in companies.db")
                return
            
            company_name, hr_email = company_details
            
            # Now update email_tracking.db
            with sqlite3.connect(self.db_file) as conn:
                # Check if record exists
                cursor = conn.execute("""
                    SELECT id FROM sent_emails WHERE company_id = ?
                """, (company_id,))
                
                if not cursor.fetchone():
                    # Insert new record with company details
                    conn.execute("""
                        INSERT INTO sent_emails 
                        (company_id, company_name, hr_email, status, error_message, sent_date)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (company_id, company_name, hr_email, status, error_message))
                    self.logger.info(f"Inserted new record for company {company_id} ({company_name})")
                else:
                    # Update existing record with company details
                    conn.execute("""
                        UPDATE sent_emails
                        SET company_name = ?,
                            hr_email = ?,
                            status = ?,
                            error_message = ?,
                            sent_date = CURRENT_TIMESTAMP
                        WHERE company_id = ?
                    """, (company_name, hr_email, status, error_message, company_id))
                    self.logger.info(f"Updated record for company {company_id} ({company_name})")
                
                conn.commit()
                
                # Verify the update
                cursor = conn.execute("""
                    SELECT status, sent_date, company_name, hr_email FROM sent_emails 
                    WHERE company_id = ?
                """, (company_id,))
                result = cursor.fetchone()
                if result:
                    self.logger.info(f"Verified update for company {company_id} ({result[2]}): status={result[0]}, sent_date={result[1]}, email={result[3]}")
                else:
                    self.logger.error(f"Failed to verify update for company {company_id}")
                
        except Exception as e:
            self.logger.error(f"Error marking email sent in tracking database: {str(e)}")
            raise
    
    def close(self):
        """Close database connection."""
        pass  # SQLite connections are automatically closed when the context manager exits