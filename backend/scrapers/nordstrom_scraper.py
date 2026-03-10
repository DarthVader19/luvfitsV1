"""Nordstrom scraper using Scrape.do API."""
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
try:

   from .base_scraper import BaseScraper, ProductExtractor
except ImportError:
    from base_scraper import BaseScraper, ProductExtractor

logger = logging.getLogger(__name__)


class NordstromScraper(BaseScraper):
    """Nordstrom specific scraper using Scrape.do."""

    def __init__(self):
        super().__init__()
        self.site_name = "Nordstrom"
        self.base_url = "https://www.nordstrom.com"
        self._request_headers = {
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nordstrom.com",
            "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }
        self._max_retries_per_mode = 1

    def _get_category_url(self, category: str) -> str:
        """Get Nordstrom category URL."""
        urls = {
            "Tops": "https://www.nordstrom.com/browse/women/clothing/tops",
            "Bottoms": "https://www.nordstrom.com/browse/women/clothing/pants",
            "Accessories": "https://www.nordstrom.com/browse/women/accessories",
            "Shoes": "https://www.nordstrom.com/browse/women/shoes",
        }
        return urls.get(category, "")

    def _products_output_path(self) -> Path:
        backend_dir = Path(__file__).resolve().parents[1]
        output_dir = backend_dir / "htmls"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / "nordstrom_products_test.json"

    def _html_cache_dir(self) -> Path:
        backend_dir = Path(__file__).resolve().parents[1]
        cache_dir = backend_dir / "htmls"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _category_html_cache_path(self, category: str) -> Path:
        slug = category.strip().lower().replace(" ", "_")
        return self._html_cache_dir() / f"nordstrom_{slug}.html"

    def _load_cached_html(self, category: str) -> str:
        cache_path = self._category_html_cache_path(category)
        if not cache_path.exists():
            return ""
        try:
            html = cache_path.read_text(encoding="utf-8")
            if html.strip():
                logger.info("Nordstrom: Using cached HTML for %s from %s", category, cache_path)
                return html
            logger.warning("Nordstrom: Cached HTML is empty for %s at %s", category, cache_path)
            return ""
        except Exception as e:
            logger.warning("Nordstrom: Failed to read cached HTML for %s: %s", category, e)
            return ""

    def _save_cached_html(self, category: str, html: str) -> None:
        if not html.strip():
            return
        cache_path = self._category_html_cache_path(category)
        try:
            cache_path.write_text(html, encoding="utf-8")
            logger.info("Nordstrom: Saved HTML cache for %s to %s", category, cache_path)
        except Exception as e:
            logger.warning("Nordstrom: Failed to save HTML cache for %s: %s", category, e)

    def _save_products_for_testing(self, products: List[Dict[str, Any]]) -> None:
        output_path = self._products_output_path()
        try:
            output_path.write_text(
                json.dumps(products, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Nordstrom: Saved %s products to %s", len(products), output_path)
        except Exception as e:
            logger.warning("Nordstrom: Failed to save test JSON %s: %s", output_path, e)

    async def _fetch_with_retry(self, url: str) -> str:
        """
        Nordstrom-specific fetch with retry and render fallback.
        Uses cleaner request params than BaseScraper.scrape_page to avoid 400 responses.
        """
        render_modes = [False, True]

        for render_js in render_modes:
            for attempt in range(1, self._max_retries_per_mode + 1):
                try:
                    params = {
                        "url": url,
                        "render": str(render_js).lower(),
                        "timeout": "45000",
                        "super": "true",
                        "geoCode": "us",
                    }
                    if self.api_key:
                        params["token"] = self.api_key

                    async with self.session.get(
                        self.SCRAPE_DO_URL,
                        params=params,
                        headers=self._request_headers,
                        timeout=90,
                    ) as response:
                        html = await response.text()
                        if response.status == 200 and html.strip():
                            return html

                        response_preview = html[:800].replace("\n", " ").strip()
                        logger.warning(
                            "Nordstrom fetch failed status=%s render_js=%s attempt=%s/%s url=%s body=%s",
                            response.status,
                            render_js,
                            attempt,
                            self._max_retries_per_mode,
                            url,
                            response_preview,
                        )

                except asyncio.TimeoutError:
                    logger.warning(
                        "Nordstrom fetch timeout render_js=%s attempt=%s/%s url=%s",
                        render_js,
                        attempt,
                        self._max_retries_per_mode,
                        url,
                    )
                except Exception as e:
                    logger.warning(
                        "Nordstrom fetch error render_js=%s attempt=%s/%s url=%s error=%s",
                        render_js,
                        attempt,
                        self._max_retries_per_mode,
                        url,
                        e,
                    )

                await asyncio.sleep(min(2 ** attempt, 6))

        logger.error("Nordstrom fetch exhausted retries url=%s", url)
        return ""

    async def scrape(self,categories = ["Tops", "Bottoms", "Accessories", "Shoes"]) -> List[Dict[str, Any]]:
        """Scrape Nordstrom products."""
        products = []
        
        # categories = [ "Accessories"]
        async with self:
            for category in categories[:1]:  # Limit to first category for testing
                url = self._get_category_url(category)
                if not url:
                    continue

                html = self._load_cached_html(category)
                if not html:
                    logger.info(f"Scraping Nordstrom {category} from {url}")
                    html = await self._fetch_with_retry(url)
                    if html:
                        self._save_cached_html(category, html)

                if html:
                    products.extend(await self._extract_products(html, category))
                else:
                    logger.warning("Nordstrom: Empty HTML for category=%s", category)

        logger.info(f"Nordstrom: Scraped {len(products)} total products")
        self._save_products_for_testing(products)
        return products

    async def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
        """Extract products from Nordstrom HTML."""
        products = []
        soup = self.parse_html(html)

        # Nordstrom product grid items
        items = soup.find_all("div", class_="product-grid__item")
        if not items:
            items = soup.find_all("article", {"class":True})
            logger.debug(f"Nordstrom: Found {len(items)} potential product items using fallback selector article")
        if not items:
            items = soup.find_all("div", {"data-testid": "productCard"})
        limit= 30
        for item in items[:limit]:  # Limit to 25 per category
            try:
                # Product name and link
                name_elem = item.find("a", class_="product-link")
                if not name_elem:
                    name_elem = item.find("a", {"class": True, "href": True})

                if not name_elem:
                    continue

                name = name_elem.get("aria-label", name_elem.text.strip())
                product_url = name_elem.get("href", "")
                if not product_url.startswith("http"):
                    product_url = self.base_url + product_url

                # Price
                price_elem = item.find("span", class_="prices")
                if not price_elem:
                    price_elem = item.find("span", {"data-testid": "value"})
                
                if not price_elem:
                    # get price using xpath like selector //*[@id="product-results-view"]/div/div/section/div/article[1]/div[3]/div/span[1]
                    price_elem = item.find("span", string=lambda s: s and "$" in s)
                    logger.debug(f"Nordstrom: Found price element using fallback selector span with $ in text: {price_elem}")

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
    

if __name__ == "__main__":
    import asyncio

    async def main():
        scraper = NordstromScraper()
        products = await scraper.scrape()
        print(f"Scraped {len(products)} products from Nordstrom")
        for product in products[:5]:  # Print first 5 products
            print(product)

    asyncio.run(main())
