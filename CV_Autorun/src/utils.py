"""
Utility functions for the cold email automation system
"""

import os
import logging
import configparser
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, Optional, List
import smtplib
import socket

def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None):
    """Setup logging configuration"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Default log file with timestamp
    if not log_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'cold_email_{timestamp}.log'
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")

def load_config(config_file: str = 'config/settings.ini') -> configparser.ConfigParser:
    """Load configuration from INI file"""
    
    config = configparser.ConfigParser()
    config_path = Path(config_file)
    
    # Create default config if it doesn't exist
    if not config_path.exists():
        create_default_config(config_file)
    
    try:
        config.read(config_file)
        return config
    except Exception as e:
        logging.error(f"Error loading config file {config_file}: {str(e)}")
        raise

def create_default_config(config_file: str):
    """Create default configuration file"""
    
    config_dir = Path(config_file).parent
    config_dir.mkdir(parents=True, exist_ok=True)
    
    default_config = """[SMTP]
# Primary email configuration
host = smtp.gmail.com
port = 587
username = your_email@gmail.com
password = your_app_password
use_tls = true

# Additional email accounts for load balancing (optional)
# username_2 = your_second_email@gmail.com
# password_2 = your_second_app_password

[EMAIL]
# Email sending configuration
batch_delay = 60
email_delay = 2.0
max_retries = 3

[SENDER]
# Your information for email personalization
name = Your Full Name
role = Software Developer
experience = 3+ years
skills = Python, JavaScript, React, SQL, AWS
location = Available to relocate

[CAMPAIGN]
# Default campaign settings
default_batch_size = 50
default_template = default
max_daily_emails = 500

[ATTACHMENTS]
# Attachment settings
resume_path = attachments/resume.pdf
max_attachment_size = 5242880

[DATABASE]
# Database configuration
db_file = data/email_tracking.db
backup_enabled = true
cleanup_days = 30

[LOGGING]
# Logging configuration
log_level = INFO
log_file = logs/cold_email.log
"""
    
    with open(config_file, 'w') as f:
        f.write(default_config)
    
    logging.info(f"Created default configuration file: {config_file}")
    print(f"✓ Created default configuration file: {config_file}")
    print("Please edit this file with your email credentials and preferences.")

def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.match(pattern, email) is not None

def validate_smtp_config(smtp_config: Dict) -> Dict:
    """Validate SMTP configuration by testing connection"""
    
    result = {
        'valid': False,
        'error': None,
        'details': {}
    }
    
    try:
        # Test basic connectivity
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(10)
            sock.connect((smtp_config['host'], smtp_config['port']))
        
        result['details']['connectivity'] = 'OK'
        
        # Test SMTP connection
        server = smtplib.SMTP(smtp_config['host'], smtp_config['port'])
        server.set_debuglevel(0)
        server.ehlo()
        
        if smtp_config.get('use_tls', True):
            server.starttls()
            server.ehlo()
        
        result['details']['smtp_connection'] = 'OK'
        
        # Test authentication
        server.login(smtp_config['username'], smtp_config['password'])
        result['details']['authentication'] = 'OK'
        
        server.quit()
        result['valid'] = True
        
    except socket.timeout:
        result['error'] = 'Connection timeout'
    except socket.gaierror:
        result['error'] = 'DNS resolution failed'
    except smtplib.SMTPAuthenticationError:
        result['error'] = 'Authentication failed - check username/password'
    except smtplib.SMTPException as e:
        result['error'] = f'SMTP error: {str(e)}'
    except Exception as e:
        result['error'] = f'Unexpected error: {str(e)}'
    
    return result

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations"""
    # Remove or replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Ensure filename is not empty
    if not filename:
        filename = 'untitled'
    
    return filename

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024.0 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def validate_attachment(file_path: str, max_size_mb: int = 5) -> Dict:
    """Validate email attachment"""
    result = {
        'valid': False,
        'error': None,
        'size': 0,
        'size_formatted': '0 B'
    }
    
    try:
        if not os.path.exists(file_path):
            result['error'] = 'File not found'
            return result
        
        file_size = os.path.getsize(file_path)
        result['size'] = file_size
        result['size_formatted'] = format_file_size(file_size)
        
        # Check file size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            result['error'] = f'File too large ({result["size_formatted"]}). Max size: {max_size_mb} MB'
            return result
        
        # Check file extension
        allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.png']
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in allowed_extensions:
            result['error'] = f'File type {file_ext} not allowed. Allowed: {", ".join(allowed_extensions)}'
            return result
        
        result['valid'] = True
        
    except Exception as e:
        result['error'] = f'Error validating attachment: {str(e)}'
    
    return result

def get_industry_keywords() -> Dict[str, List[str]]:
    """Get industry-specific keywords for better email personalization"""
    return {
        'technology': ['innovation', 'digital transformation', 'software development', 'tech stack', 'scalability'],
        'finance': ['fintech', 'financial services', 'trading', 'investment', 'banking'],
        'healthcare': ['patient care', 'medical technology', 'healthcare innovation', 'health outcomes'],
        'education': ['learning', 'educational technology', 'student success', 'knowledge'],
        'retail': ['customer experience', 'e-commerce', 'retail technology', 'shopping'],
        'manufacturing': ['automation', 'efficiency', 'production', 'industrial'],
        'consulting': ['strategy', 'consulting', 'business solutions', 'expertise'],
        'media': ['content', 'digital media', 'entertainment', 'broadcasting'],
        'automotive': ['automotive innovation', 'transportation', 'mobility'],
        'energy': ['renewable energy', 'sustainability', 'clean tech', 'energy efficiency']
    }

