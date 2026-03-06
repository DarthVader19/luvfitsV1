"""
Debug script to check database contents
"""
import logging
import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db import mongodb_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def debug_db():
    """Check database contents."""
    await mongodb_client.connect()
    
    try:
        # Get stats
        stats = await mongodb_client.get_stats()
        print("\n=== Database Statistics ===")
        print(f"Total Products: {stats.get('total_products', 0)}")
        print(f"Total Fallback Products: {stats.get('total_fallback_products', 0)}")
        print(f"Total Outfits: {stats.get('total_outfits', 0)}")
        print(f"Categories: {stats.get('categories', {})}")
        print(f"Sites: {stats.get('sites', {})}")
        
        # Count outfits
        outfits_count = await mongodb_client.count_outfits()
        print(f"\n=== Outfit Collection Count: {outfits_count} ===")
        
        # Get sample outfits
        if outfits_count > 0:
            sample_outfits = await mongodb_client.get_all_outfits(limit=3)
            print(f"\nSample Outfits ({min(3, len(sample_outfits))}):")
            for i, outfit in enumerate(sample_outfits):
                print(f"\n  Outfit {i+1}:")
                print(f"    ID: {outfit.id}")
                print(f"    Vibes: {outfit.vibes}")
                print(f"    Compatibility Score: {outfit.compatibility_score}")
        else:
            print("No outfits found in database!")
        
        # Check products count
        products_count = await mongodb_client.count_products()
        print(f"\n=== Product Collection Count: {products_count} ===")
        
        if products_count == 0:
            print("WARNING: No products in database! Run refresh first.")
        else:
            # Show product categories
            all_products = await mongodb_client.get_all_products(limit=200)
            categories = {}
            for product in all_products:
                cat = product.category
                categories[cat] = categories.get(cat, 0) + 1
            print(f"Product Categories: {categories}")
        
        # Check fallback products
        fallback_count = await mongodb_client.count_fallback_products()
        print(f"\n=== Fallback Products Collection Count: {fallback_count} ===")
        
        if fallback_count > 0:
            # Show fallback product categories
            all_fallback = await mongodb_client.get_all_fallback_products(limit=500)
            fallback_categories = {}
            for product in all_fallback:
                cat = product.category
                fallback_categories[cat] = fallback_categories.get(cat, 0) + 1
            print(f"Fallback Categories: {fallback_categories}")
            
            # Check for specific missing categories
            real_categories = set()
            for product in all_products:
                real_categories.add(product.category)
            
            missing = {'Tops', 'Bottoms', 'Shoes', 'Accessories'} - real_categories
            print(f"\nMissing Real Categories: {missing if missing else 'None'}")
            print(f"Available in Fallback: {set(fallback_categories.keys())}")
        
    finally:
        await mongodb_client.disconnect()


if __name__ == "__main__":
    asyncio.run(debug_db())
