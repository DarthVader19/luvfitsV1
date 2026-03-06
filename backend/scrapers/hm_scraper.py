# """
# H&M scraper using Scrape.do API.
# """
# import argparse
# import asyncio
# import json
# import logging
# import random
# import re
# from pathlib import Path
# import sys
# from typing import Any, Dict, List, Tuple
# from urllib.parse import urljoin

# try:
#     from .base_scraper import BaseScraper, ProductExtractor
# except ImportError:
#     # Allow direct execution: python .\scrapers\hm_scraper.py
#     sys.path.insert(0, str(Path(__file__).resolve().parent))
#     from base_scraper import BaseScraper, ProductExtractor

# logger = logging.getLogger(__name__)


# class HMScraper(BaseScraper):
#     """H&M specific scraper using Scrape.do."""

#     RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
#     MAX_RETRIES_PER_MODE = 3

#     DEFAULT_CATEGORY_URLS = {
#         "Tops": [
#             "https://www2.hm.com/en_in/women/shop-by-product/tops.html",
#             "https://www2.hm.com/en_us/women/products/hoodies-sweatshirts.html",
#         ],
#         "Bottoms": [
#             "https://www2.hm.com/en_in/women/shop-by-product/bottoms.html",
#             "https://www2.hm.com/en_us/women/products/skirts.html",
#         ],
#         "Accessories": [
#             "https://www2.hm.com/en_in/women/shop-by-product/accessories.html",
#             "https://www2.hm.com/en_us/women/products/accessories.html",
#         ],
#         "Shoes": [
#             "https://www2.hm.com/en_in/women/shop-by-product/shoes.html",
#             "https://www2.hm.com/en_us/women/products/shoes.html",
#         ],
#     }

#     PRODUCT_SELECTORS = [
#         "article[data-articlecode]",
#         "div[data-articlecode]",
#         "li.product-item",
#         "div.product-item",
#         "div.productitem",
#     ]

#     def __init__(self):
#         super().__init__()
#         self.site_name = "H&M"
#         self.base_url = "https://www2.hm.com"
#         self._request_headers = {
#             "User-Agent": (
#                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                 "AppleWebKit/537.36 (KHTML, like Gecko) "
#                 "Chrome/120.0.0.0 Safari/537.36"
#             ),
#             "Accept": (
#                 "text/html,application/xhtml+xml,application/xml;q=0.9,"
#                 "image/avif,image/webp,*/*;q=0.8"
#             ),
#             "Accept-Language": "en-US,en;q=0.9",
#             "Referer": "https://www2.hm.com/",
#             "Connection": "keep-alive",
#         }

#     def _get_category_urls(self, category: str) -> List[str]:
#         """Get H&M category URLs from static defaults only."""
#         return list(dict.fromkeys(self.DEFAULT_CATEGORY_URLS.get(category, [])))

#     def _cache_file_path(self, category: str) -> Path:
#         """Return local cache path for category HTML."""
#         backend_dir = Path(__file__).resolve().parents[1]
#         html_dir = backend_dir / "htmls"
#         html_dir.mkdir(parents=True, exist_ok=True)
#         return html_dir / f"hm_category_{category.lower()}.html"

#     def _save_cached_html(self, category: str, html: str) -> None:
#         """Persist fetched category HTML for fallback debugging."""
#         if not html.strip():
#             return
#         cache_path = self._cache_file_path(category)
#         try:
#             cache_path.write_text(html, encoding="utf-8")
#         except Exception as e:
#             logger.warning("Failed to save cached HTML %s: %s", cache_path, e)

#     def _load_cached_html(self, category: str) -> str:
#         """Load cached category HTML if present."""
#         cache_path = self._cache_file_path(category)
#         if not cache_path.exists():
#             return ""
#         try:
#             return cache_path.read_text(encoding="utf-8")
#         except Exception as e:
#             logger.warning("Failed to read cached HTML %s: %s", cache_path, e)
#             return ""

