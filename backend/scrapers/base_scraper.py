"""
Base scraper class using Scrape.do API for all sites.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any
from abc import ABC, abstractmethod

# from flask import json
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import ollama
import requests

# Load backend/.env and project-root/.env if present.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env")

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all scrapers using Scrape.do."""

    SCRAPE_DO_URL = "https://api.scrape.do"

    def __init__(self):
        self.api_key = os.getenv("SCRAPE_DO_API_KEY", "")
        self.session: aiohttp.ClientSession = None
        self.site_name = "Unknown"
        self.base_url = ""

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def scrape_page(self, url: str, render_js: bool = False, headers: dict = {"User-Agent": "Mozilla/5.0",
                         "Accept-Language": "en-US,en;q=0.9",
                         "Accept-Encoding": "gzip, deflate, br",
                         "Connection": "keep-alive"}) -> str:
        """
        Scrape a page using Scrape.do API.

        Args:
            url: The URL to scrape
            render_js: Whether to render JavaScript
        Returns:
            HTML content of the page
        """
        try:
            async with self.session.get(
                self.SCRAPE_DO_URL,
                params={
                    "url": url,
                    "render": "true" if render_js else "false",
                    "timeout": "30000",
                    **({"token": self.api_key} if self.api_key else {}),
                    "custom_headers": json.dumps(headers)  # Pass custom headers to Scrape.do
                },
                headers=headers,
                timeout=60,
            ) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Failed to scrape {url}: {response.status}, {type(response.status)}")
                    if response.status in [403,401]:
                        # try using request library as fallback for 403 or 401 errors which might indicate bot detection
                        logger.info(f"Attempting fallback scraping for {url} using requests library due to status {response.status}")
                        try:
                            resp = requests.get(url, headers=headers, timeout=30)
                            if resp.status_code == 200:
                                print(f"Fallback scraping successful for {url} with status {resp.status_code}")
                                return resp.text
                            else:
                                logger.error(f"Fallback scraping also failed for {url}: {resp.status_code}")
                        except Exception as e:
                            logger.error(f"Error during fallback scraping for {url}: {e}")

                        return ""
        except asyncio.TimeoutError:
            logger.error(f"Timeout scraping {url}")
            return ""
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return ""

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html, "html.parser")

    @abstractmethod
    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Scrape data from the site.
        Must be implemented by subclasses.
        """
        pass

    def extract_color_family(self, color: str) -> str:
        """Extract color family from color name."""
        color_lower = color.lower()

        if any(word in color_lower for word in ["white", "black", "gray", "grey", "beige", "ivory", "cream", "tan"]):
            return "neutral"
        elif any(word in color_lower for word in ["red", "orange", "yellow", "brown"]):
            return "warm"
        elif any(word in color_lower for word in ["blue", "green", "purple", "violet", "teal"]):
            return "cool"
        elif any(word in color_lower for word in ["pink", "red", "blue", "yellow", "green"]):
            return "primary"
        else:
            return "neutral"

    def extract_price(self, price_str: str) -> float:
        """Extract numeric price from string."""
        import re

        match = re.search(r"[\d,]+\.?\d*", price_str.replace(",", ""))
        return float(match.group()) if match else 0.0



class ProductExtractor:
    """Utility class for extracting product data."""

    @staticmethod
    def categorize_product(
        name: str, description: str = "", category_hint: str = ""
    ) -> str:
        """Categorize product using Google taxonomy."""
        name_lower = (name + " " + description).lower()

        # Simplified categorization (can be extended)
        if any(word in name_lower for word in ["shirt", "blouse", "top", "t-shirt", "sweater", "hoodie", "jacket", "coat"]):
            return "Tops"
        elif any(word in name_lower for word in ["pants", "jeans", "shorts", "skirt", "leggings", "trousers"]):
            return "Bottoms"
        elif any(word in name_lower for word in ["shoe", "sneaker", "boot", "sandal", "heel", "flat"]):
            return "Shoes"
        elif any(word in name_lower for word in ["bag", "watch", "necklace", "earring", "ring", "bracelet", "scarf", "hat", "belt"]):
            return "Accessories"
        else:
            return category_hint or "Tops"
    


    @staticmethod
    async def extract_vibes(name: str, description: str = "", price: float = 0) -> List[str]:
        """Extract vibe tags from product data."""
        tags = []
        full_text = (name + " " + description).lower()

        # Occasion tags
        if any(word in full_text for word in ["casual", "everyday"]):
            tags.append("casual")
        if any(word in full_text for word in ["formal", "dress", "elegant"]):
            tags.append("elegant")
        if any(word in full_text for word in ["party", "night", "club"]):
            tags.append("party")
        if any(word in full_text for word in ["date", "romantic"]):
            tags.append("date night")

        # Style tags
        if any(word in full_text for word in ["90s", "retro", "vintage"]):
            tags.append("90s")
        if any(word in full_text for word in ["minimalist", "simple"]):
            tags.append("minimalist")
        if any(word in full_text for word in ["sporty", "athletic", "gym"]):
            tags.append("sporty")
        if any(word in full_text for word in ["grunge", "dark"]):
            tags.append("grunge")
        
        # Use AI extraction for more nuanced classification
        try:
            extractor = VibeExtractor()
            ai_tags = await extractor.extract_vibes(
                name=name,
                description=description
            )
            tags.extend(ai_tags)
            logger.debug(f"AI tags for '{name}': {ai_tags}")
        except Exception as e:
            logger.warning(f"AI vibe extraction failed for '{name}': {e}")

        # Remove duplicates and return
        unique_tags = list(set(tags))
        if not unique_tags:
            logger.warning(f"No vibe tags extracted (keyword or AI) for: {name}")
        
        return unique_tags
    
    async def calculate_style_score(self, name: str, description: str) -> float:
        """Calculate style score using ollama model."""
        prompt = f"On a scale of 0 to 10, how stylish is an item with the following name and description? Name: {name} Description: {description} Just respond with the number."
        ollama_client = OllamaClient()
        score = await ollama_client.get_response(prompt)
        try:
            return float(score.strip())
        except ValueError:
            logger.warning(f"Could not convert style score to float: '{score}'")
            return 0.0


class OllamaClient:
    """Client for interacting with Ollama API."""
   

    def __init__(self, model_name: str = "qwen3:0.6b"):
        self.model_name = model_name
        
    
    async def get_response(self, prompt: str) -> str:
        """Get response from Ollama model."""
        try:
            response = ollama.chat(
                self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            logger.info(f"Ollama respons': {response}")
            return response.get("message", {}).get("content", "0")
        except Exception as e:
            logger.error(f"Error getting response from Ollama: {e}")
            return "0"  # Default to 0 if there's an error

    




from transformers import pipeline
from typing import List
import torch
import os

# Set Hugging Face cache directory to avoid repeated downloads
if not os.getenv('HF_HOME'):
    _hf_cache_dir = Path(__file__).resolve().parents[1] / ".cache" / "huggingface"
    os.environ['HF_HOME'] = str(_hf_cache_dir)
    os.environ['HF_HUB_CACHE'] = str(_hf_cache_dir)

#save model so it doesn t have to be downloaded every time
class ModelCache:
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self.classifier = None
        self.model_name = "valhalla/distilbart-mnli-12-1"
    
    @classmethod
    async def get_instance(cls):
        """Get or create singleton instance with thread safety."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = ModelCache()
                    await cls._instance._load_model()
        return cls._instance
    
    async def _load_model(self):
        """Load the model once."""
        if self.classifier is None:
            logger.info(f"Loading AI model {self.model_name}...")
            device = 0 if torch.cuda.is_available() else -1
            device_str = "cuda" if device == 0 else "cpu"
            logger.info(f"Device set to use {device_str}")
            loop = asyncio.get_event_loop()
            try:
                self.classifier = await loop.run_in_executor(
                    None,
                    lambda: pipeline(
                        "zero-shot-classification",
                        model=self.model_name,
                        framework="pt",  # Explicitly specify PyTorch framework
                        device=device
                    )
                )
                logger.info(f"AI model loaded successfully on {device_str}")
            except Exception as e:
                logger.error(f"Failed to load model on {device_str}: {e}")
                # Fallback to CPU if GPU fails
                if device != -1:
                    logger.info("Retrying with CPU...")
                    self.classifier = await loop.run_in_executor(
                        None,
                        lambda: pipeline(
                            "zero-shot-classification",
                            model=self.model_name,
                            framework="pt",
                            device=-1
                        )
                    )
                    logger.info("AI model loaded successfully on CPU (fallback)")
                else:
                    raise
    
    def get_classifier(self):
        """Get the cached classifier."""
        return self.classifier
    

