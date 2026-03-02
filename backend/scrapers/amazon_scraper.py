"""Amazon scraper using Scrape.do API."""
import logging
from typing import List, Dict, Any

import sys
import os 
 # Adjust the path as needed to import while running the scraper independently

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from scrapers.base_scraper import BaseScraper, ProductExtractor

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
            for category in categories[:]: # Limit to first category for testing
                query = self._get_category_queries(category)
                if not query:
                    continue
                # go to url only if html is not already saved for debugging
                path_exists = os.path.exists(f"./htmls/amazon_{category.lower()}.html")
                # if not path_exists:
                #     print(os.getcwd())  # Ensure directory exists
                #     break
                print(f"Checking if HTML file exists for {category}: {path_exists}")  # Debug log
                if not path_exists:
                    url = f"{self.base_url}/s?k={query}"
                    logger.info(f"Path not existing for {category}. Scraping Amazon {category} from {url}")
                # log the URL being scraped for debugging
                    print(f"Scraping URL: {url}")

                    html = await self.scrape_page(url, render_js=True)
                    print(f"Scraped HTML length for {category}: {len(html) if html else 'No HTML'}")  # Debug log
                # save the HTML to a file for debugging
                    with open(f"./htmls/amazon_{category.lower()}.html", "w", encoding="utf-8") as f:
                       f.write(html if html else "")
                
                if path_exists:
                    with open(f"./htmls/amazon_{category.lower()}.html", "r", encoding="utf-8") as f:
                        html = f.read()
                if html:
                    products.extend(await self._extract_products(html, category))

        logger.info(f"Amazon: Scraped {len(products)} total products")
        return products

    async def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
        """Extract products from Amazon HTML."""
        products = []
        soup = self.parse_html(html)

        # Amazon product result items
        items = soup.find_all("div", {"data-component-type": "s-search-result"})
        logger.debug(f"Found {len(items)} items")
        # con = input(f"{len(items)} found with data-component-type. Try with class 's-result-item'? (y/n): ")

        if not items:
            items = soup.find_all("div", class_="s-result-item")
            logger.debug(f"Found {len(items)} items")
        limit = 48 
        elements = []
        for item in items[:limit]:  # Limit to 25 per category
            try:
                # Product name and link
                # search class contiaing "size" 
                
                
                name_elem = item.find("h2", class_=lambda x: x and "size" in x)
                # print(f"name elem: {name_elem}")# Debug log
                elements.append(name_elem)  # Save for debugging

                if not name_elem:
                    name_elem = item.find("span", class_="a-size-base-plus")

                if not name_elem:
                    continue

                name_link = item.find("a",href=True, class_=lambda x: x and "a-link-normal" in x)
                # print(f"name link: {name_link.get('href', 'No href')}")# Debug log
                if not name_link :
                    continue
                
                
                name = name_elem.find("span").get_text(strip=True)
                # print(f"name: {name}")# Debug log
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
                        "style_score": 0.6,  # Default score
                        "available": True,
                    }
                    
                    products.append(product)
                    logger.debug(f"Extracted Amazon product: {name}")

            except Exception as e:
                logger.warning(f"Error extracting Amazon product: {e}")
                continue
                        # save the name_elem to a file for debugging
        with open(f"./htmls/amazon_name_elem_{category.lower()}.html", "w", encoding="utf-8") as f:
                    # write line by line if elements is a list of tags
                    for elem in elements:
                        f.write(str(elem) + "\n")
                    if not elements:
                        f.write("No name element found")

        return products
    

if __name__ == "__main__":
    import asyncio

    async def test_scrape():
        scraper = AmazonScraper()
        products = await scraper.scrape()
        print(f"Scraped {len(products)} products from Amazon.")
        for product in products[:5]:  # Print first 5 products
            print(product)

    asyncio.run(test_scrape())