#     def _safe_price(self, value: Any) -> float:
#         """Best-effort normalization for price fields in H&M JSON."""
#         if value is None:
#             return 0.0
#         if isinstance(value, (int, float)):
#             return float(value)
#         text = str(value)
#         text = re.sub(r"[^\d.,]", "", text).replace(",", "")
#         try:
#             return float(text) if text else 0.0
#         except ValueError:
#             return 0.0

#     async def _extract_from_next_data(self, soup, category: str) -> List[Dict[str, Any]]:
#         """Extract products from Next.js __NEXT_DATA__ payload when available."""
#         script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
#         if not script_tag or not script_tag.string:
#             return []

#         try:
#             data = json.loads(script_tag.string)
#         except json.JSONDecodeError as e:
#             logger.warning("Failed to parse __NEXT_DATA__ JSON: %s", e)
#             return []

#         # H&M shape may vary by region; try known paths first.
#         raw_products = (
#             data.get("props", {})
#             .get("pageProps", {})
#             .get("productListingProps", {})
#             .get("products", [])
#         )
#         if not isinstance(raw_products, list):
#             raw_products = []

#         products: List[Dict[str, Any]] = []
#         for item in raw_products[:25]:
#             if not isinstance(item, dict):
#                 continue

#             name = item.get("productName") or item.get("name") or "H&M Product"
#             link = item.get("link") or item.get("productUrl") or ""
#             product_url = urljoin(self.base_url, link) if link else ""
#             if not product_url:
#                 continue

#             # Image can be dict, list, or nested in different keys.
#             image_url = ""
#             image_data = item.get("image") or item.get("images") or item.get("gallery")
#             if isinstance(image_data, list) and image_data:
#                 first = image_data[0]
#                 if isinstance(first, dict):
#                     image_url = first.get("src") or first.get("url") or ""
#                 elif isinstance(first, str):
#                     image_url = first
#             elif isinstance(image_data, dict):
#                 image_url = image_data.get("src") or image_data.get("url") or ""
#             elif isinstance(image_data, str):
#                 image_url = image_data

#             color = item.get("color") or item.get("mainColor") or "Unknown"
#             description = (
#                 item.get("description")
#                 or item.get("productDescription")
#                 or name
#             )
#             price = self._safe_price(item.get("price"))
#             currency = item.get("currency") or "USD"
#             tags = await ProductExtractor.extract_vibes(name, description, price)

#             products.append(
#                 {
#                     "name": name,
#                     "price": price,
#                     "currency": currency,
#                     "color": color,
#                     "color_family": self.extract_color_family(color),
#                     "description": description,
#                     "image_url": image_url,
#                     "product_url": product_url,
#                     "category": category,
#                     "subcategory": None,
#                     "site": self.site_name,
#                     "tags": tags,
#                     "style_score": 0.7,
#                     "available": not bool(item.get("outOfStock", False)),
#                 }
#             )

#         if products:
#             logger.info("H&M __NEXT_DATA__ extracted %s products for %s", len(products), category)
#         return products

#     async def _fetch_with_retry(self, url: str, debug: bool = False) -> str:
#         """
#         H&M-only resilient fetch.
#         Tries JS-rendered first, then non-rendered, with retry/backoff.
#         """
#         render_modes = [True, False]

#         for render_js in render_modes:
#             for attempt in range(1, self.MAX_RETRIES_PER_MODE + 1):
#                 try:
#                     async with self.session.get(
#                         self.SCRAPE_DO_URL,
#                         params={
#                             "url": url,
#                             "render": "true" if render_js else "false",
#                             "timeout": "30000",
#                             **({"token": self.api_key} if self.api_key else {}),
#                         },
#                         headers=self._request_headers,
#                         timeout=60,
#                     ) as response:
#                         html = await response.text()
#                         status = response.status
#                         if status == 200 and html.strip():
#                             if debug:
#                                 logger.info(
#                                     "[DEBUG] Fetch ok url=%s render_js=%s attempt=%s html_chars=%s",
#                                     url,
#                                     render_js,
#                                     attempt,
#                                     len(html),
#                                 )
#                             return html

