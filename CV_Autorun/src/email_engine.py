"""
Email Engine for sending personalized emails with rate limiting and error handling
"""

import smtplib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, List, Optional, Tuple, Any
import os
from pathlib import Path
import random
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)

class EmailEngine:
    """Handles email sending with SMTP, rate limiting, and error handling"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize email engine with SMTP configuration"""
        self.smtp_server = config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.sender_email = config.get('sender_email', '')
        self.sender_password = config.get('sender_password', '')
        self.use_tls = config.get('use_tls', True)
        
        # Rate limiting settings
        self.batch_delay = config.get('batch_delay', 60)
        self.max_retries = config.get('max_retries', 3)
        
        if not self.sender_email or not self.sender_password:
            raise ValueError("Email credentials not configured")
            
        logger.info(f"Email engine initialized with SMTP server: {self.smtp_server}:{self.smtp_port}")
    
    def _send_email(self, to_email: str, subject: str, content: str, is_html: bool = False, attachments: Optional[List[str]] = None):
        """Send a single email with optional attachments."""
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add body
            if is_html:
                msg.attach(MIMEText(content, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(content, 'plain'))
            
            # Add attachments
            if attachments:
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        with open(attachment_path, 'rb') as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                            msg.attach(part)
                            logger.info(f"Attached {os.path.basename(attachment_path)} to email")
                    else:
                        logger.warning(f"Attachment not found: {attachment_path}")
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            raise
    
    def send_batch(self, emails: List[Dict[str, str]], template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Send a batch of emails using the provided template."""
        results = []
        
        for email_data in emails:
            try:
                # Add random delay between emails
                time.sleep(self.batch_delay + random.uniform(1, 5))
                
                # Format email content using template manager
                from template_manager import TemplateManager
                template_manager = TemplateManager()
                content = template_manager.format_template(
                    template,
                    company_name=email_data['company_name'],
                    hr_email=email_data['hr_email'],
                    hr_name="HR Manager",
                    position=email_data.get('position', 'Software Engineer')
                )
                
                # Format subject with default position if not provided
                subject = template['subject'].format(
                    company_name=email_data['company_name'],
                    position=email_data.get('position', 'Software Engineer')
                )
                
                # Send email with retries
                success = False
                for attempt in range(self.max_retries):
                    try:
                        self._send_email(
                            to_email=email_data['hr_email'],
                            subject=subject,
                            content=content,
                            is_html=template.get('is_html', True),
                            attachments=template.get('attachments', [])
                        )
                        success = True
                        break
                    except Exception as e:
                        if attempt < self.max_retries - 1:
                            wait_time = (2 ** attempt) + random.uniform(1, 5)
                            logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {wait_time:.1f}s: {str(e)}")
                            time.sleep(wait_time)
                        else:
                            raise
                
                results.append({
                    'company_id': email_data.get('company_id'),
                    'company_name': email_data['company_name'],
                    'hr_email': email_data['hr_email'],
                    'success': success,
                    'error': None
                })
                
            except Exception as e:
                logger.error(f"Failed to send email to {email_data['hr_email']}: {str(e)}")
                results.append({
                    'company_id': email_data.get('company_id'),
                    'company_name': email_data['company_name'],
                    'hr_email': email_data['hr_email'],
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def _personalize_content(self, template: str, company_data: Dict) -> str:
        """Personalize email content with company data"""
        try:
            # Standard replacements
            replacements = {
                '{company_name}': company_data.get('company_name', 'Your Company'),
                '{hr_name}': company_data.get('hr_name', 'HR Team'),
                '{hr_email}': company_data.get('hr_email', ''),
                '{industry}': company_data.get('industry', 'your industry'),
                '{location}': company_data.get('location', 'your location'),
                '{company_size}': company_data.get('company_size', 'your organization'),
                
                # Sender information
                '{sender_name}': self.config.get('SENDER', 'name', fallback='Job Seeker'),
                '{sender_role}': self.config.get('SENDER', 'role', fallback='Software Developer'),
                '{sender_experience}': self.config.get('SENDER', 'experience', fallback='3+ years'),
                '{sender_skills}': self.config.get('SENDER', 'skills', fallback='Python, JavaScript, SQL'),
                '{sender_location}': self.config.get('SENDER', 'location', fallback='Available to relocate'),
                
                # Dynamic content based on industry
                '{industry_note}': self._get_industry_note(company_data.get('industry', '')),
                '{role_interest}': self._get_role_interest(company_data.get('industry', '')),
            }
            
            # Perform replacements
            personalized = template
            for placeholder, value in replacements.items():
                personalized = personalized.replace(placeholder, str(value))
            
            return personalized
            
        except Exception as e:
            logger.error(f"Error personalizing content: {str(e)}")
            return template
    
    def _get_industry_note(self, industry: str) -> str:
        """Generate industry-specific notes"""
        industry_lower = industry.lower()
        
        industry_notes = {
            'technology': "I'm particularly excited about the innovation in tech",
            'finance': "I'm interested in the fintech revolution and financial technology",
            'healthcare': "I'm passionate about technology's impact on healthcare",
            'education': "I believe technology can transform education",
            'retail': "I'm fascinated by e-commerce and retail technology",
            'manufacturing': "I'm interested in industrial automation and smart manufacturing",
            'consulting': "I appreciate the diverse challenges in consulting",
            'media': "I'm excited about digital media and content technology",
            'automotive': "I'm passionate about automotive technology and innovation",
            'energy': "I'm interested in clean energy and sustainable technology"
        }
        
        for key, note in industry_notes.items():
            if key in industry_lower:
                return note
        
        return "I'm excited about the opportunities in your industry"
    
    def _get_role_interest(self, industry: str) -> str:
        """Generate role interest based on industry"""
        industry_lower = industry.lower()
        
        role_interests = {
            'technology': "Software Engineer, Full Stack Developer, or Backend Developer",
            'finance': "Software Developer, Fintech Engineer, or Quantitative Developer",
            'healthcare': "Healthcare Software Developer or Health Tech Engineer",
            'education': "EdTech Developer or Educational Software Engineer",
            'retail': "E-commerce Developer or Retail Technology Engineer",
            'manufacturing': "Industrial Software Developer or Automation Engineer",
            'consulting': "Technical Consultant or Software Developer",
            'media': "Media Technology Developer or Digital Platform Engineer",
            'automotive': "Automotive Software Engineer or Embedded Systems Developer",
            'energy': "Energy Software Developer or Clean Tech Engineer"
        }
        
        for key, role in role_interests.items():
            if key in industry_lower:
                return role
        
        return "Software Developer, Full Stack Engineer, or Backend Developer"
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """Add file attachment to email"""
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Attachment file not found: {file_path}")
                return
            
            with open(file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(file_path)}'
            )
            
            msg.attach(part)
            logger.debug(f"Added attachment: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to add attachment {file_path}: {str(e)}")
    
    def test_smtp_connection(self) -> Dict:
        """Test SMTP connections for all configured accounts"""
        results = {}
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.sender_email, self.sender_password)
                results['status'] = 'success'
                results['message'] = 'Connection successful'
        except Exception as e:
            results['status'] = 'failed'
            results['message'] = str(e)
        
        return results
    
    def get_daily_send_limit(self) -> int:
        """Get daily send limit based on email provider"""
        # Conservative limits to avoid being flagged as spam
        provider_limits = {
            'gmail.com': 500,
            'outlook.com': 300,
            'hotmail.com': 300,
            'yahoo.com': 100
        }
        
        if self.smtp_server:
            domain = self.smtp_server.split('@')[1].lower()
            return provider_limits.get(domain, 100)
        
        return 100