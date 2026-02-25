"""
H&M scraper using Scrape.do API.
"""
import logging
from typing import List, Dict, Any
from .base_scraper import BaseScraper, ProductExtractor

logger = logging.getLogger(__name__)


class HMScraper(BaseScraper):
    """H&M specific scraper using Scrape.do."""

    def __init__(self):
        super().__init__()
        self.site_name = "H&M"
        self.base_url = "https://www.hm.com"

    def _get_category_url(self, category: str) -> str:
        """Get H&M category URL."""
        urls = {
            "Tops": "https://www.hm.com/en_us/women/products/tops.html",
            "Bottoms": "https://www.hm.com/en_us/women/products/bottoms.html",
            "Accessories": "https://www.hm.com/en_us/women/products/accessories.html",
            "Shoes": "https://www.hm.com/en_us/women/products/shoes.html",
        }
        return urls.get(category, "")

    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape H&M products."""
        products = []
        categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

        async with self:
            for category in categories:
                url = self._get_category_url(category)
                if not url:
                    continue

                logger.info(f"Scraping H&M {category} from {url}")
                html = await self.scrape_page(url, render_js=True)

                if html:
                    products.extend(self._extract_products(html, category))

        logger.info(f"H&M: Scraped {len(products)} total products")
        return products

    def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
        """Extract products from H&M HTML."""
        products = []
        soup = self.parse_html(html)

        # H&M product grid items
        items = soup.find_all("div", class_="productitem")

        for item in items[:25]:  # Limit to 25 per category
            try:
                # Product name and link
                name_elem = item.find("a", class_="link")
                if not name_elem:
                    continue

                name = name_elem.get_text(strip=True)
                product_url = name_elem.get("href", "")
                if not product_url.startswith("http"):
                    product_url = self.base_url + product_url

                # Price
                price_elem = item.find("span", class_="price-now")
                price_text = price_elem.text.strip() if price_elem else "0"
                price = self.extract_price(price_text)

                # Image
                img_elem = item.find("img")
                image_url = img_elem.get("src", "") if img_elem else ""

                # Color from alt text or description
                alt_text = img_elem.get("alt", "") if img_elem else ""
                color = alt_text.split("|")[1].strip() if "|" in alt_text else "Unknown"

                # Description
                description = name

                if name and product_url:
                    color_family = self.extract_color_family(color)
                    vibes = ProductExtractor.extract_vibes(name, description, price)

                    product = {
                        "name": name,
                        "price": price,
                        "currency": "USD",
                        "color": color,
                        "color_family": color_family,
                        "description": description,
                        "image_url": image_url,
                        "product_url": product_url,
                        "category": category,
                        "subcategory": None,
                        "site": self.site_name,
                        "tags": vibes,
                        "style_score": 0.7,  # Default score
                        "available": True,
                    }
                    products.append(product)
                    logger.debug(f"Extracted H&M product: {name}")

            except Exception as e:
                logger.warning(f"Error extracting H&M product: {e}")
                continue

        return products