#                         if status in self.RETRYABLE_STATUSES:
#                             logger.warning(
#                                 "H&M fetch retry url=%s status=%s render_js=%s attempt=%s/%s",
#                                 url,
#                                 status,
#                                 render_js,
#                                 attempt,
#                                 self.MAX_RETRIES_PER_MODE,
#                             )
#                         else:
#                             logger.error(
#                                 "H&M fetch failed url=%s status=%s render_js=%s (non-retryable)",
#                                 url,
#                                 status,
#                                 render_js,
#                             )
#                             break
#                 except asyncio.TimeoutError:
#                     logger.warning(
#                         "H&M fetch timeout url=%s render_js=%s attempt=%s/%s",
#                         url,
#                         render_js,
#                         attempt,
#                         self.MAX_RETRIES_PER_MODE,
#                     )
#                 except Exception as e:
#                     logger.warning(
#                         "H&M fetch error url=%s render_js=%s attempt=%s/%s error=%s",
#                         url,
#                         render_js,
#                         attempt,
#                         self.MAX_RETRIES_PER_MODE,
#                         e,
#                     )

#                 backoff = (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
#                 await asyncio.sleep(backoff)

#             if debug:
#                 logger.info(
#                     "[DEBUG] Switching render mode for url=%s -> render_js=%s",
#                     url,
#                     not render_js,
#                 )

#         logger.error("H&M fetch exhausted retries url=%s", url)
#         return ""

#     def _find_items(self, soup) -> Tuple[str | None, List[Any]]:
#         """Find product card nodes using known selector fallbacks."""
#         for selector in self.PRODUCT_SELECTORS:
#             found = soup.select(selector)
#             if found:
#                 return selector, found
#         return None, []

#     async def scrape(self, debug: bool = False) -> List[Dict[str, Any]]:
#         """Scrape H&M products."""
#         products: List[Dict[str, Any]] = []
#         categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

#         async with self:
#             for category in categories:
#                 urls = self._get_category_urls(category)
#                 if debug:
#                     logger.info(f"[DEBUG] Category={category} urls={len(urls)}")
#                 for url in urls:
#                     logger.info(f"Scraping H&M {category} from {url}")
#                     html = await self._fetch_with_retry(url, debug=debug)
#                     if not html:
#                         html = self._load_cached_html(category)
#                         if html:
#                             logger.warning(
#                                 "Using cached H&M HTML for category=%s after fetch failure",
#                                 category,
#                             )
#                         if debug:
#                             logger.warning(f"[DEBUG] Empty HTML for url={url}")
#                         if not html:
#                             continue
#                     else:
#                         self._save_cached_html(category, html)

#                     extracted = await self._extract_products(html, category)
#                     products.extend(extracted)
#                     if debug:
#                         logger.info(
#                             f"[DEBUG] url={url} extracted={len(extracted)} total={len(products)}"
#                         )

#                     category_count = len(
#                         [p for p in products if p.get("category") == category]
#                     )
#                     if category_count >= 25:
#                         break
#                     await asyncio.sleep(random.uniform(0.4, 1.0))

#         logger.info(f"H&M: Scraped {len(products)} total products")
#         return products

#     async def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
#         """Extract products from H&M HTML."""
#         soup = self.parse_html(html)
#         json_products = await self._extract_from_next_data(soup, category)
#         if json_products:
#             return json_products

#         products: List[Dict[str, Any]] = []
#         _, items = self._find_items(soup)

#         if not items:
#             return await self._extract_from_links(soup, category)

#         for item in items[:25]:
#             product = await self._parse_item(item, category)
#             if product:
#                 products.append(product)

