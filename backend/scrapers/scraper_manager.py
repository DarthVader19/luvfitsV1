"""
Manages all scrapers and orchestrates data collection with async support.
"""
import asyncio
import logging
from typing import Dict, List, Any
from datetime import datetime
from .hm_scraper import HMScraper
from .amazon_scraper import AmazonScraper
from .nordstrom_scraper import NordstromScraper
from database.db import mongodb_client
from database.models import Product, ScrapingJob

logger = logging.getLogger(__name__)


class ScraperManager:
    """Manages all scrapers and orchestrates data collection."""

    def __init__(self):
        self.scrapers = [HMScraper(), AmazonScraper(), NordstromScraper()]

    async def scrape_all(self) -> Dict[str, Any]:
        """Scrape all sites concurrently using asyncio."""
        results = {
            "total_products": 0,
            "stored_products": 0,
            "errors": 0,
            "by_site": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        tasks = []
        for scraper in self.scrapers:
            tasks.append(self._scrape_site(scraper, results))

        await asyncio.gather(*tasks)
        return results

    async def _scrape_site(
        self, scraper, results: Dict[str, Any]
    ) -> None:
        """Scrape a single site."""
        site_name = scraper.site_name
        results["by_site"][site_name] = {
            "products": 0,
            "stored": 0,
            "errors": 0,
        }

        try:
            # Create scraping job record
            job = ScrapingJob(site=site_name, status="running")
            job_id = await mongodb_client.add_scraping_job(job)

            # Scrape products
            products = await scraper.scrape()
            results["by_site"][site_name]["products"] = len(products)
            results["total_products"] += len(products)

            # Store in database
            stored = await self._store_products(products)
            results["by_site"][site_name]["stored"] = stored
            results["stored_products"] += stored

            # Update job status
            await mongodb_client.update_scraping_job(
                job_id,
                {
                    "status": "completed",
                    "products_scraped": len(products),
                    "products_stored": stored,
                    "completed_at": datetime.utcnow(),
                },
            )

            logger.info(
                f"{site_name}: Scraped {len(products)}, stored {stored} products"
            )

        except Exception as e:
            logger.error(f"Error scraping {site_name}: {e}")
            results["errors"] += 1
            results["by_site"][site_name]["errors"] = 1

    async def _store_products(self, products: List[Dict[str, Any]]) -> int:
        """Store products in MongoDB."""
        stored = 0
        for product_data in products:
            try:
                product = Product(**product_data)
                await mongodb_client.add_product(product)
                stored += 1
            except Exception as e:
                logger.warning(f"Error storing product: {e}")

        return stored

    async def refresh_all_data(self) -> Dict[str, Any]:
        """Complete refresh pipeline: scrape and store."""
        logger.info("Starting complete data refresh...")

        # Connect to MongoDB
        await mongodb_client.connect()

        try:
            # Scrape all data
            results = await self.scrape_all()
            logger.info(f"Refresh complete: {results['total_products']} products scraped, {results['stored_products']} stored")
            return results

        finally:
            await mongodb_client.disconnect()


async def main():
    """Main entry point for scraper manager."""
    manager = ScraperManager()
    results = await manager.refresh_all_data()
    print(results)


if __name__ == "__main__":
    asyncio.run(main())
