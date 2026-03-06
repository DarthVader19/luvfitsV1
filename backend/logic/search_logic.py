"""
Advanced outfit search using BART model for tag extraction and intelligent matching.
"""
import asyncio
import logging
from typing import List, Dict, Tuple

import os   
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import Product
from scrapers.base_scraper import VibeExtractor, ModelCache
from database.db import mongodb_client
logger = logging.getLogger(__name__)


def build_outfit() -> Dict:
    """
    Build a fallback/empty outfit structure.
    Used when no valid outfit can be generated from available products.
    """
    return {
        'top': None,
        'bottom': None,
        'accessory': None,
        'shoe': None,
        'compatibility_score': 0.0,
        'matched_tags': []
    }


async def extract_query_tags(query: str) -> List[str]:
    """
    Use BART model to extract vibe tags from user query.
    E.g., "casual weekend look" -> ["casual", "sporty"]
    """
    try:
        logger.info(f"Extracting tags from query: '{query}'")
        
        # Pre-load model if not already loaded
        await ModelCache.get_instance()
        
        # Use VibeExtractor to understand user intent
        extractor = VibeExtractor()
        tags = await extractor.extract_vibes(
            name=query,
            description=""
        )
        
        if tags:
            logger.info(f"Extracted tags: {tags}")
            return tags
        else:
            # Fallback: extract keywords manually
            keywords = query.lower().split()
            logger.warning(f"No BART tags extracted, using keywords: {keywords}")
            return keywords
    except Exception as e:
        logger.error(f"Error extracting tags: {e}")
        return query.lower().split()


def get_products_by_tags(tags: List[str], limit: int = 50) -> Dict[str, List[Product]]:
    """
    Fetch products grouped by category that match the extracted tags.
    """
    session = mongodb_client.get_session()
    products_by_category = {
        'Tops': [],
        'Bottoms': [],
        'Accessories': [],
        'Shoes': []
    }
    
    try:
        for category in products_by_category.keys():
            for tag in tags:
                # Query products by category that contain any of the tags
                products = session.query(Product).filter(
                    Product.category == category,
                    Product.available == True
                ).all()
                
                # Filter by tag match
                matching = [
                    p for p in products 
                    if any(tag.lower() in t.lower() for t in p.tags)
                ]
                
                if matching:
                    products_by_category[category].extend(matching)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_products = []
            for p in products_by_category[category]:
                if p.id not in seen:
                    seen.add(p.id)
                    unique_products.append(p)
            
            products_by_category[category] = unique_products[:limit]
            
            # Fallback: get products from category if no tag match
            if not products_by_category[category]:
                fallback = session.query(Product).filter(
                    Product.category == category,
                    Product.available == True
                ).order_by(Product.style_score.desc()).limit(10).all()
                products_by_category[category] = fallback
    
    except Exception as e:
        logger.error(f"Error fetching products by tags: {e}")
    finally:
        session.close()
    
    return products_by_category


def calculate_tag_overlap(items: List[Product], target_tags: List[str]) -> float:
    """Calculate how many target tags the outfit items have"""
    if not items:
        return 0.0
    
    try:
        matching_count = 0
        for item in items:
            for tag in target_tags:
                if any(tag.lower() in t.lower() for t in item.tags):
                    matching_count += 1
                    break
        
        return min(matching_count / len(items) if items else 0.0, 1.0)
    except Exception as e:
        logger.warning(f"Error calculating tag overlap: {e}")
        return 0.5


def calculate_color_harmony(items: List[Product]) -> float:
    """Calculate color harmony between items"""
    if not items or len(items) < 2:
        return 0.5
    
    COLOR_HARMONY = {
        'neutral': ['neutral', 'warm', 'cool', 'primary'],
        'warm': ['warm', 'neutral', 'primary'],
        'cool': ['cool', 'neutral', 'primary'],
        'primary': ['primary', 'neutral']
    }
    
    try:
        color_families = [item.color_family for item in items if item.color_family]
        if not color_families:
            return 0.5
        
        total_score = 0
        comparisons = 0
        
        for i, color in enumerate(color_families):
            for other_color in color_families[i+1:]:
                if other_color in COLOR_HARMONY.get(color, []):
                    total_score += 1
                comparisons += 1
        
        return total_score / comparisons if comparisons > 0 else 0.5
    except Exception as e:
        logger.warning(f"Error calculating color harmony: {e}")
        return 0.5


