import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_position_column():
    db_path = 'data/companies.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Check if 'position' column exists
        cursor.execute("PRAGMA table_info(companies)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'position' not in columns:
            logger.info("Adding 'position' column to companies table...")
            cursor.execute("ALTER TABLE companies ADD COLUMN position TEXT DEFAULT 'Software Engineer'")
            conn.commit()
            logger.info("'position' column added successfully.")
        else:
            logger.info("'position' column already exists. No changes made.")
        # Update all NULLs to default value
        cursor.execute("UPDATE companies SET position = 'Software Engineer' WHERE position IS NULL")
        conn.commit()
        logger.info("All NULL positions set to 'Software Engineer'.")
    except Exception as e:
        logger.error(f"Error updating companies table: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_position_column() 