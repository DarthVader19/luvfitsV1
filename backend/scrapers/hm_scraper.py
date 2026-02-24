import logging
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class HMScraper(BaseScraper):
    """H&M specific scraper"""
    
    def __init__(self):
        super().__init__("H&M")
    
    def get_category_url(self, category: str) -> str:
        """Get H&M category URL"""
        urls = {
            "Tops": "https://www.hm.com/en_us/women/products/tops.html",
            "Bottoms": "https://www.hm.com/en_us/women/products/bottoms.html",
            "Accessories": "https://www.hm.com/en_us/women/products/accessories.html",
            "Shoes": "https://www.hm.com/en_us/women/products/shoes.html"
        }
        return urls.get(category)
    
    def extract_products(self, soup) -> list:
        """Extract products from H&M HTML"""
        products = []
        
        # H&M uses product-list items
        items = soup.find_all('div', class_='productitem')
        
        if not items:
            # Try alternative selector
            items = soup.find_all('div', {'data-testid': 'product-item'})
        
        for item in items:
            try:
                # Product name
                name_elem = item.find('a', class_='link')
                name = name_elem.text.strip() if name_elem else ''
                
                # Product URL
                product_url = name_elem.get('href', '') if name_elem else ''
                if product_url.startswith('/'):
                    product_url = 'https://www.hm.com' + product_url
                elif not product_url.startswith('http'):
                    product_url = 'https://www.hm.com/' + product_url
                
                # Price
                price_elem = item.find('span', class_='price-now')
                price_text = price_elem.text.strip() if price_elem else '0'
                try:
                    price = float(price_text.replace('$', '').replace(',', ''))
                except:
                    price = 0.0
                
                # Image
                img_elem = item.find('img')
                image_url = img_elem.get('src', '') if img_elem else ''
                
                # Color (from title or alt text)
                color = img_elem.get('alt', '').split('|')[1].strip() if img_elem and '|' in img_elem.get('alt', '') else ''
                
                # Description
                description = name
                
                if name and product_url:
                    product = {
                        'name': name,
                        'price': price,
                        'color': color,
                        'description': description,
                        'image_url': image_url,
                        'product_url': product_url,
                        'category': self.current_category,
                        'site': self.site_name,
                        'tags': self.generate_tags(name, description, self.current_category, color),
                        'color_family': self.get_color_family(color)
                    }
                    products.append(product)
                    logger.debug(f"Extracted: {name}")
            except Exception as e:
                logger.warning(f"Error extracting product from H&M: {str(e)}")
        
        return products
    
    def scrape(self, category: str, num_products: int = 25) -> list:
        """Override to set current category for extraction"""
        self.current_category = category
        return super().scrape(category, num_products)