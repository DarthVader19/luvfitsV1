#refresh product and outfit data tags in database and regenerate tags for all products

import datetime
import logging
import asyncio

import sys 

# Add parent directory to path for imports
import os
import json   
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    

from database.db import mongodb_client
from database.models import Product
from scrapers.base_scraper import ProductExtractor, ModelCache, VibeExtractor
logger = logging.getLogger(__name__)

async def refresh_tags():
    """Refresh product tags in database."""
    # Configure logging to see debug messages
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    await mongodb_client.connect()
    
    # Pre-load the model once before processing all products
    logger.info("Pre-loading AI model...")
    try:
        await ModelCache.get_instance()
        logger.info("AI model pre-loaded successfully")
    except Exception as e:
        logger.error(f"Failed to pre-load model: {e}", exc_info=True)
        return

    # Get all products
    products = await mongodb_client.get_all_products(limit=1000)
    logger.info(f"Refreshing tags for {len(products)} products...")
    
    success_count = 0
    failed_count = 0
    no_tags_count = 0

    for i, product in enumerate(products):
        try:
            # Regenerate tags using vibe extractor logic in base scraper
            logger.info(f"[{i+1}/{len(products)}] Processing product {product.id}: {product.name[:50]}...")
            new_tags = await ProductExtractor.extract_vibes(product.name, product.description)
            
            if new_tags:
                # Update product in database
                success = await mongodb_client.update_product(
                    str(product.id),
                    {"tags": new_tags, "updated_at": datetime.datetime.utcnow()}
                )
                if success:
                    logger.info(f"✓ Updated tags for product {product.id}: {new_tags}")
                    success_count += 1
                else:
                    logger.warning(f"✗ Failed to update tags for product {product.id}")
                    failed_count += 1
            else:
                logger.warning(f"✗ No tags extracted for product {product.id}: {product.name[:50]}")
                no_tags_count += 1
        except Exception as e:
            logger.error(f"✗ Error refreshing tags for product {product.id}: {e}", exc_info=True)
            failed_count += 1
    
    logger.info(f"\nTag refresh complete:")
    logger.info(f"  ✓ Successful: {success_count}")
    logger.info(f"  ✗ Failed: {failed_count}")
    logger.info(f"  ⚠ No tags: {no_tags_count}")

#run refresh tags for all outfits as well to update vibe field


# update the color field and style score for all products by re-scraping the product pages and extracting the color and style score using the same logic as in the amazon scraper. This will ensure that we have accurate and up-to-date information for all products in our database.

from scrapers.amazon_scraper import AmazonScraper
from scrapers.nordstrom_scraper import NordstromScraper
from scrapers.hm_scraper import HMScraper



async def update_product_info_from_scraped_data():
    # scrape
    am_scraper = AmazonScraper()
    nord_scraper = NordstromScraper()
    hm_scraper = HMScraper()
    site_scrapers ={"amazon": am_scraper, "nordstrom": nord_scraper, "h&m": hm_scraper}
    # connect to database
    await mongodb_client.connect()
    # get all products from database
    products = await mongodb_client.get_all_products(limit=1000)
    updated_products=[]
    for product in products:
        # check if color is unknown and then scrape the product page to try to extract the color
        if product.color == "Unknown":
            scraper = site_scrapers.get(product.site.lower())
            if scraper:
                scraped_products = await scraper.scrape(categories=[product.category]) if product.site.lower() in ["amazon", "nordstrom"] else await scraper.scrape()
                
                # find the scraped product that matches the product url
                for scraped_product in scraped_products:
                    if scraped_product["product_url"] == product.product_url:
                        # update the color and style score in the database
                        await mongodb_client.update_product(
                            str(product.id),
                            {"color": scraped_product["color"], "style_score": scraped_product["style_score"], "updated_at": datetime.datetime.utcnow()}
                        )
                        logger.info(f"Updated product {product.id} with color {scraped_product['color']} and style score {scraped_product['style_score']}")
                        updated_products.append(product)
                        break
    # save these updates in the data folder in json format with the filename "updated_products.json"
    
    with open("data/updated_products.json", "w") as f:
        json.dump([product.dict() for product in updated_products], f)



if __name__ == "__main__":
    # asyncio.run(refresh_tags())
    asyncio.run(update_product_info_from_scraped_data())
    
                