def get_time_zone_info() -> Dict:
    """Get timezone information for optimal email sending"""
    return {
        'optimal_hours': {
            'weekdays': [(9, 11), (14, 16)],  # 9-11 AM and 2-4 PM
            'weekends': [(10, 12)]  # 10 AM - 12 PM
        },
        'avoid_hours': {
            'early_morning': (0, 8),
            'late_evening': (18, 23),
            'night': (23, 6)
        },
        'best_days': ['Tuesday', 'Wednesday', 'Thursday'],
        'avoid_days': ['Friday', 'Saturday', 'Sunday', 'Monday']
    }

def calculate_send_schedule(total_emails: int, daily_limit: int, 
                          start_date: Optional[datetime] = None) -> Dict:
    """Calculate optimal sending schedule"""
    if not start_date:
        start_date = datetime.now()
    
    # Conservative approach - use 80% of daily limit
    safe_daily_limit = int(daily_limit * 0.8)
    
    days_needed = (total_emails + safe_daily_limit - 1) // safe_daily_limit
    emails_per_day = total_emails // days_needed if days_needed > 0 else total_emails
    
    # Calculate batches per day
    batch_size = min(50, emails_per_day // 4)  # Aim for 4 batches per day
    if batch_size < 1:
        batch_size = 1
    
    batches_per_day = (emails_per_day + batch_size - 1) // batch_size
    
    # Calculate delay between batches (spread over 8 hours)
    if batches_per_day > 1:
        delay_minutes = (8 * 60) // (batches_per_day - 1)
    else:
        delay_minutes = 0
    
    return {
        'total_emails': total_emails,
        'daily_limit': daily_limit,
        'safe_daily_limit': safe_daily_limit,
        'days_needed': days_needed,
        'emails_per_day': emails_per_day,
        'batch_size': batch_size,
        'batches_per_day': batches_per_day,
        'delay_between_batches_minutes': delay_minutes,
        'estimated_completion': start_date.strftime('%Y-%m-%d')
    }

def check_dependencies() -> Dict:
    """Check if all required dependencies are installed"""
    required_packages = [
        'pandas',
        'openpyxl',
        'tqdm',
        'sqlite3'  # Built-in, should always be available
    ]
    
    results = {
        'all_installed': True,
        'packages': {}
    }
    
    for package in required_packages:
        try:
            if package == 'sqlite3':
                import sqlite3
            else:
                __import__(package)
            
            results['packages'][package] = 'installed'
        except ImportError:
            results['packages'][package] = 'missing'
            results['all_installed'] = False
    
    return results

def create_directory_structure():
    """Create necessary directory structure for the application"""
    directories = [
        'config',
        'config/email_templates',
        'data',
        'logs',
        'attachments',
        'reports'
    ]
    
    created_dirs = []
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(directory)
    
    if created_dirs:
        logging.info(f"Created directories: {', '.join(created_dirs)}")
    
    return created_dirs

def backup_database(db_file: str, backup_dir: str = 'backups') -> str:
    """Create backup of the database"""
    import shutil
    
    if not os.path.exists(db_file):
        raise FileNotFoundError(f"Database file not found: {db_file}")
    
    # Create backup directory
    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)
    
    # Create backup filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"email_tracking_backup_{timestamp}.db"
    backup_file = backup_path / backup_filename
    
    # Copy database file
    shutil.copy2(db_file, backup_file)
    
    logging.info(f"Database backed up to: {backup_file}")
    return str(backup_file)

def generate_progress_report(current: int, total: int, start_time: datetime) -> str:
    """Generate progress report string"""
    if total == 0:
        return "No items to process"
    
    percentage = (current / total) * 100
    elapsed_time = datetime.now() - start_time
    
    if current > 0:
        estimated_total_time = elapsed_time * (total / current)
        remaining_time = estimated_total_time - elapsed_time
        
        return (f"Progress: {current}/{total} ({percentage:.1f}%) | "
                f"Elapsed: {str(elapsed_time).split('.')[0]} | "
                f"Remaining: {str(remaining_time).split('.')[0]}")
    else:
        return f"Progress: {current}/{total} ({percentage:.1f}%) | Just started..."

def validate_company_data(df) -> Dict:
    """Validate company data from Excel file"""
    issues = {
        'errors': [],
        'warnings': [],
        'stats': {}
    }
    
    # Check required columns
    required_columns = ['company_name', 'hr_email']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        issues['errors'].append(f"Missing required columns: {', '.join(missing_columns)}")
        return issues
    
    # Check for empty required fields
    empty_company_names = df['company_name'].isna().sum()
    empty_emails = df['hr_email'].isna().sum()
    
    if empty_company_names > 0:
        issues['warnings'].append(f"{empty_company_names} rows have empty company names")
    
    if empty_emails > 0:
        issues['warnings'].append(f"{empty_emails} rows have empty email addresses")
    
    # Validate email formats
    valid_emails = df['hr_email'].dropna().apply(validate_email)
    invalid_email_count = (~valid_emails).sum()
    
    if invalid_email_count > 0:
        issues['warnings'].append(f"{invalid_email_count} rows have invalid email formats")
    
    # Check for duplicates
    duplicate_emails = df['hr_email'].dropna().duplicated().sum()
    if duplicate_emails > 0:
        issues['warnings'].append(f"{duplicate_emails} duplicate email addresses found")
    
    # Statistics
    issues['stats'] = {
        'total_rows': len(df),
        'valid_companies': len(df.dropna(subset=['company_name', 'hr_email'])),
        'unique_emails': df['hr_email'].dropna().nunique(),
        'completion_rate': len(df.dropna(subset=['company_name', 'hr_email'])) / len(df) * 100
    }
    
    return issues