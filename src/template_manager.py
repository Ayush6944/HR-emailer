import logging
import os
from typing import Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TemplateManager:
    def __init__(self):
        """Initialize the template manager."""
        self.templates_dir = 'data/templates'
        self.templates = {}
        self._load_templates()
        logger.info("Template manager initialized with HTML template")

    def _load_templates(self):
        """Load all templates from the templates directory."""
        try:
            # Load job inquiry template
            job_inquiry_path = os.path.join(self.templates_dir, 'job_inquiry.html')
            if os.path.exists(job_inquiry_path):
                with open(job_inquiry_path, 'r', encoding='utf-8') as f:
                    self.templates['job_inquiry'] = {
                        'subject': 'Application for {position} at {company_name}',
                        'body': f.read(),
                        'is_html': True,
                        'attachments': ['resume.pdf']
                    }
            else:
                logger.warning(f"Job inquiry template not found at {job_inquiry_path}")
                
        except Exception as e:
            logger.error(f"Error loading templates: {str(e)}")
            raise

    def get_template(self, template_name: str = 'job_inquiry') -> Dict[str, Any]:
        """Get a template by name."""
        try:
            if template_name not in self.templates:
                raise ValueError(f"Template '{template_name}' not found")
            return self.templates[template_name]
        except Exception as e:
            logger.error(f"Error getting template: {str(e)}")
            raise

    def format_template(self, template: Dict[str, Any], **kwargs) -> str:
        """Format a template with the given parameters."""
        try:
            # Format the body
            body = template['body']
            for key, value in kwargs.items():
                placeholder = '{' + key + '}'
                body = body.replace(placeholder, str(value))
            
            return body
        except Exception as e:
            logger.error(f"Error formatting template: {str(e)}")
            raise 