#         return products

#     async def _extract_from_links(self, soup, category: str) -> List[Dict[str, Any]]:
#         """Fallback extraction from product links when card selectors fail."""
#         products: List[Dict[str, Any]] = []
#         links = soup.select("a[href*='/productpage.']")
#         seen = set()

#         for link in links[:40]:
#             href = link.get("href", "")
#             if not href:
#                 continue
#             product_url = href if href.startswith("http") else urljoin(self.base_url, href)
#             if product_url in seen:
#                 continue
#             seen.add(product_url)

#             name = link.get("title") or link.get_text(strip=True) or "H&M Product"
#             description = name
#             price = 0.0
#             color = "Unknown"
#             tags = await ProductExtractor.extract_vibes(name, description, price)
#             products.append(
#                 {
#                     "name": name,
#                     "price": price,
#                     "currency": "USD",
#                     "color": color,
#                     "color_family": self.extract_color_family(color),
#                     "description": description,
#                     "image_url": "",
#                     "product_url": product_url,
#                     "category": category,
#                     "subcategory": None,
#                     "site": self.site_name,
#                     "tags":tags,
#                     "style_score": 0.7,
#                     "available": True,
#                 }
#             )

#         return products[:25]

#     async def _parse_item(self, item, category: str) -> Dict[str, Any] | None:
#         """Parse one product card."""
#         try:
#             name_elem = item.select_one("a[href*='/productpage.'], a.link, a.item-link")
#             if not name_elem:
#                 return None

#             name = name_elem.get("title") or name_elem.get_text(strip=True) or "H&M Product"
#             href = name_elem.get("href", "")
#             if not href:
#                 return None
#             product_url = href if href.startswith("http") else urljoin(self.base_url, href)

#             price_elem = item.select_one(
#                 "span.price-now, span.a-price, span[data-price], [class*='price']"
#             )
#             price_text = price_elem.get_text(" ", strip=True) if price_elem else "0"
#             price = self.extract_price(price_text)

#             img_elem = item.find("img")
#             image_url = ""
#             alt_text = ""
#             if img_elem:
#                 image_url = (
#                     img_elem.get("src")
#                     or img_elem.get("data-src")
#                     or img_elem.get("data-altimage")
#                     or ""
#                 )
#                 alt_text = img_elem.get("alt", "")

#             description = " ".join([name, item.get_text(" ", strip=True)[:200]]).strip()
#             color = "Unknown"
#             color_match = re.search(
#                 r"\b(black|white|blue|red|green|pink|gray|grey|brown|beige|navy|cream)\b",
#                 f"{alt_text} {description}".lower(),
#             )
#             if color_match:
#                 color = color_match.group(1).capitalize()
#             tags = await ProductExtractor.extract_vibes(name, description, price)
#             return {
#                 "name": name,
#                 "price": price,
#                 "currency": "USD",
#                 "color": color,
#                 "color_family": self.extract_color_family(color),
#                 "description": description,
#                 "image_url": image_url,
#                 "product_url": product_url,
#                 "category": category,
#                 "subcategory": None,
#                 "site": self.site_name,
#                 "tags": tags,
#                 "style_score": 0.7,
#                 "available": True,
#             }
#         except Exception as e:
#             logger.warning(f"Error extracting H&M product: {e}")
#             return None

#     async def debug_scrape(
#         self, max_urls_per_category: int = 1, max_items_per_url: int = 10
#     ) -> Dict[str, Any]:
#         """
#         Debug scraper step-by-step to diagnose extraction issues quickly.
#         """
#         report: Dict[str, Any] = {
#             "site": self.site_name,
#             "categories": {},
#             "totals": {"urls_tested": 0, "products_parsed": 0, "fallback_products": 0},
#         }
#         categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

