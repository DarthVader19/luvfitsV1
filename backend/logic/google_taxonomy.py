"""
Google Taxonomy Mapper for product categorization.
Helps classify fashion products according to Google's taxonomy.
"""
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class GoogleTaxonomyMapper:
    """Map products to Google commerce taxonomy."""

    # Simplified Google taxonomy for fashion
    TAXONOMY = {
        "Apparel & Accessories > Clothing > Shirts & Tops": [
            "shirt",
            "blouse",
            "top",
            "t-shirt",
            "tee",
            "sweater",
            "hoodie",
            "sweatshirt",
        ],
        "Apparel & Accessories > Clothing > Pants": [
            "pants",
            "trousers",
            "jeans",
            "denim",
            "leggings",
        ],
        "Apparel & Accessories > Clothing > Shorts": [
            "shorts",
            "short pants",
        ],
        "Apparel & Accessories > Clothing > Skirts": [
            "skirt",
            "skirts",
        ],
        "Apparel & Accessories > Clothing > Dresses": [
            "dress",
            "dresses",
        ],
        "Apparel & Accessories > Clothing > Jackets & Coats": [
            "jacket",
            "coat",
            "blazer",
            "cardigan",
            "sweater jacket",
        ],
        "Apparel & Accessories > Footwear > Shoes": [
            "shoe",
            "shoes",
            "sneaker",
            "boot",
            "sandal",
            "heel",
            "flat",
            "loafer",
            "pump",
        ],
        "Apparel & Accessories > Footwear > Socks": [
            "sock",
            "socks",
        ],
        "Apparel & Accessories > Accessories > Bags": [
            "bag",
            "bags",
            "purse",
            "handbag",
            "backpack",
            "tote",
        ],
        "Apparel & Accessories > Accessories > Hats": [
            "hat",
            "caps",
            "beanie",
            "baseball cap",
        ],
        "Apparel & Accessories > Accessories > Scarves": [
            "scarf",
            "scarves",
            "shawl",
        ],
        "Apparel & Accessories > Accessories > Belts": [
            "belt",
            "belts",
        ],
        "Apparel & Accessories > Accessories > Jewelry": [
            "necklace",
            "bracelet",
            "earring",
            "ring",
            "watch",
            "jewelry",
        ],
    }

    # Extended attributes for products
    STYLE_ATTRIBUTES = {
        "casual": [
            "casual",
            "everyday",
            "relaxed",
            "comfortable",
            "jeans",
            "t-shirt",
        ],
        "formal": ["formal", "dress", "elegant", "business", "blazer"],
        "sporty": [
            "sporty",
            "athletic",
            "gym",
            "sport",
            "yoga",
            "activewear",
        ],
        "vintage": ["vintage", "retro", "80s", "90s", "classic"],
        "minimalist": ["minimalist", "simple", "plain", "neutral"],
        "bohemian": ["bohemian", "boho", "hippie", "flowing"],
        "preppy": ["preppy", "smart", "collegiate"],
        "grunge": ["grunge", "edgy", "dark", "alternative"],
    }

    @classmethod
    def categorize(cls, name: str, description: str = "") -> Tuple[str, str]:
        """
        Categorize a product into Google taxonomy.
        
        Args:
            name: Product name
            description: Product description
            
        Returns:
            Tuple of (category, subcategory)
        """
        full_text = (name + " " + description).lower()

        # Find matching taxonomy
        for taxonomy_path, keywords in cls.TAXONOMY.items():
            for keyword in keywords:
                if keyword in full_text:
                    # Split into main and sub category
                    parts = taxonomy_path.split(" > ")
                    main_category = parts[-1] if parts else "Clothing"
                    sub_category = (
                        parts[-2] if len(parts) > 1 else "General"
                    )
                    return main_category, sub_category

        # Default categorization based on simple keywords
        if any(word in full_text for word in ["shirt", "top", "blouse", "tee"]):
            return "Tops", "Shirts & Tops"
        elif any(
            word in full_text for word in ["pants", "jeans", "leggings"]
        ):
            return "Bottoms", "Pants"
        elif any(word in full_text for word in ["shoe", "sneaker", "boot"]):
            return "Shoes", "Footwear"
        elif any(
            word in full_text
            for word in ["bag", "watch", "necklace", "hat", "belt"]
        ):
            return "Accessories", "Fashion Accessories"
        else:
            return "General", "Clothing"

    @classmethod
    def extract_style_tags(cls, text: str) -> List[str]:
        """
        Extract style attributes from product text.
        
        Args:
            text: Product name/description
            
        Returns:
            List of applicable style tags
        """
        text_lower = text.lower()
        tags = []

        for style, keywords in cls.STYLE_ATTRIBUTES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    tags.append(style)
                    break  # Add style once

        return tags

    @classmethod
    def get_subcategory(cls, category: str) -> str:
        """Get subcategory from main category."""
        category_map = {
            "Tops": "Shirts & Tops",
            "Bottoms": "Pants",
            "Shoes": "Footwear",
            "Accessories": "Fashion Accessories",
        }
        return category_map.get(category, "General")

    @classmethod
    def validate_category(cls, category: str) -> bool:
        """Validate if category is standard."""
        valid_categories = ["Tops", "Bottoms", "Shoes", "Accessories"]
        return category in valid_categories


class TaxonomyEnhancer:
    """Enhance product data with taxonomy information."""

    @staticmethod
    async def enhance_product(product_data: Dict) -> Dict:
        """
        Enhance product with taxonomy and style information.
        
        Args:
            product_data: Raw product data
            
        Returns:
            Enhanced product data
        """
        # Get category
        name = product_data.get("name", "")
        description = product_data.get("description", "")

        category, subcategory = GoogleTaxonomyMapper.categorize(
            name, description
        )

        # Extract style tags
        style_tags = GoogleTaxonomyMapper.extract_style_tags(
            name + " " + description
        )

        # Update product data
        product_data["category"] = category
        product_data["subcategory"] = subcategory
        product_data["tags"] = list(
            set(product_data.get("tags", []) + style_tags)
        )

        logger.debug(f"Enhanced {name}: {category}/{subcategory}")

        return product_data
