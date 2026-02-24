import logging
import schedule
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scrapers.scraper_manager import ScraperManager
from database.models import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def refresh():
    """Execute data refresh"""
    logger.info("Starting scheduled data refresh...")
    try:
        # Initialize database
        init_db()
        
        # Scrape and save
        manager = ScraperManager()
        results = manager.refresh_all_data()
        logger.info(f"Refresh completed. Total products: {results.get('total_products', 0)}")
        return results
    except Exception as e:
        logger.error(f"Error during refresh: {str(e)}", exc_info=True)
        return None

def schedule_refresh(interval_hours: int = 24):
    """Schedule refresh at regular intervals"""
    schedule.every(interval_hours).hours.do(refresh)
    logger.info(f"Scheduled refresh every {interval_hours} hours")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Run once on startup
    refresh()
    # Uncomment to schedule periodic refreshes
    # schedule_refresh(24)