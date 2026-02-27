#refresh product and outfit data tags in database and regenerate tags for all products

import datetime
import logging
import asyncio

import sys 

# Add parent directory to path for imports
import os   
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


if __name__ == "__main__":
    asyncio.run(refresh_tags())
                