#         async with self:
#             for category in categories:
#                 category_urls = self._get_category_urls(category)[:max_urls_per_category]
#                 category_report = {
#                     "urls": category_urls,
#                     "url_results": [],
#                     "products_parsed": 0,
#                     "fallback_products": 0,
#                 }
#                 logger.info(f"[DEBUG] Category={category} test_urls={len(category_urls)}")

#                 for url in category_urls:
#                     report["totals"]["urls_tested"] += 1
#                     logger.info(f"[DEBUG] Step 1/4 fetch url={url}")
#                     html = await self._fetch_with_retry(url, debug=True)
#                     if not html:
#                         category_report["url_results"].append(
#                             {"url": url, "ok": False, "reason": "empty_html"}
#                         )
#                         logger.warning(f"[DEBUG] Empty HTML for {url}")
#                         continue

#                     logger.info(f"[DEBUG] Step 2/4 parse HTML chars={len(html)}")
#                     soup = self.parse_html(html)
#                     selector_counts = {
#                         selector: len(soup.select(selector))
#                         for selector in self.PRODUCT_SELECTORS
#                     }
#                     selected_selector, items = self._find_items(soup)

#                     logger.info(
#                         "[DEBUG] Step 3/4 selector results=%s selected=%s items=%s",
#                         selector_counts,
#                         selected_selector,
#                         len(items),
#                     )

#                     parsed_here = 0
#                     fallback_here = 0
#                     if items:
#                         for item in items[:max_items_per_url]:
#                             product = await self._parse_item(item, category)
#                             if product:
#                                 parsed_here += 1
#                     else:
#                         fallback_products = await self._extract_from_links(soup, category)
#                         fallback_here = min(len(fallback_products), max_items_per_url)

#                     logger.info(
#                         f"[DEBUG] Step 4/4 parsed={parsed_here} fallback={fallback_here}"
#                     )

#                     category_report["products_parsed"] += parsed_here
#                     category_report["fallback_products"] += fallback_here
#                     report["totals"]["products_parsed"] += parsed_here
#                     report["totals"]["fallback_products"] += fallback_here
#                     category_report["url_results"].append(
#                         {
#                             "url": url,
#                             "ok": True,
#                             "html_chars": len(html),
#                             "selected_selector": selected_selector,
#                             "selector_counts": selector_counts,
#                             "items_found": len(items),
#                             "parsed_products": parsed_here,
#                             "fallback_products": fallback_here,
#                         }
#                     )

#                 report["categories"][category] = category_report

#         return report


# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Run H&M scraper")
#     parser.add_argument(
#         "--debug",
#         action="store_true",
#         help="Run debug mode with step-by-step diagnostics",
#     )
#     parser.add_argument(
#         "--debug-urls",
#         type=int,
#         default=1,
#         help="Number of URLs per category to test in debug mode",
#     )
#     parser.add_argument(
#         "--debug-items",
#         type=int,
#         default=10,
#         help="Max products to parse per URL in debug mode",
#     )
#     parser.add_argument(
#         "--output",
#         default="hm_products.json",
#         help="Output JSON file path",
#     )
#     args = parser.parse_args()

#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s %(levelname)s %(name)s: %(message)s",
#     )

#     async def run():
#         scraper = HMScraper()
#         if args.debug:
#             report = await scraper.debug_scrape(
#                 max_urls_per_category=max(1, args.debug_urls),
#                 max_items_per_url=max(1, args.debug_items),
#             )
#             with open(args.output, "w", encoding="utf-8") as f:
#                 json.dump(report, f, indent=2)
#             print(json.dumps(report["totals"], indent=2))
#             print(f"Debug report saved to {args.output}")
#             return

#         products = await scraper.scrape()
#         with open(args.output, "w", encoding="utf-8") as f:
#             json.dump(products, f, indent=2)

#         print(f"Scraped {len(products)} products from H&M")
#         for p in products[:5]:
#             print(p)

#     asyncio.run(run())



"""
H&M scraper using Scrape.do API - 2025/2026 fixed version
"""
import argparse
import asyncio
import json
import logging
import random
import re
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin

