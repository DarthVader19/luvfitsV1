import logging
from database.models import SessionLocal, Product
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class OutfitMatcher:
    """Advanced outfit matching logic with aesthetic considerations"""
    
    # Color harmony rules
    COLOR_HARMONY = {
        'neutral': ['neutral', 'warm', 'cool', 'primary'],
        'warm': ['warm', 'neutral', 'primary'],
        'cool': ['cool', 'neutral', 'primary'],
        'primary': ['primary', 'neutral']
    }
    
    def __init__(self):
        self.session = SessionLocal()
    
    def calculate_style_compatibility(self, items: List[Product]) -> float:
        """Calculate how well items work together"""
        if not items or len(items) < 4:
            return 0.0
        
        # Check color harmony
        color_families = [item.color_family for item in items]
        total_score = 0
        
        # Score color combinations
        for i, color in enumerate(color_families):
            for j, other_color in enumerate(color_families[i+1:], i+1):
                if other_color in self.COLOR_HARMONY.get(color, []):
                    total_score += 1
        
        # Normalize
        max_combinations = len(items) * (len(items) - 1) / 2
        return min(total_score / max_combinations, 1.0) if max_combinations > 0 else 0.5
    
    def get_products_by_tags(self, query: str) -> Dict[str, List[Product]]:
        """Get products grouped by category for a specific vibe"""
        products_by_category = {
            'Tops': [],
            'Bottoms': [],
            'Accessories': [],
            'Shoes': []
        }
        
        try:
            for category in products_by_category.keys():
                # Search by tags
                products = self.session.query(Product).filter(
                    Product.category == category,
                    Product.tags.contains(query)
                ).all()
                
                if products:
                    products_by_category[category] = products
                else:
                    # Fallback to any category
                    products = self.session.query(Product).filter(
                        Product.category == category
                    ).order_by(Product.style_score.desc()).limit(10).all()
                    products_by_category[category] = products
        
        except Exception as e:
            logger.error(f"Error fetching products: {str(e)}")
        
        return products_by_category
    
    def find_best_combination(self, products_by_category: Dict[str, List[Product]]) -> Dict:
        """Find the best combination of items from each category"""
        
        # Check if we have at least one item per category
        if not all(products_by_category.values()):
            return self._build_fallback_outfit()
        
        best_score = 0
        best_combo = None
        
        # Try combinations
        tops = products_by_category.get('Tops', [])
        bottoms = products_by_category.get('Bottoms', [])
        accessories = products_by_category.get('Accessories', [])
        shoes = products_by_category.get('Shoes', [])
        
        for top in tops[:5]:
            for bottom in bottoms[:5]:
                for accessory in accessories[:5]:
                    for shoe in shoes[:5]:
                        items = [top, bottom, accessory, shoe]
                        score = self._score_outfit(items)
                        
                        if score > best_score:
                            best_score = score
                            best_combo = (top, bottom, accessory, shoe)
        
        if best_combo:
            return {
                'top': best_combo[0].to_dict(),
                'bottom': best_combo[1].to_dict(),
                'accessory': best_combo[2].to_dict(),
                'shoe': best_combo[3].to_dict(),
                'compatibility_score': best_score
            }
        
        return self._build_fallback_outfit()
    
    def _score_outfit(self, items: List[Product]) -> float:
        """Score an outfit based on multiple factors"""
        score = 0.0
        
        # Color compatibility (weight: 0.4)
        color_score = self.calculate_style_compatibility(items)
        score += color_score * 0.4
        
        # Style tag overlap (weight: 0.3)
        tag_score = self._calculate_tag_overlap(items)
        score += tag_score * 0.3
        
        # Price balance (weight: 0.2)
        price_score = self._calculate_price_balance(items)
        score += price_score * 0.2
        
        # Individual style scores (weight: 0.1)
        avg_style = sum(item.style_score for item in items) / len(items) if items else 0.5
        score += avg_style * 0.1
        
        return score
    
    def _calculate_tag_overlap(self, items: List[Product]) -> float:
        """Calculate how many tags items share"""
        if not items:
            return 0.0
        
        try:
            all_tags = []
            for item in items:
                tags = [t.strip() for t in item.tags.split(',') if t.strip()]
                all_tags.extend(tags)
            
            # Count tag frequency
            tag_counts = {}
            for tag in all_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            
            # Score based on shared tags
            shared_tags = sum(1 for count in tag_counts.values() if count > 1)
            return min(shared_tags / len(items), 1.0)
        except Exception as e:
            logger.warning(f"Error calculating tag overlap: {str(e)}")
            return 0.5
    
    def _calculate_price_balance(self, items: List[Product]) -> float:
        """Prefer balanced prices (not too extreme differences)"""
        if not items or len(items) < 2:
            return 0.5
        
        prices = [item.price for item in items if item.price > 0]
        if not prices:
            return 0.5
        
        # Calculate coefficient of variation
        mean_price = sum(prices) / len(prices)
        if mean_price == 0:
            return 0.5
        
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        std_dev = variance ** 0.5
        cv = std_dev / mean_price
        
        # Lower CV is better (more balanced)
        return max(0, 1 - (cv / 2))
    
    def _build_fallback_outfit(self) -> Dict:
        """Build a random outfit if no good combination found"""
        try:
            outfit = {}
            for category in ['Tops', 'Bottoms', 'Accessories', 'Shoes']:
                product = self.session.query(Product).filter(
                    Product.category == category
                ).first()
                outfit[category.lower()] = product.to_dict() if product else None
            outfit['compatibility_score'] = 0.3
            return outfit
        except Exception as e:
            logger.error(f"Error building fallback outfit: {str(e)}")
            return {'top': None, 'bottom': None, 'accessory': None, 'shoe': None}
    
    def search_outfits(self, query: str) -> Dict:
        """Main entry point for outfit search"""
        products_by_category = self.get_products_by_tags(query)
        return self.find_best_combination(products_by_category)
    
    def close(self):
        """Close database session"""
        self.session.close()
