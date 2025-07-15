"""
Report Generator for creating Excel reports of email campaigns
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, List

class ReportGenerator:
    """Generates Excel reports for email campaigns"""
    
    def __init__(self, reports_dir: str = "reports"):
        self.logger = logging.getLogger(__name__)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self, sent_emails: List[Dict], campaign_name: str) -> str:
        """Generate an Excel report for a campaign"""
        try:
            # Convert sent emails data to DataFrame
            df = pd.DataFrame(sent_emails)
            
            # Add timestamp column
            df['sent_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Select only required columns
            columns = ['company_name', 'hr_email', 'sent_timestamp']
            
            # Ensure all columns exist
            for col in columns:
                if col not in df.columns:
                    df[col] = ''
            
            # Select only required columns
            df = df[columns]
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"campaign_report_{campaign_name}_{timestamp}.xlsx"
            filepath = self.reports_dir / filename
            
            # Create Excel writer
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Write main data
                df.to_excel(writer, sheet_name='Sent Emails', index=False)
                
                # Get the worksheet
                worksheet = writer.sheets['Sent Emails']
                
                # Auto-adjust column widths
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(col)
                    )
                    worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
            
            self.logger.info(f"Generated campaign report: {filename}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error generating campaign report: {str(e)}")
            raise
    
    def generate_summary_report(self, campaign_stats: Dict) -> str:
        """Generate a summary report of all campaigns"""
        try:
            # Create summary DataFrame
            summary_data = {
                'Campaign Name': [],
                'Date': [],
                'Total Sent': [],
                'Success Rate': []
            }
            
            # Add campaign statistics
            for campaign in campaign_stats.get('recent_campaigns', []):
                summary_data['Campaign Name'].append(campaign.get('name', 'Unknown'))
                summary_data['Date'].append(campaign.get('date', 'Unknown'))
                summary_data['Total Sent'].append(campaign.get('sent', 0))
                success_rate = campaign.get('success_rate', 0)
                summary_data['Success Rate'].append(f"{success_rate:.2f}%")
            
            # Create DataFrame
            df = pd.DataFrame(summary_data)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"campaign_summary_{timestamp}.xlsx"
            filepath = self.reports_dir / filename
            
            # Create Excel writer
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Write summary data
                df.to_excel(writer, sheet_name='Campaign Summary', index=False)
                
                # Write overall statistics
                overall_stats = pd.DataFrame([{
                    'Total Emails Sent': campaign_stats.get('total_sent', 0),
                    'Overall Success Rate': f"{campaign_stats.get('success_rate', 0):.2f}%"
                }])
                overall_stats.to_excel(writer, sheet_name='Overall Statistics', index=False)
                
                # Get the worksheets
                summary_sheet = writer.sheets['Campaign Summary']
                stats_sheet = writer.sheets['Overall Statistics']
                
                # Auto-adjust column widths
                for sheet in [summary_sheet, stats_sheet]:
                    for idx, col in enumerate(df.columns):
                        max_length = max(
                            df[col].astype(str).apply(len).max(),
                            len(col)
                        )
                        sheet.column_dimensions[chr(65 + idx)].width = max_length + 2
            
            self.logger.info(f"Generated summary report: {filename}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error generating summary report: {str(e)}")
            raise 