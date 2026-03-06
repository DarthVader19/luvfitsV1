#intial data scrape to populate the database with the initial data
import asyncio
from scrapers.scraper_manager import ScraperManager

async def initial_scrape():
    """Perform initial data scrape to populate the database."""
    print("Starting initial data scrape...")

    # Create scraper manager and run scrape
    manager = ScraperManager()
    results = await manager.refresh_all_data()

    print(f"Initial scrape completed. Total products: {results.get('total_products', 0)}")


if __name__ == "__main__":
    asyncio.run(initial_scrape())
