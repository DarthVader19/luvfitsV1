#intial data scrape to populate the database with the initial data
import asyncio
from backend.scrapers.scraper_manager import ScraperManager
from database.models import init_db

async def initial_scrape():
    """Perform initial data scrape to populate the database."""
    print("Starting initial data scrape...")
    
    # Initialize database
    init_db()
    
    # Create scraper manager and run scrape
    manager = ScraperManager()
    results = await manager.scrape_all()
    
    print(f"Initial scrape completed. Total products: {results.get('total_products', 0)}")