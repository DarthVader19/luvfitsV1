"""
Advanced outfit matching logic using AI-extracted tags for better matching.
"""
import asyncio
import logging
from typing import List, Dict, Tuple, Optional

from database.models import Product
from database.db import mongodb_client
from scrapers.base_scraper import VibeExtractor, ModelCache

logger = logging.getLogger(__name__)


class OutfitMatcher:
    """Advanced outfit matching logic with AI-powered tag extraction"""
    
    # Color harmony rules
    COLOR_HARMONY = {
        'neutral': ['neutral', 'warm', 'cool', 'primary'],
        'warm': ['warm', 'neutral', 'primary'],
        'cool': ['cool', 'neutral', 'primary'],
        'primary': ['primary', 'neutral']
    }
    
    def __init__(self):
        pass
    
    async def extract_query_tags(self, query: str) -> List[str]:
        """
        Use BART model to extract vibe tags from user query.
        E.g., "I want a casual weekend look" -> ["casual"]
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
                logger.warning(f"No BART tags extracted from query: '{query}'")
                return []
        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            return []
    
    async def get_products_by_tags(self, tags: List[str], limit: int = 20) -> Dict[str, List[Product]]:
        """
        Get products grouped by category that match the extracted tags.
        Uses MongoDB text search and tag filtering.
        """
        products_by_category = {
            'Tops': [],
            'Bottoms': [],
            'Accessories': [],
            'Shoes': []
        }
        
        try:
            for category in products_by_category.keys():
                all_category_products = await mongodb_client.get_products_by_category(category, limit=100)
                
                # Score products by tag match
                scored_products = []
                for product in all_category_products:
                    match_score = sum(
                        1 for tag in tags
                        if any(tag.lower() in t.lower() for t in product.tags)
                    )
                    if match_score > 0 or not tags:  # Include all if no tags
                        scored_products.append((product, match_score))
                
                # Sort by match score, then by style score
                scored_products.sort(
                    key=lambda x: (-x[1], -x[0].style_score)
                )
                
                products_by_category[category] = [p[0] for p in scored_products[:limit]]
                
                logger.debug(f"Category {category}: found {len(products_by_category[category])} products")
        
        except Exception as e:
            logger.error(f"Error fetching products by tags: {e}")
        
        return products_by_category
    
    def calculate_style_compatibility(self, items: List[Product]) -> float:
        """Calculate how well items work together based on color harmony"""
        if not items or len(items) < 4:
            return 0.0
        
        color_families = [item.color_family for item in items if item.color_family]
        if not color_families:
            return 0.5
        
        total_score = 0
        comparisons = 0
        
        for i, color in enumerate(color_families):
            for other_color in color_families[i+1:]:
                if other_color in self.COLOR_HARMONY.get(color, []):
                    total_score += 1
                comparisons += 1
        
        return min(total_score / comparisons if comparisons > 0 else 0.0, 1.0)
    
    def calculate_tag_overlap(self, items: List[Product], target_tags: List[str]) -> float:
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
    
    def calculate_price_balance(self, items: List[Product]) -> float:
        """Prefer balanced prices (not too extreme differences)"""
        if not items or len(items) < 2:
            return 0.5
        
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
    
    def _score_outfit(self, items: List[Product], target_tags: List[str]) -> float:
        """
        Score an outfit based on multiple factors:
        - Tag match (40%)
        - Color harmony (30%)
        - Price balance (20%)
        - Individual style scores (10%)
        """
        if not items or len(items) < 4:
            return 0.0
        
        score = 0.0
        
        # Tag match (weight: 0.4)
        tag_score = self.calculate_tag_overlap(items, target_tags)
        score += tag_score * 0.4
        
        # Color harmony (weight: 0.3)
        color_score = self.calculate_style_compatibility(items)
        score += color_score * 0.3
        
        # Price balance (weight: 0.2)
        price_score = self.calculate_price_balance(items)
        score += price_score * 0.2
        
        # Individual style scores (weight: 0.1)
        avg_style = sum(item.style_score for item in items) / len(items) if items else 0.5
        score += avg_style * 0.1
        
        return score
    
    def find_best_combination(
        self,
        products_by_category: Dict[str, List[Product]],
        target_tags: List[str],
        max_combinations: int = 100
    ) -> Optional[Dict]:
        """Find the best combination of items from each category"""
        
        # Check if we have at least one item per category
        if not all(products_by_category.values()):
            logger.warning("Missing products in one or more categories")
            return None
        
        best_score = 0.0
        best_combo = None
        combinations_tried = 0
        
        tops = products_by_category.get('Tops', [])[:10]
        bottoms = products_by_category.get('Bottoms', [])[:10]
        accessories = products_by_category.get('Accessories', [])[:10]
        shoes = products_by_category.get('Shoes', [])[:10]
        
        for top in tops:
            for bottom in bottoms:
                for accessory in accessories:
                    for shoe in shoes:
                        if combinations_tried >= max_combinations:
                            break
                        
                        items = [top, bottom, accessory, shoe]
                        score = self._score_outfit(items, target_tags)
                        
                        if score > best_score:
                            best_score = score
                            best_combo = {
                                'top': top,
                                'bottom': bottom,
                                'accessory': accessory,
                                'shoe': shoe,
                                'compatibility_score': score
                            }
                        
                        combinations_tried += 1
        
        logger.info(f"Tried {combinations_tried} combinations, best score: {best_score:.3f}")
        
        return best_combo
    
    async def _build_fallback_outfit(self) -> Dict:
        """Build a random outfit if no good combination found"""
        try:
            outfit = {}
            for category in ['Tops', 'Bottoms', 'Accessories', 'Shoes']:
                products = await mongodb_client.get_products_by_category(category, limit=1)
                product = products[0] if products else None
                outfit[category.lower()] = product.model_dump() if product else None
            outfit['compatibility_score'] = 0.3
            return outfit
        except Exception as e:
            logger.error(f"Error building fallback outfit: {e}")
            return {'top': None, 'bottom': None, 'accessory': None, 'shoe': None, 'compatibility_score': 0.0}
    
    async def search_outfits(self, query: str) -> Dict:
        """
        Main entry point for outfit search.
        1. Extract tags from user query using BART model
        2. Find products matching those tags
        3. Build best outfit combination
        """
        logger.info(f"Starting outfit search for query: '{query}'")
        
        try:
            # Step 1: Extract tags from query
            target_tags = await self.extract_query_tags(query)
            
            if not target_tags:
                logger.info("No tags extracted, returning fallback outfit")
                return await self._build_fallback_outfit()
            
            # Step 2: Get products matching those tags
            products_by_category = await self.get_products_by_tags(target_tags)
            
            # Step 3: Find best combination
            best_outfit = self.find_best_combination(products_by_category, target_tags)
            
            if best_outfit:
                # Convert products to dicts
                outfit_response = {}
                for key, product in best_outfit.items():
                    if key == 'compatibility_score':
                        outfit_response[key] = product
                    elif product:
                        outfit_response[key] = product.model_dump()
                    else:
                        outfit_response[key] = None
                
                outfit_response['matched_tags'] = target_tags
                logger.info(f"Found outfit with score {best_outfit['compatibility_score']:.3f}")
                return outfit_response
            else:
                logger.warning("No valid outfit combination found")
                return await self._build_fallback_outfit()
        
        except Exception as e:
            logger.error(f"Error during outfit search: {e}", exc_info=True)
            return await self._build_fallback_outfit()


# Global instance for reuse
_matcher_instance: Optional[OutfitMatcher] = None


def get_matcher() -> OutfitMatcher:
    """Get or create OutfitMatcher instance"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = OutfitMatcher()
    return _matcher_instance


async def search_outfits_async(query: str) -> Dict:
    """Async search outfits using AI tag extraction"""
    matcher = get_matcher()
    return await matcher.search_outfits(query)
