import logging
import pandas as pd
from data_manager import DataManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_companies(excel_path: str):
    """Load companies from Excel file into database."""
    try:
        # Initialize data manager
        data_manager = DataManager()
        
        # Load companies
        count = data_manager.load_companies(excel_path)
        logger.info(f"Successfully loaded {count} companies into database")
        
    except Exception as e:
        logger.error(f"Error loading companies: {str(e)}")
        raise

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python load_companies.py <excel_file>")
        sys.exit(1)
        
    excel_path = sys.argv[1]
    load_companies(excel_path) 