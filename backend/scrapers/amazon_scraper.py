"""Amazon scraper using Scrape.do API."""
import logging
from typing import List, Dict, Any
from .base_scraper import BaseScraper, ProductExtractor

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    """Amazon specific scraper using Scrape.do."""

    def __init__(self):
        super().__init__()
        self.site_name = "Amazon"
        self.base_url = "https://www.amazon.com"

    def _get_category_queries(self, category: str) -> str:
        """Get Amazon search query for category."""
        queries = {
            "Tops": "women+clothing+tops",
            "Bottoms": "women+clothing+bottoms+jeans+pants",
            "Accessories": "women+fashion+accessories",
            "Shoes": "women+shoes",
        }
        return queries.get(category, "")

    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape Amazon products."""
        products = []
        categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

        async with self:
            for category in categories:
                query = self._get_category_queries(category)
                if not query:
                    continue

                url = f"{self.base_url}/s?k={query}"
                logger.info(f"Scraping Amazon {category} from {url}")
                html = await self.scrape_page(url, render_js=True)

                if html:
                    products.extend(self._extract_products(html, category))

        logger.info(f"Amazon: Scraped {len(products)} total products")
        return products

    def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
        """Extract products from Amazon HTML."""
        products = []
        soup = self.parse_html(html)

        # Amazon product result items
        items = soup.find_all("div", {"data-component-type": "s-search-result"})
        if not items:
            items = soup.find_all("div", class_="s-result-item")

        for item in items[:25]:  # Limit to 25 per category
            try:
                # Product name and link
                name_elem = item.find("h2", class_="s-size")
                if not name_elem:
                    name_elem = item.find("span", class_="a-size-base-plus")

                if not name_elem:
                    continue

                name_link = name_elem.find("a")
                if not name_link:
                    continue

                name = name_link.get_text(strip=True)
                product_url = name_link.get("href", "")
                if not product_url.startswith("http"):
                    product_url = self.base_url + product_url

                # Price
                price_elem = item.find("span", class_="a-price-whole")
                price_text = price_elem.text.strip() if price_elem else "0"
                price = self.extract_price(price_text)

                # Image
                img_elem = item.find("img", class_="s-image")
                image_url = img_elem.get("src", "") if img_elem else ""

                # Color from name
                color = "Unknown"
                color_keywords = ["black", "white", "blue", "red", "green", "pink", "gray", "brown", "navy", "beige"]
                for keyword in color_keywords:
                    if keyword in name.lower():
                        color = keyword.capitalize()
                        break

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
                        "style_score": 0.6,  # Default score
                        "available": True,
                    }
                    products.append(product)
                    logger.debug(f"Extracted Amazon product: {name}")

            except Exception as e:
                logger.warning(f"Error extracting Amazon product: {e}")
                continue

        return products