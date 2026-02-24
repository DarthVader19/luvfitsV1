import logging
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class NordstromScraper(BaseScraper):
    """Nordstrom specific scraper"""
    
    def __init__(self):
        super().__init__("Nordstrom")
    
    def get_category_url(self, category: str) -> str:
        """Get Nordstrom category URL"""
        urls = {
            "Tops": "https://www.nordstrom.com/browse/women/clothing/tops",
            "Bottoms": "https://www.nordstrom.com/browse/women/clothing/bottoms-shorts",
            "Accessories": "https://www.nordstrom.com/browse/women/accessories",
            "Shoes": "https://www.nordstrom.com/browse/women/shoes"
        }
        return urls.get(category)
    
    def extract_products(self, soup) -> list:
        """Extract products from Nordstrom HTML"""
        products = []
        
        # Nordstrom uses various product item selectors
        items = soup.find_all('div', class_='product-grid__item')
        
        if not items:
            items = soup.find_all('article', class_='product-item')
        
        if not items:
            items = soup.find_all('div', {'data-testid': 'productCard'})
        
        for item in items:
            try:
                # Product name and link
                name_elem = item.find('a', class_='product-link')
                if not name_elem:
                    name_elem = item.find('a', class_='product__link')
                
                if name_elem:
                    name = name_elem.text.strip()
                    product_url = name_elem.get('href', '')
                else:
                    continue
                
                # Ensure full URL
                if product_url and not product_url.startswith('http'):
                    product_url = 'https://www.nordstrom.com' + product_url if product_url.startswith('/') else 'https://www.nordstrom.com/' + product_url
                
                # Price
                price_elem = item.find('span', class_='prices')
                if not price_elem:
                    price_elem = item.find('span', {'data-testid': 'value'})
                
                price_text = price_elem.text.strip() if price_elem else '0'
                try:
                    price = float(price_text.replace('$', '').replace(',', '').split('-')[0].strip())
                except:
                    price = 0.0
                
                # Image
                img_elem = item.find('img', class_='product-image')
                if not img_elem:
                    img_elem = item.find('img')
                
                image_url = img_elem.get('src', '') if img_elem else ''
                
                # Color
                color = ''
                color_elem = item.find('span', class_='product-color')
                if color_elem:
                    color = color_elem.text.strip()
                else:
                    for color_keyword in ['black', 'white', 'blue', 'red', 'green', 'pink', 'gray', 'brown', 'navy', 'beige']:
                        if color_keyword in name.lower():
                            color = color_keyword.capitalize()
                            break
                
                # Description
                description = name
                
                if name and product_url and product_url.startswith('http'):
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
                logger.warning(f"Error extracting product from Nordstrom: {str(e)}")
        
        return products
    
    def scrape(self, category: str, num_products: int = 25) -> list:
        """Override to set current category for extraction"""
        self.current_category = category
        return super().scrape(category, num_products)