class VibeExtractor:
    def __init__(self):
        """
        Initializes the zero-shot classifier (lazy loaded).
        The model 'distilbart-mnli-12-1' is excellent for semantic classification.
        """
        self.classifier = None
        self.threshold = 0.3  # Lower threshold to be more inclusive (from 0.4)
        self.candidate_labels = [
            "casual", "elegant", "party", "date night", 
            "90s", "minimalist", "sporty", "grunge", "vintage"
        ]
    
    async def _ensure_loaded(self):
        """Ensure the model is loaded before use."""
        if self.classifier is None:
            cache = await ModelCache.get_instance()
            self.classifier = cache.get_classifier()
            if self.classifier is None:
                raise RuntimeError("Failed to load classifier from cache")

    async def extract_vibes(self, name: str, description: str = "") -> List[str]:
        """Extract vibe tags using semantic AI classification."""
        try:
            await self._ensure_loaded()
        except Exception as e:
            logger.error(f"Failed to load classifier: {e}")
            return []
        
        # Combine name and description for context
        full_text = f"{name} {description}".strip()
        
        if not full_text:
            logger.debug(f"Empty product text for name='{name}', description='{description}'")
            return []

        try:
            # Perform classification
            # multi_label=True allows the model to pick multiple tags (e.g., both '90s' and 'grunge')
            result = self.classifier(
                full_text, 
                self.candidate_labels, 
                multi_label=True
            )

            # result['labels'] and result['scores'] are returned in matching order
            # We zip them together and filter by the confidence threshold
            extracted_tags = [
                label for label, score in zip(result['labels'], result['scores'])
                if score >= self.threshold
            ]
            
            if extracted_tags:
                logger.debug(f"Extracted vibes for '{name}': {[(tag, score) for tag, score in zip(result['labels'], result['scores']) if tag in extracted_tags]}")
            else:
                logger.debug(f"No vibes above threshold {self.threshold} for '{name}'")

            return extracted_tags
        except Exception as e:
            logger.error(f"Error extracting vibes for '{name}': {e}", exc_info=True)
            return []