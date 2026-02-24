import time
import random
import logging
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Base class for all site-specific scrapers"""
    
    def __init__(self, site_name: str):
        self.site_name = site_name
        self.products = []
        self.driver = None
        self.wait_time = 10
        
    @abstractmethod
    def get_category_url(self, category: str) -> str:
        """Return URL for a specific category"""
        pass
    
    @abstractmethod
    def extract_products(self, soup) -> list:
        """Extract products from beautifulsoup object"""
        pass
    
    def get_driver(self):
        """Initialize Chrome webdriver with anti-detection measures"""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-data-dir=/tmp/chrome")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--start-maximized")
        
        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
        return driver
    
    def fetch_page(self, url: str, retry_count: int = 3) -> str:
        """Fetch page content with retries and delays"""
        for attempt in range(retry_count):
            try:
                if self.driver is None:
                    self.driver = self.get_driver()
                
                self.driver.get(url)
                time.sleep(random.uniform(2, 5))
                
                # Wait for main content to load
                WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, "body"))
                )
                
                return self.driver.page_source
            except TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1} for {url}")
                if attempt < retry_count - 1:
                    time.sleep(random.uniform(5, 10))
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(random.uniform(5, 10))
    
        return None
    
    def parse_html(self, html: str):
        """Parse HTML and extract products"""
        if not html:
            logger.error("No HTML content to parse")
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        return self.extract_products(soup)
    
    def generate_tags(self, name: str, description: str, category: str, color: str = "") -> str:
        """Generate tags based on product attributes"""
        tags = set()
        text = (name + ' ' + description + ' ' + color).lower()
        
        # Style tags
        if any(word in text for word in ['jeans', 'denim']):
            tags.add('casual')
        if any(word in text for word in ['dress', 'blouse', 'blazer']):
            tags.add('elegant')
        if any(word in text for word in ['hoodie', 'sweater', 'tee']):
            tags.add('casual')
        
        # Color tags
        if any(word in text for word in ['black', 'navy', 'charcoal', 'dark']):
            tags.add('dark')
        if any(word in text for word in ['white', 'cream', 'beige', 'light']):
            tags.add('light')
        if any(word in text for word in ['red', 'pink', 'magenta']):
            tags.add('warm')
        if any(word in text for word in ['blue', 'teal', 'purple']):
            tags.add('cool')
        
        # Occasion tags
        if any(word in text for word in ['heel', 'stiletto', 'formal']):
            tags.add('formal')
        if any(word in text for word in ['sneaker', 'trainer', 'casual']):
            tags.add('sporty')
        if any(word in text for word in ['party', 'night', 'dance', 'glitter']):
            tags.add('party')
        if any(word in text for word in ['90s', 'retro', 'vintage', 'grunge']):
            tags.add('90s')
        if any(word in text for word in ['minimalist', 'simple', 'plain']):
            tags.add('minimalist')
        
        # Fallback
        if not tags:
            tags.add('neutral')
        
        return ', '.join(sorted(tags))
    
    def get_color_family(self, color: str) -> str:
        """Categorize color into family"""
        color = color.lower() if color else ""
        
        if any(c in color for c in ['black', 'white', 'gray', 'grey']):
            return 'neutral'
        elif any(c in color for c in ['red', 'orange', 'yellow', 'brown']):
            return 'warm'
        elif any(c in color for c in ['blue', 'green', 'purple', 'teal']):
            return 'cool'
        elif any(c in color for c in ['pink', 'rose', 'coral']):
            return 'warm'
        else:
            return 'neutral'
    
    def scrape(self, category: str, num_products: int = 25) -> list:
        """Main scraping method"""
        products = []
        url = self.get_category_url(category)
        
        if not url:
            logger.error(f"Invalid category: {category}")
            return []
        
        try:
            html = self.fetch_page(url)
            if html:
                products = self.parse_html(html)
                logger.info(f"Scraped {len(products)} products from {self.site_name} - {category}")
        except Exception as e:
            logger.error(f"Error scraping {self.site_name}: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
        
        return products[:num_products]
    
    def close(self):
        """Close driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
