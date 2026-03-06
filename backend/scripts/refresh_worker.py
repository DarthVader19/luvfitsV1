"""
Background worker for scheduled data refresh using APScheduler.
Handles daily scraping, embedding generation, and outfit creation.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scrapers.scraper_manager import ScraperManager
from logic.embedding_search import embedding_service
from logic.outfit_builder import outfit_builder
from logic.google_taxonomy import TaxonomyEnhancer
from database.db import mongodb_client
from database.models import Product

logger = logging.getLogger(__name__)


class RefreshWorker:
    """Manages background refresh tasks."""

    def __init__(self):
        """Initialize refresh worker."""
        self.scheduler = BackgroundScheduler()
        self.scraper_manager = ScraperManager()
        self.is_running = False

    def start(self):
        """Start background scheduler."""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        # Schedule daily refresh at 2 AM
        self.scheduler.add_job(
            func=self.refresh_all,
            trigger=CronTrigger(hour=2, minute=0),
            id="daily_refresh",
            name="Daily data refresh",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("Background scheduler started")

    def stop(self):
        """Stop background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Background scheduler stopped")

    def refresh_all(self):
        """Execute full refresh pipeline."""
        logger.info("=== Starting full data refresh ===")

        try:
            # Run async refresh in event loop
            asyncio.run(self._async_refresh())
        except Exception as e:
            logger.error(f"Error during refresh: {e}")

    async def _async_refresh(self):
        """Async refresh pipeline."""
        # 1. Connect to database
        await mongodb_client.connect()

        try:
            # 2. Scrape products
            logger.info("Step 1: Scraping products...")
            scrape_results = await self.scraper_manager.scrape_all()
            logger.info(
                f"Scraped {scrape_results['total_products']} products, "
                f"stored {scrape_results['stored_products']}"
            )

            # 3. Get all products for embedding
            logger.info("Step 2: Generating embeddings...")
            all_products = []
            skip = 0
            while True:
                batch = await mongodb_client.get_all_products(
                    skip=skip, limit=100
                )
                if not batch:
                    break
                all_products.extend(batch)
                skip += 100

            # 4. Generate embeddings
            await embedding_service.embed_products(all_products)
            logger.info(f"Embedded {len(all_products)} products")

            # 5. Create outfits
            logger.info("Step 3: Generating outfits...")
            outfits = await outfit_builder.create_outfits(num_outfits=50)
            saved = await outfit_builder.save_outfits(outfits)
            logger.info(f"Generated and saved {saved} outfits")

            logger.info("=== Data refresh complete ===")

        finally:
            await mongodb_client.disconnect()

    async def on_demand_refresh(self) -> dict:
        """
        Execute refresh on-demand (e.g., from API endpoint).
        
        Returns:
            Refresh results summary
        """
        logger.info("On-demand refresh triggered")

        await mongodb_client.connect()

        try:
            results = await self._async_refresh()
            return {
                "status": "success",
                "message": "Refresh completed successfully",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"On-demand refresh failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

        finally:
            await mongodb_client.disconnect()

    def quick_scrape(self):
        """Quick scrape of just one site (for testing)."""
        logger.info("Quick scrape triggered")

        try:
            asyncio.run(self._quick_scrape_async())
        except Exception as e:
            logger.error(f"Quick scrape failed: {e}")

    async def _quick_scrape_async(self):
        """Async quick scrape."""
        await mongodb_client.connect()

        try:
            scraper = self.scraper_manager.scrapers[0]  # H&M
            products = await scraper.scrape()
            logger.info(f"Quick scrape: Got {len(products)} products")

        finally:
            await mongodb_client.disconnect()

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self.scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time),
                }
                for job in self.scheduler.get_jobs()
            ],
        }


# Global worker instance
refresh_worker = RefreshWorker()


# Convenience functions for quick access

def start_refresh_worker():
    """Start the background refresh worker."""
    refresh_worker.start()


def stop_refresh_worker():
    """Stop the background refresh worker."""
    refresh_worker.stop()


def trigger_on_demand_refresh():
    """Trigger on-demand refresh."""
    return refresh_worker.on_demand_refresh()


def get_worker_status():
    """Get worker status."""
    return refresh_worker.get_status()
