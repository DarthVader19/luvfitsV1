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
        self.scrapers = [ AmazonScraper(),HMScraper()] #HMScraper(),, NordstromScraper()
        self.categories = ["Tops", "Bottoms", "Accessories", "Shoes"]
        self.target_per_category = int(os.getenv("TARGET_PRODUCTS_PER_CATEGORY", "25"))
        self.fallback_products = self._load_fallback_products()
        self.data_folder = Path(__file__).resolve().parents[1] / "data"

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

    def _save_products_to_json(self, products: List[Dict[str, Any]], site_name: str, product_type: str = "real") -> None:
        """Save products to a JSON file for the given site and type (real or fallback)."""
        try:
            # Ensure data folder exists
            self.data_folder.mkdir(parents=True, exist_ok=True)

            # Save site-specific products file with type prefix
            site_filename = f"{site_name.lower().replace('&', 'and').replace(' ', '_')}_{product_type}_products.json"
            site_filepath = self.data_folder / site_filename

            with open(site_filepath, "w", encoding="utf-8") as fh:
                json.dump(products, fh, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Saved {len(products)} {product_type} products to {site_filepath}")

        except Exception as e:
            logger.warning(f"Failed to save {product_type} products to JSON for {site_name}: {e}")

    def _save_all_products_to_json(self, all_products: List[Dict[str, Any]], product_type: str = "real") -> None:
        """Save all products from all sites to a consolidated JSON file."""
        try:
            # Ensure data folder exists
            self.data_folder.mkdir(parents=True, exist_ok=True)

            # Save consolidated all products file
            all_filepath = self.data_folder / f"all_{product_type}_products.json"

            with open(all_filepath, "w", encoding="utf-8") as fh:
                json.dump(all_products, fh, indent=2, ensure_ascii=False, default=str)

            logger.info(f"Saved {len(all_products)} total {product_type} products to {all_filepath}")

        except Exception as e:
            logger.warning(f"Failed to save all {product_type} products to JSON: {e}")

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
    ) -> tuple:
        """
        Ensure each site has enough products per category by using local JSON fallback.
        Returns (real_products, fallback_products) tuple.
        """
        real_products = list(scraped_products)
        fallback_products = []
        added = 0

        for category in self.categories:
            existing = [p for p in real_products if p.get("category") == category]
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
                fallback_product = self._normalize_fallback_product(
                    template=template,
                    site_name=site_name,
                    category=category,
                    index=len(existing) + i + 1,
                )
                fallback_products.append(fallback_product)
                added += 1

        if added:
            logger.info(f"{site_name}: added {added} fallback products from JSON")
        
        return real_products, fallback_products

    async def scrape_all(self) -> Dict[str, Any]:
        """Scrape all sites concurrently using asyncio."""
        results = {
            "total_products": 0,
            "total_fallback": 0,
            "stored_products": 0,
            "stored_fallback": 0,
            "errors": 0,
            "by_site": {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        all_real_products = []  # Track real products
        all_fallback_products = []  # Track fallback products

        tasks = []
        for scraper in self.scrapers:
            tasks.append(self._scrape_site(scraper, results, all_real_products, all_fallback_products))

        await asyncio.gather(*tasks)

        # Save all products to consolidated JSON files
        self._save_all_products_to_json(all_real_products, "real")
        self._save_all_products_to_json(all_fallback_products, "fallback")

        return results

    async def _scrape_site(
        self, scraper, results: Dict[str, Any], all_real_products: List[Dict[str, Any]], all_fallback_products: List[Dict[str, Any]]
    ) -> None:
        """Scrape a single site."""
        site_name = scraper.site_name
        results["by_site"][site_name] = {
            "products": 0,
            "fallback": 0,
            "stored": 0,
            "stored_fallback": 0,
            "errors": 0,
        }

        try:
            # Create scraping job record
            job = ScrapingJob(site=site_name, status="running")
            job_id = await mongodb_client.add_scraping_job(job)

            # Scrape products
            scraped_products = await scraper.scrape()
            real_products, fallback_products = self._top_up_with_fallback(site_name, scraped_products)
            
            results["by_site"][site_name]["products"] = len(real_products)
            results["by_site"][site_name]["fallback"] = len(fallback_products)
            results["total_products"] += len(real_products)
            results["total_fallback"] += len(fallback_products)

            # Store in database and JSON
            stored_real = await self._store_real_products(real_products, site_name)
            stored_fallback = await self._store_fallback_products(fallback_products, site_name)
            
            results["by_site"][site_name]["stored"] = stored_real
            results["by_site"][site_name]["stored_fallback"] = stored_fallback
            results["stored_products"] += stored_real
            results["stored_fallback"] += stored_fallback

            # Add to consolidated lists
            all_real_products.extend(real_products)
            all_fallback_products.extend(fallback_products)

            # Update job status
            await mongodb_client.update_scraping_job(
                job_id,
                {
                    "status": "completed",
                    "products_scraped": len(real_products),
                    "products_stored": stored_real,
                    "completed_at": datetime.utcnow(),
                },
            )

            logger.info(
                f"{site_name}: Scraped {len(real_products)} real products, {len(fallback_products)} fallback; stored {stored_real} real, {stored_fallback} fallback"
            )

        except Exception as e:
            logger.error(f"Error scraping {site_name}: {e}")
            results["errors"] += 1
            results["by_site"][site_name]["errors"] = 1

    async def _store_real_products(self, products: List[Dict[str, Any]], site_name: str = None) -> int:
        """Store real products in MongoDB products collection and JSON file."""
        stored = 0
        for product_data in products:
            try:
                product = Product(**product_data)
                await mongodb_client.add_product(product)
                stored += 1
            except Exception as e:
                logger.warning(f"Error storing real product: {e}")

        # Save to JSON file after MongoDB storage
        if site_name:
            self._save_products_to_json(products, site_name, "real")

        return stored

    async def _store_fallback_products(self, products: List[Dict[str, Any]], site_name: str = None) -> int:
        """Store fallback products in MongoDB fallback_products collection and JSON file."""
        stored = 0
        for product_data in products:
            try:
                product = Product(**product_data)
                await mongodb_client.add_fallback_product(product)
                stored += 1
            except Exception as e:
                logger.warning(f"Error storing fallback product: {e}")

        # Save to JSON file after MongoDB storage
        if site_name:
            self._save_products_to_json(products, site_name, "fallback")

        return stored

    async def refresh_all_data(self) -> Dict[str, Any]:
        """Complete refresh pipeline: scrape and store products, then generate outfits."""
        logger.info("Starting complete data refresh...")

        # Connect to MongoDB
        await mongodb_client.connect()

        try:
            # Pre-load the AI model before scraping
            logger.info("Pre-loading AI model for vibe extraction...")
            try:
                from scrapers.base_scraper import ModelCache
                await ModelCache.get_instance()
                logger.info("AI model pre-loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to pre-load model: {e}. Continuing without optimization...")

            # Scrape all data
            logger.info("Phase 1: Scraping products...")
            results = await self.scrape_all()
            logger.info(f"Scraping complete: {results['total_products']} products total, {results['stored_products']} stored")
            
            # Generate outfits from scraped products
            logger.info("Phase 2: Generating outfits from scraped products...")
            try:
                from logic.outfit_builder import outfit_builder
                outfits = await outfit_builder.create_outfits(num_outfits=50)
                logger.info(f"Created {len(outfits)} outfit combinations")
                
                if outfits:
                    saved_outfits = await outfit_builder.save_outfits(outfits)
                    results['outfits_generated'] = saved_outfits
                    logger.info(f"Successfully saved {saved_outfits} outfits to database")
                else:
                    logger.warning("No outfits were generated (insufficient products or all combinations scored too low)")
                    results['outfits_generated'] = 0
            except Exception as e:
                logger.error(f"Error during outfit generation/saving: {e}", exc_info=True)
                results['outfits_generated'] = 0
            
            logger.info(f"Refresh pipeline complete: {results['total_products']} products, {results['outfits_generated']} outfits")
            return results

        except Exception as e:
            logger.error(f"Error during refresh pipeline: {e}", exc_info=True)
            raise
        finally:
            await mongodb_client.disconnect()
            logger.info("MongoDB connection closed")


async def main():
    """Main entry point for scraper manager."""
    manager = ScraperManager()
    results = await manager.refresh_all_data()
    print(results)


if __name__ == "__main__":
    asyncio.run(main())
