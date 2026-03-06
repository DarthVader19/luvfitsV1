"""
Outfit bundling logic: Creates coherent 4-piece outfits from products.
Uses color harmony, vibe matching, and price balance scoring.
"""
import logging
from typing import List, Dict, Any, Tuple, Optional

import sys 
import os
path_to_backend = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, path_to_backend)

from database.db import mongodb_client
from database.models import Product, Outfit

logger = logging.getLogger(__name__)


class OutfitBuilder:
    """Builds/generates coherent, balanced outfit combinations from products."""

    # Color harmony rules
    COLOR_HARMONY = {
        "neutral": ["neutral", "warm", "cool", "primary"],
        "warm": ["warm", "neutral", "primary"],
        "cool": ["cool", "neutral", "primary"],
        "primary": ["primary", "neutral"],
    }

    # Price range balance threshold (max ratio between pieces)
    PRICE_BALANCE_RATIO = 2.5

    def __init__(self):
        """Initialize outfit matcher."""
        self.vibes = [
            "casual",
            "elegant",
            "party",
            "date night",
            "90s",
            "minimalist",
            "sporty",
            "grunge",
        ]

    async def create_outfits(self, num_outfits: int = 100) -> List[Outfit]:
        """
        Generate outfit combinations from available products.
        Fills gaps with fallback products if needed.
        
        Args:
            num_outfits: Number of outfits to generate
            
        Returns:
            List of generated Outfit objects
        """
        logger.info(f"Generating {num_outfits} outfits...")
        
        # Ensure MongoDB is connected
        if mongodb_client.db is None:
            await mongodb_client.connect()

        # Get products by category (real products first)
        tops = await mongodb_client.get_products_by_category("Tops", limit=100)
        bottoms = await mongodb_client.get_products_by_category("Bottoms", limit=100)
        shoes = await mongodb_client.get_products_by_category("Shoes", limit=100)
        accessories = await mongodb_client.get_products_by_category("Accessories", limit=100)

        logger.info(f"Real products - Tops: {len(tops)}, Bottoms: {len(bottoms)}, Shoes: {len(shoes)}, Accessories: {len(accessories)}")

        # If missing any category entirely, try to fill with fallback products
        if not bottoms:
            logger.warning("No Bottoms found, attempting to use fallback products...")
            all_fallback = await mongodb_client.get_all_fallback_products(limit=500)
            bottoms = [p for p in all_fallback if p.category == "Bottoms"][:100]
            logger.info(f"Filled Bottoms with {len(bottoms)} fallback products")
        
        if not accessories:
            logger.warning("No Accessories found, attempting to use fallback products...")
            all_fallback = await mongodb_client.get_all_fallback_products(limit=500)
            accessories = [p for p in all_fallback if p.category == "Accessories"][:100]
            logger.info(f"Filled Accessories with {len(accessories)} fallback products")
        
        if not shoes or len(shoes) == 0:
            logger.warning("No Shoes found, attempting to use fallback products...")
            all_fallback = await mongodb_client.get_all_fallback_products(limit=500)
            shoes_fallback = [p for p in all_fallback if p.category == "Shoes"][:100]
            if shoes_fallback:
                shoes = shoes_fallback
            logger.info(f"Filled/supplemented Shoes with {len(shoes)} products (fallback)")
        
        if not tops or len(tops) == 0:
            logger.warning("No Tops found, attempting to use fallback products...")
            all_fallback = await mongodb_client.get_all_fallback_products(limit=500)
            tops_fallback = [p for p in all_fallback if p.category == "Tops"][:100]
            if tops_fallback:
                tops = tops_fallback
            logger.info(f"Filled/supplemented Tops with {len(tops)} products (fallback)")

        if not all([tops, bottoms, shoes, accessories]):
            logger.error(f"Still missing categories after fallback attempt. Tops: {len(tops)}, Bottoms: {len(bottoms)}, Shoes: {len(shoes)}, Accessories: {len(accessories)}")
            return []

        outfits = []
        generated = 0
        skipped = 0

        # Generate outfits with balanced selection
        for top in tops:
            for bottom in bottoms:
                for shoe in shoes:
                    for accessory in accessories:
                        if generated >= num_outfits:
                            break

                        # Score outfit
                        score = self._score_outfit(
                            top, bottom, shoe, accessory
                        )

                        if score["compatibility"] > 0.3:  # Lowered threshold to ensure outfit generation
                            # Extract shared vibes
                            vibes = self._extract_shared_vibes(
                                [top, bottom, shoe, accessory]
                            )

                            outfit = Outfit(
                                top_id=top.id,
                                bottom_id=bottom.id,
                                shoe_id=shoe.id,
                                accessory_id=accessory.id,
                                vibes=vibes,
                                compatibility_score=score["compatibility"],
                                color_harmony=score["color_harmony"],
                                total_price=(
                                    top.price
                                    + bottom.price
                                    + shoe.price
                                    + accessory.price
                                ),
                            )

                            outfits.append(outfit)
                            generated += 1
                        else:
                            skipped += 1

                    if generated >= num_outfits:
                        break
                if generated >= num_outfits:
                    break
            if generated >= num_outfits:
                break

        logger.info(f"Generated {len(outfits)} valid outfits (skipped {skipped} low-score combinations)")
        return outfits
        # Note: Connection is kept open for save_outfits

    def _score_outfit(
        self, top: Product, bottom: Product, shoe: Product, accessory: Product
    ) -> Dict[str, float]:
        """
        Score an outfit combination.
        
        Returns:
            Dict with scores: compatibility, color_harmony, price_balance
        """
        # Color compatibility (40%)
        color_harmony = self._score_color_harmony(
            top.color_family, bottom.color_family, shoe.color_family
        )

        # Vibe/tag overlap (30%)
        vibe_overlap = self._score_vibe_overlap(
            [top.tags, bottom.tags, shoe.tags, accessory.tags]
        )

        # Price balance (20%)
        price_balance = self._score_price_balance(
            [top.price, bottom.price, shoe.price, accessory.price]
        )

        # Individual product scores (10%)
        avg_style_score = (
            top.style_score
            + bottom.style_score
            + shoe.style_score
            + accessory.style_score
        ) / 4

        # Weighted final score
        compatibility = (
            (color_harmony * 0.4)
            + (vibe_overlap * 0.3)
            + (price_balance * 0.2)
            + (avg_style_score * 0.1)
        )

        return {
            "compatibility": min(compatibility, 1.0),  # Cap at 1.0
            "color_harmony": color_harmony,
            "price_balance": price_balance,
        }

    def _score_color_harmony(
        self, color1: str, color2: str, color3: str
    ) -> float:
        """Score how well colors harmonize (0-1)."""
        # Check if colors are compatible
        all_harmonious = True

        for c1 in [color1]:
            compatible_colors = self.COLOR_HARMONY.get(c1, [])
            if color2 not in compatible_colors or color3 not in compatible_colors:
                all_harmonious = False
                break

        return 1.0 if all_harmonious else 0.6

    def _score_vibe_overlap(self, tag_lists: List[List[str]]) -> float:
        """Score how many vibes overlap across pieces (0-1)."""
        if not tag_lists or any(not tags for tags in tag_lists):
            return 0.5  # Default middle score

        # Find common tags
        common_tags = set(tag_lists[0])
        for tags in tag_lists[1:]:
            common_tags &= set(tags)

        # Score based on overlap ratio
        avg_tags = sum(len(tags) for tags in tag_lists) / len(tag_lists)
        overlap_ratio = len(common_tags) / max(avg_tags, 1)

        return min(overlap_ratio, 1.0)

    def _score_price_balance(self, prices: List[float]) -> float:
        """Score price balance (favor balanced pricing) (0-1)."""
        if not prices or min(prices) == 0:
            return 0.5

        ratio = max(prices) / min(prices)

        # Penalize extreme ratios
        if ratio > self.PRICE_BALANCE_RATIO:
            return 0.4
        elif ratio > 2.0:
            return 0.7
        else:
            return 1.0

    def _extract_shared_vibes(self, products: List[Product]) -> List[str]:
        """Extract vibes that appear in multiple products."""
        if not products:
            return []

        # Get vibes from all products
        all_vibes = [vibe for product in products for vibe in product.tags]

        # Count occurrences
        vibe_counts = {}
        for vibe in all_vibes:
            vibe_counts[vibe] = vibe_counts.get(vibe, 0) + 1

        # Return vibes that appear in 2+ pieces
        shared_vibes = [
            vibe for vibe, count in vibe_counts.items() if count >= 1
        ]

        return shared_vibes if shared_vibes else ["neutral"]

    async def save_outfits(self, outfits: List[Outfit]) -> int:
        """Save outfits to MongoDB."""
        logger.info(f"Saving {len(outfits)} outfits to MongoDB...")
        
        # Ensure MongoDB is connected
        if mongodb_client.db is None:
            await mongodb_client.connect()
        
        saved = 0
        failed = 0
        
        for i, outfit in enumerate(outfits):
            try:
                # Verify outfit has valid IDs
                if not all([outfit.top_id, outfit.bottom_id, outfit.shoe_id, outfit.accessory_id]):
                    logger.warning(f"Outfit {i} missing product IDs, skipping")
                    failed += 1
                    continue
                    
                outfit_id = await mongodb_client.add_outfit(outfit)
                logger.debug(f"Saved outfit {i+1}/{len(outfits)} with ID: {outfit_id}")
                saved += 1
            except Exception as e:
                logger.error(f"Error saving outfit {i}: {e}", exc_info=True)
                failed += 1

        logger.info(f"Successfully saved {saved}/{len(outfits)} outfits ({failed} failures)")
        return saved


# Global instance
#create outfits and save to DB when this file runs
if __name__ == "__main__":
    outfit_builder = OutfitBuilder()
    import asyncio
    async def generate_and_save():
        outfits = await outfit_builder.create_outfits(num_outfits=50)
        logger.info(f"Generated {len(outfits)} outfits, now saving...")
        if outfits:
            await outfit_builder.save_outfits(outfits)
            logger.info("Outfits saved successfully.")
    asyncio.run(generate_and_save())

outfit_builder = OutfitBuilder()