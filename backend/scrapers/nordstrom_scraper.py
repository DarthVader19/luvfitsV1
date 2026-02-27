"""Nordstrom scraper using Scrape.do API."""
import logging
from typing import List, Dict, Any
from .base_scraper import BaseScraper, ProductExtractor

logger = logging.getLogger(__name__)


class NordstromScraper(BaseScraper):
    """Nordstrom specific scraper using Scrape.do."""

    def __init__(self):
        super().__init__()
        self.site_name = "Nordstrom"
        self.base_url = "https://www.nordstrom.com"

    def _get_category_url(self, category: str) -> str:
        """Get Nordstrom category URL."""
        urls = {
            "Tops": "https://www.nordstrom.com/browse/women/clothing/tops",
            "Bottoms": "https://www.nordstrom.com/browse/women/clothing/bottoms-shorts",
            "Accessories": "https://www.nordstrom.com/browse/women/accessories",
            "Shoes": "https://www.nordstrom.com/browse/women/shoes",
        }
        return urls.get(category, "")

    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape Nordstrom products."""
        products = []
        categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

        async with self:
            for category in categories:
                url = self._get_category_url(category)
                if not url:
                    continue

                logger.info(f"Scraping Nordstrom {category} from {url}")
                html = await self.scrape_page(url, render_js=True)

                if html:
                    products.extend(self._extract_products(html, category))

        logger.info(f"Nordstrom: Scraped {len(products)} total products")
        return products

    async def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
        """Extract products from Nordstrom HTML."""
        products = []
        soup = self.parse_html(html)

        # Nordstrom product grid items
        items = soup.find_all("div", class_="product-grid__item")
        if not items:
            items = soup.find_all("article", class_="product-item")
        if not items:
            items = soup.find_all("div", {"data-testid": "productCard"})

        for item in items[:25]:  # Limit to 25 per category
            try:
                # Product name and link
                name_elem = item.find("a", class_="product-link")
                if not name_elem:
                    name_elem = item.find("a", class_="product__link")

                if not name_elem:
                    continue

                name = name_elem.get_text(strip=True)
                product_url = name_elem.get("href", "")
                if not product_url.startswith("http"):
                    product_url = self.base_url + product_url

                # Price
                price_elem = item.find("span", class_="prices")
                if not price_elem:
                    price_elem = item.find("span", {"data-testid": "value"})

                price_text = price_elem.text.strip() if price_elem else "0"
                price = self.extract_price(price_text)

                # Image
                img_elem = item.find("img", class_="product-image")
                if not img_elem:
                    img_elem = item.find("img")

                image_url = img_elem.get("src", "") if img_elem else ""

                # Color
                color = "Unknown"
                color_elem = item.find("span", class_="product-color")
                if color_elem:
                    color = color_elem.get_text(strip=True)
                else:
                    color_keywords = ["black", "white", "blue", "red", "green", "pink", "gray", "brown", "navy", "beige"]
                    for keyword in color_keywords:
                        if keyword in name.lower():
                            color = keyword.capitalize()
                            break

                # Description
                description = name

                if name and product_url:
                    color_family = self.extract_color_family(color)
                    vibes = await ProductExtractor.extract_vibes(name, description, price)

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
                        "style_score": 0.65,  # Default score
                        "available": True,
                    }
                    products.append(product)
                    logger.debug(f"Extracted Nordstrom product: {name}")

            except Exception as e:
                logger.warning(f"Error extracting Nordstrom product: {e}")
                continue

        return products
