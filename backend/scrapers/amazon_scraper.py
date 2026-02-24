import logging
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class AmazonScraper(BaseScraper):
    """Amazon specific scraper"""
    
    def __init__(self):
        super().__init__("Amazon")
    
    def get_category_url(self, category: str) -> str:
        """Get Amazon category URL"""
        queries = {
            "Tops": "women+clothing+tops",
            "Bottoms": "women+clothing+bottoms+jeans+pants",
            "Accessories": "women+fashion+accessories",
            "Shoes": "women+shoes"
        }
        query = queries.get(category, "")
        return f"https://www.amazon.com/s?k={query}" if query else None
    
    def extract_products(self, soup) -> list:
        """Extract products from Amazon HTML"""
        products = []
        
        # Amazon uses various selectors for product items
        items = soup.find_all('div', {'data-component-type': 's-search-result'})
        
        if not items:
            items = soup.find_all('div', class_='s-result-item')
        
        for item in items:
            try:
                # Product name and link
                name_elem = item.find('h2', class_='s-size')
                if not name_elem:
                    name_elem = item.find('span', class_='a-size-base-plus')
                
                if name_elem:
                    name_link = name_elem.find('a')
                    name = name_link.text.strip() if name_link else ''
                    product_url = name_link.get('href', '') if name_link else ''
                else:
                    continue
                
                # Ensure full URL
                if product_url and not product_url.startswith('http'):
                    product_url = 'https://www.amazon.com' + product_url if product_url.startswith('/') else 'https://www.amazon.com/' + product_url
                
                # Price
                price_elem = item.find('span', class_='a-price-whole')
                price_text = price_elem.text.strip() if price_elem else '0'
                try:
                    price = float(price_text.replace('$', '').replace(',', ''))
                except:
                    price = 0.0
                
                # Image
                img_elem = item.find('img', class_='s-image')
                image_url = img_elem.get('src', '') if img_elem else ''
                
                # Color (try to extract from name)
                color = ''
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
                logger.warning(f"Error extracting product from Amazon: {str(e)}")
        
        return products
    
    def scrape(self, category: str, num_products: int = 25) -> list:
        """Override to set current category for extraction"""
        self.current_category = category
        return super().scrape(category, num_products)