"""
H&M scraper using Scrape.do API.
"""
import logging
import re
from pathlib import Path
import sys
from typing import Any, Dict, List
from urllib.parse import urljoin

try:
    from .base_scraper import BaseScraper, ProductExtractor
except ImportError:
    # Allow direct execution: python .\scrapers\hm_scraper.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from base_scraper import BaseScraper, ProductExtractor

logger = logging.getLogger(__name__)


class HMScraper(BaseScraper):
    """H&M specific scraper using Scrape.do."""

    # Trimmed from the navigation-carousel JSON shared by the user.
    NAVIGATION_LINKS = [
        {"department": "ladies", "title": "Maternity Wear", "aliasPath": "/en_us/women/products/maternity-clothes.html"},
        {"department": "ladies", "title": "Skirts", "aliasPath": "/en_us/women/products/skirts.html"},
        {"department": "ladies", "title": "Festival Edit", "aliasPath": "/en_us/women/seasonal-trending/festival.html"},
        {"department": "ladies", "title": "Swimwear", "aliasPath": "/en_us/women/products/swimwear.html"},
        {"department": "men", "title": "Hoodies & Sweatshirts", "aliasPath": "/en_us/men/products/hoodies-sweatshirts.html"},
        {"department": "men", "title": "Underwear", "aliasPath": "/en_us/men/products/underwear.html"},
    ]

    CATEGORY_KEYWORDS = {
        "Tops": ["top", "hoodie", "sweatshirt", "shirt", "blouse", "sweater"],
        "Bottoms": ["jeans", "skirt", "pants", "trousers", "shorts", "leggings"],
        "Accessories": ["accessories", "bag", "hat", "belt", "jewelry", "underwear"],
        "Shoes": ["shoes", "sneaker", "boot", "heel", "sandal", "loafer"],
    }

    def __init__(self):
        super().__init__()
        self.site_name = "H&M"
        self.base_url = "https://www2.hm.com"

    def _get_category_urls(self, category: str) -> List[str]:
        """Get H&M category URLs from defaults + nav JSON aliases."""
        defaults = {
            "Tops": [
                "https://www2.hm.com/en_us/women/products/tops.html",
                "https://www2.hm.com/en_us/women/products/hoodies-sweatshirts.html",
            ],
            "Bottoms": [
                "https://www2.hm.com/en_us/women/products/bottoms.html",
                "https://www2.hm.com/en_us/women/products/skirts.html",
            ],
            "Accessories": [
                "https://www2.hm.com/en_us/women/products/accessories.html",
            ],
            "Shoes": [
                "https://www2.hm.com/en_us/women/products/shoes.html",
            ],
        }

        urls = list(defaults.get(category, []))
        for link in self.NAVIGATION_LINKS:
            title = link.get("title", "").lower()
            alias_path = link.get("aliasPath", "")
            if not alias_path:
                continue
            if any(keyword in title for keyword in self.CATEGORY_KEYWORDS[category]):
                urls.append(urljoin(self.base_url, alias_path))

        return list(dict.fromkeys(urls))

    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape H&M products."""
        products: List[Dict[str, Any]] = []
        categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

        async with self:
            for category in categories:
                urls = self._get_category_urls(category)
                for url in urls:
                    logger.info(f"Scraping H&M {category} from {url}")
                    html = await self.scrape_page(url, render_js=True)
                    if html:
                        products.extend(self._extract_products(html, category))

                    category_count = len(
                        [p for p in products if p.get("category") == category]
                    )
                    if category_count >= 25:
                        break

        logger.info(f"H&M: Scraped {len(products)} total products")
        return products

    def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
        """Extract products from H&M HTML."""
        products: List[Dict[str, Any]] = []
        soup = self.parse_html(html)

        selectors = [
            "article[data-articlecode]",
            "div[data-articlecode]",
            "li.product-item",
            "div.product-item",
            "div.productitem",
        ]

        items = []
        for selector in selectors:
            found = soup.select(selector)
            if found:
                items = found
                break

        if not items:
            return self._extract_from_links(soup, category)

        for item in items[:25]:
            product = self._parse_item(item, category)
            if product:
                products.append(product)

        return products

    def _extract_from_links(self, soup, category: str) -> List[Dict[str, Any]]:
        """Fallback extraction from product links when card selectors fail."""
        products: List[Dict[str, Any]] = []
        links = soup.select("a[href*='/productpage.']")
        seen = set()

        for link in links[:40]:
            href = link.get("href", "")
            if not href:
                continue
            product_url = href if href.startswith("http") else urljoin(self.base_url, href)
            if product_url in seen:
                continue
            seen.add(product_url)

            name = link.get("title") or link.get_text(strip=True) or "H&M Product"
            description = name
            price = 0.0
            color = "Unknown"

            products.append(
                {
                    "name": name,
                    "price": price,
                    "currency": "USD",
                    "color": color,
                    "color_family": self.extract_color_family(color),
                    "description": description,
                    "image_url": "",
                    "product_url": product_url,
                    "category": category,
                    "subcategory": None,
                    "site": self.site_name,
                    "tags": ProductExtractor.extract_vibes(name, description, price),
                    "style_score": 0.7,
                    "available": True,
                }
            )

        return products[:25]

    def _parse_item(self, item, category: str) -> Dict[str, Any] | None:
        """Parse one product card."""
        try:
            name_elem = item.select_one("a[href*='/productpage.'], a.link, a.item-link")
            if not name_elem:
                return None

            name = name_elem.get("title") or name_elem.get_text(strip=True) or "H&M Product"
            href = name_elem.get("href", "")
            if not href:
                return None
            product_url = href if href.startswith("http") else urljoin(self.base_url, href)

            price_elem = item.select_one(
                "span.price-now, span.a-price, span[data-price], [class*='price']"
            )
            price_text = price_elem.get_text(" ", strip=True) if price_elem else "0"
            price = self.extract_price(price_text)

            img_elem = item.find("img")
            image_url = ""
            alt_text = ""
            if img_elem:
                image_url = (
                    img_elem.get("src")
                    or img_elem.get("data-src")
                    or img_elem.get("data-altimage")
                    or ""
                )
                alt_text = img_elem.get("alt", "")

            description = " ".join([name, item.get_text(" ", strip=True)[:200]]).strip()
            color = "Unknown"
            color_match = re.search(
                r"\b(black|white|blue|red|green|pink|gray|grey|brown|beige|navy|cream)\b",
                f"{alt_text} {description}".lower(),
            )
            if color_match:
                color = color_match.group(1).capitalize()

            return {
                "name": name,
                "price": price,
                "currency": "USD",
                "color": color,
                "color_family": self.extract_color_family(color),
                "description": description,
                "image_url": image_url,
                "product_url": product_url,
                "category": category,
                "subcategory": None,
                "site": self.site_name,
                "tags": ProductExtractor.extract_vibes(name, description, price),
                "style_score": 0.7,
                "available": True,
            }
        except Exception as e:
            logger.warning(f"Error extracting H&M product: {e}")
            return None


if __name__ == "__main__":
    import asyncio
    import json
    async def test_scraper():
        scraper = HMScraper()
        products = await scraper.scrape()
        # save to json(products, "hm_products.json")

        with open("hm_products.json", "w") as f:
            json.dump(products, f, indent=2)
        

        print(f"Scraped {len(products)} products from H&M")
        for p in products[:5]:
            print(p)

    asyncio.run(test_scraper())
