import logging
import asyncio
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scrapers.scraper_manager import ScraperManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _refresh_async():
    """Execute async data refresh using the MongoDB pipeline."""
    manager = ScraperManager()
    return await manager.refresh_all_data()


def refresh():
    """Execute data refresh."""
    logger.info("Starting scheduled data refresh...")
    try:
        results = asyncio.run(_refresh_async())
        logger.info(f"Refresh completed. Total products: {results.get('total_products', 0)}, Outfits: {results.get('outfits_generated', 0)}")
        return results
    except Exception as e:
        logger.error(f"Error during refresh: {str(e)}", exc_info=True)
        return None


def schedule_refresh(interval_hours: int = 24):
    """Schedule refresh at regular intervals without extra dependencies."""
    interval_seconds = max(1, int(interval_hours * 3600))
    logger.info(f"Scheduled refresh every {interval_hours} hours")

    while True:
        refresh()
        time.sleep(interval_seconds)



if __name__ == "__main__":
    # Run once on startup
    results = refresh()
    if results:
        print(f"Refresh complete. Outfits generated: {results.get('outfits_generated', 0)}")
    # Uncomment to schedule periodic refreshes
    # schedule_refresh(24)