try:
    from .base_scraper import BaseScraper, ProductExtractor
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from base_scraper import BaseScraper, ProductExtractor

logger = logging.getLogger(__name__)


class HMScraper(BaseScraper):
    """H&M scraper - resilient version for 2025/2026"""

    RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
    MAX_RETRIES_PER_MODE = 3

    DEFAULT_CATEGORY_URLS = {
        "Tops": [
            "https://www2.hm.com/en_in/women/shop-by-product/tops.html",
            "https://www2.hm.com/en_us/women/products/hoodies-sweatshirts.html",
        ],
        "Bottoms": [
            "https://www2.hm.com/en_in/women/shop-by-product/bottoms.html",
            "https://www2.hm.com/en_us/women/products/skirts.html",
        ],
        "Accessories": [
            "https://www2.hm.com/en_in/women/shop-by-product/accessories.html",
            "https://www2.hm.com/en_us/women/products/accessories.html",
        ],
        "Shoes": [
            "https://www2.hm.com/en_in/women/shop-by-product/shoes.html",
            "https://www2.hm.com/en_us/women/products/shoes.html",
        ],
    }

    PRODUCT_SELECTORS = [
        "article[data-articlecode]",
        "div[data-articlecode]",
        "li.product-item",
        "div.product-item",
        "div[data-testid='product-item']",
        "article[class*='Product']",
    ]

    def __init__(self):
        super().__init__()
        self.site_name = "H&M"
        self.base_url = "https://www2.hm.com"
        self._request_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www2.hm.com/",
            "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }

    def _get_category_urls(self, category: str) -> List[str]:
        return list(dict.fromkeys(self.DEFAULT_CATEGORY_URLS.get(category, [])))

    def _cache_file_path(self, category: str) -> Path:
        backend_dir = Path(__file__).resolve().parents[1]
        html_dir = backend_dir / "htmls"
        html_dir.mkdir(parents=True, exist_ok=True)
        return html_dir / f"hm_{category.lower()}.html"

    def _save_cached_html(self, category: str, html: str) -> None:
        if not html.strip():
            return
        try:
            self._cache_file_path(category).write_text(html, encoding="utf-8")
        except Exception as e:
            logger.warning("Cache save failed: %s", e)

    def _load_cached_html(self, category: str) -> str:
        path = self._cache_file_path(category)
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _safe_price(self, value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            value = value.get("value") or value.get("price") or 0
        text = str(value).replace(",", "").replace("₹", "").replace("$", "").strip()
        try:
            return float(text) if text else 0.0
        except ValueError:
            return 0.0

    async def _extract_from_next_data(self, soup, category: str) -> List[Dict[str, Any]]:
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script or not script.string:
            return []

        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            return []

        # Try several known 2025–2026 paths
        paths = [
            lambda d: d["props"]["pageProps"]["initialState"]["search"]["result"]["hits"],
            lambda d: d["props"]["pageProps"]["srpProps"]["hits"],
            lambda d: d["props"]["pageProps"]["productListingProps"]["products"],
            lambda d: d["props"]["pageProps"]["searchResults"]["items"],
            lambda d: d["props"]["pageProps"]["products"],
            lambda d: d["props"]["pageProps"]["initialState"]["products"],
        ]

        raw_products = []
        for finder in paths:
            try:
                val = finder(data)
                if isinstance(val, list) and val:
                    raw_products = val
                    break
            except (KeyError, TypeError):
                continue

        if not raw_products:
            return []

        products = []
        for item in raw_products[:25]:
            if not isinstance(item, dict):
                continue

            name = item.get("name") or item.get("productName") or item.get("title") or "Unknown"
            link = (
                item.get("pdpUrl")
                or item.get("link")
                or item.get("productUrl")
                or item.get("url")
                or ""
            )
            product_url = urljoin(self.base_url, link) if link else ""
            if not product_url:
                continue

            # Image
            image_url = ""
            imgs = item.get("images", []) or item.get("gallery", []) or []
            if imgs:
                first = imgs[0] if isinstance(imgs, list) else imgs
                image_url = first.get("url") or first.get("src") or first.get("large") or ""

            price = self._safe_price(
                item.get("price", {}).get("value")
                or item.get("regularPrice", {}).get("value")
                or item.get("price", 0)
            )

            currency = (
                item.get("currency")
                or item.get("price", {}).get("currency")
                or "INR"
            )

            color = (
                item.get("color", {}).get("name")
                or item.get("color")
                or item.get("mainColor")
                or "Unknown"
            )

            description = item.get("description") or name

            tags = await ProductExtractor.extract_vibes(name, description, price)

            products.append({
                "name": name,
                "price": price,
                "currency": currency,
                "color": color,
                "color_family": self.extract_color_family(color),
                "description": description,
                "image_url": image_url,
                "product_url": product_url,
                "category": category,
                "subcategory": None,
                "site": self.site_name,
                "tags": tags,
                "style_score": 0.7,
                "available": not bool(item.get("outOfStock", False)),
            })

        if products:
            logger.info("Extracted %d products from __NEXT_DATA__ for %s", len(products), category)
        return products

    async def _fetch_with_retry(self, url: str, debug: bool = False) -> str:
        # Try non-rendered first — much lower ban/502 rate on many sites
        render_modes = [False, True]

        for render_js in render_modes:
            for attempt in range(1, self.MAX_RETRIES_PER_MODE + 1):
                try:
                    params = {
                        "url": url,
                        "render": str(render_js).lower(),
                        "timeout": "40000",
                    }
                    if self.api_key:
                        params["token"] = self.api_key

                    async with self.session.get(
                        self.SCRAPE_DO_URL,
                        params=params,
                        headers=self._request_headers,
                        timeout=90,
                    ) as resp:
                        html = await resp.text()
                        status = resp.status

                        if status == 200 and len(html) > 2000:
                            if debug:
                                logger.info("Success - render=%s attempt=%d len=%d", render_js, attempt, len(html))
                            return html

                        if status in self.RETRYABLE_STATUSES:
                            delay = (3 ** attempt) + random.uniform(1.5, 5.0)  # longer on 502/429
                            logger.warning("Retry %d/%d | status=%d | render=%s | wait=%.1fs", 
                                           attempt, self.MAX_RETRIES_PER_MODE, status, render_js, delay)
                            await asyncio.sleep(delay)
                        else:
                            logger.error("Non-retryable status %d for %s", status, url)
                            break

                except asyncio.TimeoutError:
                    logger.warning("Timeout render=%s attempt=%d", render_js, attempt)
                except Exception as e:
                    logger.warning("Fetch error render=%s attempt=%d: %s", render_js, attempt, e)

            if debug:
                logger.info("Switching render mode → %s", not render_js)

        logger.error("Exhausted retries for %s", url)
        return ""
    

    def _find_items(self, soup) -> Tuple[str | None, List[Any]]:
        """Find product card nodes using known selector fallbacks."""
        for selector in self.PRODUCT_SELECTORS:
            found = soup.select(selector)
            if found:
                return selector, found
        return None, []

    async def scrape(self, debug: bool = False) -> List[Dict[str, Any]]:
        """Scrape H&M products."""
        products: List[Dict[str, Any]] = []
        categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

        async with self:
            for category in categories:
                urls = self._get_category_urls(category)
                if debug:
                    logger.info(f"[DEBUG] Category={category} urls={len(urls)}")
                for url in urls:
                    logger.info(f"Scraping H&M {category} from {url}")
                    html = await self._fetch_with_retry(url, debug=debug)
                    if not html:
                        html = self._load_cached_html(category)
                        if html:
                            logger.warning(
                                "Using cached H&M HTML for category=%s after fetch failure",
                                category,
                            )
                        if debug:
                            logger.warning(f"[DEBUG] Empty HTML for url={url}")
                        if not html:
                            continue
                    else:
                        self._save_cached_html(category, html)

                    extracted = await self._extract_products(html, category)
                    products.extend(extracted)
                    if debug:
                        logger.info(
                            f"[DEBUG] url={url} extracted={len(extracted)} total={len(products)}"
                        )

                    category_count = len(
                        [p for p in products if p.get("category") == category]
                    )
                    if category_count >= 25:
                        break
                    await asyncio.sleep(random.uniform(0.4, 1.0))

        logger.info(f"H&M: Scraped {len(products)} total products")
        return products

    async def _extract_products(self, html: str, category: str) -> List[Dict[str, Any]]:
        """Extract products from H&M HTML."""
        soup = self.parse_html(html)
        json_products = await self._extract_from_next_data(soup, category)
        if json_products:
            return json_products

        products: List[Dict[str, Any]] = []
        _, items = self._find_items(soup)

        if not items:
            return await self._extract_from_links(soup, category)

        for item in items[:25]:
            product = await self._parse_item(item, category)
            if product:
                products.append(product)

        return products

    async def _extract_from_links(self, soup, category: str) -> List[Dict[str, Any]]:
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
            tags = await ProductExtractor.extract_vibes(name, description, price)
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
                    "tags":tags,
                    "style_score": 0.7,
                    "available": True,
                }
            )

        return products[:25]

    async def _parse_item(self, item, category: str) -> Dict[str, Any] | None:
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
            tags = await ProductExtractor.extract_vibes(name, description, price)
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
                "tags": tags,
                "style_score": 0.7,
                "available": True,
            }
        except Exception as e:
            logger.warning(f"Error extracting H&M product: {e}")
            return None

    async def scrape(self, debug: bool = False) -> List[Dict[str, Any]]:
        products: List[Dict[str, Any]] = []
        categories = ["Tops", "Bottoms", "Accessories", "Shoes"]

        async with self:
            for category in categories:
                urls = self._get_category_urls(category)
                for url in urls:
                    logger.info("Scraping %s → %s", category, url)
                    html = await self._fetch_with_retry(url, debug=debug)

                    if not html:
                        html = self._load_cached_html(category)
                        if html:
                            logger.info("Using cached HTML for %s", category)
                        else:
                            continue
                    else:
                        self._save_cached_html(category, html)

                    extracted = await self._extract_products(html, category)
                    products.extend(extracted)

                    if len([p for p in products if p["category"] == category]) >= 25:
                        break

                    await asyncio.sleep(random.uniform(0.8, 2.2))

        logger.info("H&M total products scraped: %d", len(products))
        return products

    # The rest of the methods (_extract_products, _extract_from_links, _parse_item, debug_scrape, etc.)
    # remain the same as in your original code unless you want further changes.
    # Most important fixes are already in _extract_from_next_data and _fetch_with_retry.

    # ... (keep your existing _extract_products, _find_items, _parse_item, _extract_from_links, debug_scrape)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="H&M Scraper (fixed)")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--debug-urls", type=int, default=1)
    parser.add_argument("--debug-items", type=int, default=10)
    parser.add_argument("--output", default="hm_products.json")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    async def main():
        scraper = HMScraper()
        if args.debug:
            report = await scraper.debug_scrape(
                max_urls_per_category=args.debug_urls,
                max_items_per_url=args.debug_items
            )
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print("Debug report saved →", args.output)
            print(json.dumps(report["totals"], indent=2))
            return

        products = await scraper.scrape(debug=args.debug)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False)

        print(f"\nScraped {len(products)} products")
        if products:
            print("Sample:")
            for p in products[:3]:
                print(f"  • {p['name'][:60]}... | ₹{p['price']} | {p['product_url']}")

    asyncio.run(main())