def calculate_price_balance(items: List[Product]) -> float:
    """Prefer balanced prices (not too extreme differences)"""
    if not items or len(items) < 2:
        return 0.5
    
    try:
        prices = [item.price for item in items if item.price > 0]
        if not prices:
            return 0.5
        
        mean_price = sum(prices) / len(prices)
        if mean_price == 0:
            return 0.5
        
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        cv = std_dev / mean_price
        
        # Lower CV is better (more balanced)
        return max(0, 1 - (cv / 2))
    except Exception as e:
        logger.warning(f"Error calculating price balance: {e}")
        return 0.5


def score_outfit(items: List[Product], target_tags: List[str]) -> float:
    """
    Score outfit based on:
    - Tag match (40%)
    - Color harmony (30%)
    - Price balance (20%)
    - Style scores (10%)
    """
    if not items or len(items) < 4:
        return 0.0
    
    score = 0.0
    
    # Tag match (weight: 0.4)
    tag_score = calculate_tag_overlap(items, target_tags)
    score += tag_score * 0.4
    
    # Color harmony (weight: 0.3)
    color_score = calculate_color_harmony(items)
    score += color_score * 0.3
    
    # Price balance (weight: 0.2)
    price_score = calculate_price_balance(items)
    score += price_score * 0.2
    
    # Style scores (weight: 0.1)
    avg_style = sum(item.style_score for item in items) / len(items)
    score += avg_style * 0.1
    
    return score


def find_best_outfit_combination(
    products_by_category: Dict[str, List[Product]],
    target_tags: List[str],
    max_combinations: int = 100
) -> Tuple[Dict, float]:
    """
    Find the best outfit combination using tag-aware scoring.
    Returns tuple of (outfit_dict, score)
    """
    
    best_score = 0.0
    best_outfit = None
    combinations_tried = 0
    
    tops = products_by_category.get('Tops', [])[:10]
    bottoms = products_by_category.get('Bottoms', [])[:10]
    accessories = products_by_category.get('Accessories', [])[:10]
    shoes = products_by_category.get('Shoes', [])[:10]
    
    # If missing any category, fallback
    if not all([tops, bottoms, accessories, shoes]):
        logger.warning("Missing products in one or more categories")
        return None, 0.0
    
    for top in tops:
        for bottom in bottoms:
            for accessory in accessories:
                for shoe in shoes:
                    if combinations_tried >= max_combinations:
                        break
                    
                    items = [top, bottom, accessory, shoe]
                    score = score_outfit(items, target_tags)
                    
                    if score > best_score:
                        best_score = score
                        best_outfit = {
                            'top': top,
                            'bottom': bottom,
                            'accessory': accessory,
                            'shoe': shoe
                        }
                    
                    combinations_tried += 1
    
    logger.info(f"Tried {combinations_tried} combinations, best score: {best_score:.3f}")
    
    if best_outfit:
        return best_outfit, best_score
    
    # Final fallback
    return {
        'top': tops[0] if tops else None,
        'bottom': bottoms[0] if bottoms else None,
        'accessory': accessories[0] if accessories else None,
        'shoe': shoes[0] if shoes else None
    }, 0.0


async def search_outfits(query: str) -> Dict:
    """
    Main entry point: search for outfits using AI-extracted tags.
    """
    logger.info(f"Starting outfit search for query: '{query}'")
    
    try:
        # Step 1: Extract tags from user query using BART model
        tags = await extract_query_tags(query)
        
        if not tags:
            logger.warning("No tags extracted, using fallback outfit")
            return build_outfit()
        
        logger.info(f"Target tags for search: {tags}")
        
        # Step 2: Get products matching those tags
        products_by_category = get_products_by_tags(tags)
        
        # Step 3: Check if we have products in all categories
        if not all(products_by_category.values()):
            logger.warning("Missing products in some categories, using partial match")
        
        # Step 4: Find best outfit combination
        best_outfit_items, score = find_best_outfit_combination(
            products_by_category,
            tags
        )
        
        if not best_outfit_items or not any(best_outfit_items.values()):
            logger.warning("No valid outfit combination found")
            return build_outfit()
        
        # Step 5: Format outfit for response
        outfit = {}
        for key, product in best_outfit_items.items():
            if product:
                outfit[key] = product.model_dump()
            else:
                outfit[key] = None
        
        outfit['compatibility_score'] = score
        outfit['matched_tags'] = tags
        
        logger.info(f"Found outfit with score {score:.3f}, tags: {tags}")
        return outfit
    
    except Exception as e:
        logger.error(f"Error during outfit search: {e}", exc_info=True)
        return build_outfit()


def search_outfits_sync(query: str) -> Dict:
    """
    Synchronous wrapper for search_outfits (for non-async contexts).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, search_outfits(query))
                return future.result()
        else:
            return asyncio.run(search_outfits(query))
    except Exception as e:
        logger.error(f"Error in sync wrapper: {e}")
        return build_outfit()