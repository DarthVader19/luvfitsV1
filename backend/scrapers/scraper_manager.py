import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrapers.hm_scraper import HMScraper
from scrapers.amazon_scraper import AmazonScraper
from scrapers.nordstrom_scraper import NordstromScraper
from database.models import SessionLocal, Product, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScraperManager:
    """Manages all scrapers and orchestrates data collection"""
    
    CATEGORIES = ["Tops", "Bottoms", "Accessories", "Shoes"]
    PRODUCTS_PER_CATEGORY = 25
    
    def __init__(self):
        self.scrapers = [HMScraper(), AmazonScraper(), NordstromScraper()]
        
    def scrape_all(self, max_workers: int = 3) -> dict:
        """Scrape all sites concurrently"""
        results = {
            'total_products': 0,
            'success': 0,
            'errors': 0,
            'by_site': {}
        }
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for scraper in self.scrapers:
                for category in self.CATEGORIES:
                    future = executor.submit(
                        scraper.scrape, 
                        category, 
                        self.PRODUCTS_PER_CATEGORY
                    )
                    futures[future] = (scraper.site_name, category)
            
            for future in as_completed(futures):
                site_name, category = futures[future]
                try:
                    products = future.result()
                    if site_name not in results['by_site']:
                        results['by_site'][site_name] = {'success': 0, 'products': []}
                    
                    results['by_site'][site_name]['products'].extend(products)
                    results['by_site'][site_name]['success'] += len(products)
                    results['total_products'] += len(products)
                    results['success'] += 1
                    
                    logger.info(f"Scraped {len(products)} products from {site_name} - {category}")
                except Exception as e:
                    results['errors'] += 1
                    logger.error(f"Error scraping {site_name} - {category}: {str(e)}")
        
        return results
    
    def save_to_database(self, products: list):
        """Save products to database"""
        session = SessionLocal()
        try:
            # Delete duplicates based on product_url
            for product in products:
                existing = session.query(Product).filter(
                    Product.product_url == product.get('product_url')
                ).first()
                
                if not existing:
                    db_product = Product(
                        name=product.get('name'),
                        price=product.get('price', 0),
                        color=product.get('color', ''),
                        description=product.get('description', ''),
                        image_url=product.get('image_url', ''),
                        product_url=product.get('product_url'),
                        category=product.get('category'),
                        site=product.get('site'),
                        tags=product.get('tags', ''),
                        color_family=product.get('color_family', 'neutral'),
                        style_score=0.5  # Default, can be improved
                    )
                    session.add(db_product)
            session.commit()
            logger.info("Products saved to database successfully")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving to database: {str(e)}")
        finally:
            session.close()
    
    def refresh_all_data(self):
        """Complete refresh pipeline"""
        logger.info("Starting complete data refresh...")
        
        # Initialize database tables
        init_db()
        logger.info("Database initialized")
        
        # Clear old data
        session = SessionLocal()
        try:
            session.query(Product).delete()
            session.commit()
            logger.info("Cleared old product data")
        except Exception as e:
            session.rollback()
            logger.warning(f"Could not clear old data: {str(e)}")
        finally:
            session.close()
        
        # Scrape new data
        results = self.scrape_all()
        logger.info(f"Scraping results: {results['total_products']} products, {results['errors']} errors")
        
        # Collect all products
        all_products = []
        for site_data in results['by_site'].values():
            all_products.extend(site_data['products'])
        
        # Save to database
        self.save_to_database(all_products)
        
        logger.info(f"Data refresh complete. Total products in database: {len(all_products)}")
        return results

if __name__ == "__main__":
    manager = ScraperManager()
    manager.refresh_all_data()
