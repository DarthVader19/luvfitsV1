"""
Manages all scrapers and orchestrates data collection with async support.
"""
import asyncio
import copy
import json
import logging
import os
from pathlib import Path
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
        self.categories = ["Tops", "Bottoms", "Accessories", "Shoes"]
        self.target_per_category = int(os.getenv("TARGET_PRODUCTS_PER_CATEGORY", "25"))
        self.fallback_products = self._load_fallback_products()

    def _load_fallback_products(self) -> List[Dict[str, Any]]:
        """Load fallback products from local JSON file."""
        default_path = Path(__file__).resolve().parents[1] / "data" / "fallback_products.json"
        print(f"Default fallback path: {default_path}")
        fallback_path = Path(os.getenv("FALLBACK_PRODUCTS_JSON", str(default_path)))
        print(f"Using fallback path: {fallback_path}")

        try:
            with open(fallback_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                logger.warning("Fallback JSON must contain a top-level list. Ignoring fallback data.")
                return []
            logger.info(f"Loaded {len(data)} fallback products from {fallback_path}")
            return data
        except FileNotFoundError:
            logger.warning(f"Fallback JSON file not found: {fallback_path}")
            return []
        except Exception as e:
            logger.warning(f"Failed to load fallback JSON from {fallback_path}: {e}")
            return []

    def _fallback_for(self, site_name: str, category: str) -> List[Dict[str, Any]]:
        return [
            p for p in self.fallback_products
            if p.get("site") == site_name and p.get("category") == category
        ]

    def _normalize_fallback_product(
        self,
        template: Dict[str, Any],
        site_name: str,
        category: str,
        index: int,
    ) -> Dict[str, Any]:
        product = copy.deepcopy(template)
        product.setdefault("currency", "USD")
        product.setdefault("color", "Unknown")
        product.setdefault("color_family", "neutral")
        product.setdefault("description", product.get("name", "Fallback product"))
        product.setdefault("image_url", "")
        product.setdefault("subcategory", None)
        product.setdefault("tags", [])
        product.setdefault("style_score", 0.5)
        product.setdefault("available", True)
        product["site"] = site_name
        product["category"] = category

        # Keep fallback URLs deterministic and unique per slot.
        base_url = product.get(
            "product_url",
            f"https://fallback.luvfits.local/{site_name.lower().replace('&', 'and')}/{category.lower()}",
        )
        separator = "&" if "?" in base_url else "?"
        product["product_url"] = (
            f"{base_url}{separator}fallback=true&slot={index}"
        )
        return product

    def _top_up_with_fallback(
        self, site_name: str, scraped_products: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Ensure each site has enough products per category by using local JSON fallback.
        """
        products = list(scraped_products)
        added = 0

        for category in self.categories:
            existing = [p for p in products if p.get("category") == category]
            missing = max(0, self.target_per_category - len(existing))
            if missing == 0:
                continue

            pool = self._fallback_for(site_name, category)
            if not pool:
                logger.warning(
                    f"{site_name}/{category}: missing {missing} products and no fallback pool available."
                )
                continue

            for i in range(missing):
                template = pool[i % len(pool)]
                products.append(
                    self._normalize_fallback_product(
                        template=template,
                        site_name=site_name,
                        category=category,
                        index=len(existing) + i + 1,
                    )
                )
                added += 1

        if added:
            logger.info(f"{site_name}: added {added} fallback products from JSON")
        return products

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
            scraped_products = await scraper.scrape()
            products = self._top_up_with_fallback(site_name, scraped_products)
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
