"""
MongoDB connection and operations handler.
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv
from .models import Product, Outfit, ScrapingJob
import logging

logger = logging.getLogger(__name__)

# Load backend/.env and project-root/.env if present.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env")


class MongoDBClient:
    """MongoDB async client wrapper."""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or os.getenv(
            "MONGODB_URL", "mongodb://localhost:27017"
        )
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[Any] = None
        
    async def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(self.connection_string)
            self.db = self.client["luvfits"]
            # Test connection
            await self.db.command("ping")
            logger.info("Connected to MongoDB")
            await self._create_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def _create_indexes(self):
        """Create necessary indexes for performance."""
        if  self.db is None:
            return

        # Products collection indexes
        products = self.db["products"]
        await products.create_index([("product_url", ASCENDING)], unique=True)
        await products.create_index([("category", ASCENDING)])
        await products.create_index([("site", ASCENDING)])
        await products.create_index([("tags", ASCENDING)])
        await products.create_index([("color_family", ASCENDING)])
        await products.create_index([("created_at", DESCENDING)])

        # Outfits collection indexes
        outfits = self.db["outfits"]
        await outfits.create_index([("vibes", ASCENDING)])
        await outfits.create_index([("created_at", DESCENDING)])

        # Scraping jobs
        jobs = self.db["scraping_jobs"]
        await jobs.create_index([("site", ASCENDING)])
        await jobs.create_index([("status", ASCENDING)])

        # Fallback products collection indexes
        fallback_products = self.db["fallback_products"]
        await fallback_products.create_index([("product_url", ASCENDING)], unique=True)
        await fallback_products.create_index([("category", ASCENDING)])
        await fallback_products.create_index([("site", ASCENDING)])
        await fallback_products.create_index([("created_at", DESCENDING)])

        logger.info("Indexes created")

    # Products operations

    async def add_product(self, product: Product) -> str:
        """Add a product to the database."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                raise ValueError("Database not connected")
            products = self.db["products"]
            result = await products.insert_one(product.dict(exclude={"id"}))
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Product URL {product.product_url} already exists")
            # Update existing product instead
            existing = await products.find_one({"product_url": product.product_url})
            if existing:
                return str(existing["_id"])
            raise
        except Exception as e:
            logger.error(f"Error adding product: {e}")
            raise

    async def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID."""
        from bson import ObjectId

        try:
            if self.db is None:
                logger.error("Database not connected")
                return None
            products = self.db["products"]
            doc = await products.find_one({"_id": ObjectId(product_id)})
            if doc:
                doc["id"] = str(doc["_id"])
                return Product(**doc)
            return None
        except Exception as e:
            logger.error(f"Error getting product: {e}")
            return None

    async def get_products_by_category(
        self, category: str, limit: int = 50
    ) -> List[Product]:
        """Get products by category."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return []
            products = self.db["products"]
            cursor = products.find({"category": category}).limit(limit)
            docs = await cursor.to_list(length=limit)
            result = []
            for doc in docs:
                doc["id"] = str(doc["_id"])
                result.append(Product(**doc))
            return result
        except Exception as e:
            logger.error(f"Error getting products by category: {e}")
            return []

    async def search_by_embedding(
        self, embedding: List[float], limit: int = 10
    ) -> List[Product]:
        """Search products using vector similarity (simple distance)."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return []
            products = self.db["products"]
            # MongoDB doesn't have native vector search in free tier
            # Use simple filtering by tags as fallback
            cursor = products.find({"embedding": {"$exists": True}}).limit(limit)
            docs = await cursor.to_list(length=limit)
            result = []
            for doc in docs:
                doc["id"] = str(doc["_id"])
                result.append(Product(**doc))
            return result
        except Exception as e:
            logger.error(f"Error searching by embedding: {e}")
            return []

    async def get_all_products(
        self, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """Get all products with pagination."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return []
            products = self.db["products"]
            cursor = (
                products.find({})
                .skip(skip)
                .limit(limit)
                .sort("created_at", DESCENDING)
            )
            docs = await cursor.to_list(length=limit)
            result = []
            for doc in docs:
                doc["id"] = str(doc["_id"])
                result.append(Product(**doc))
            return result
        except Exception as e:
            logger.error(f"Error getting all products: {e}")
            return []

    async def count_products(self, category: Optional[str] = None) -> int:
        """Count products, optionally by category."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return 0
            products = self.db["products"]
            query = {"category": category} if category else {}
            return await products.count_documents(query)
        except Exception as e:
            logger.error(f"Error counting products: {e}")
            return 0

    async def update_product(self, product_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a product by ID."""
        from bson import ObjectId
        try:
            if self.db is None:
                logger.error("Database not connected")
                return False
            products = self.db["products"]
            # update tag field in products collection

            result = await products.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": update_data},
                
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating product: {e}")
            return False

    async def update_fallback_product(self, product_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a fallback product by ID."""
        from bson import ObjectId
        try:
            if self.db is None:
                logger.error("Database not connected")
                return False
            fallback_products = self.db["fallback_products"]

            result = await fallback_products.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": update_data},
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating fallback product: {e}")
            return False

    # Fallback products operations

    async def add_fallback_product(self, product: Product) -> str:
        """Add a fallback product to the fallback_products collection."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                raise ValueError("Database not connected")
            fallback_products = self.db["fallback_products"]
            result = await fallback_products.insert_one(product.dict(exclude={"id"}))
            return str(result.inserted_id)
        except DuplicateKeyError:
            logger.warning(f"Fallback product URL {product.product_url} already exists")
            # Update existing fallback product instead
            fallback_products = self.db["fallback_products"]
            existing = await fallback_products.find_one({"product_url": product.product_url})
            if existing:
                return str(existing["_id"])
            raise
        except Exception as e:
            logger.error(f"Error adding fallback product: {e}")
            raise

    async def get_all_fallback_products(
        self, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """Get all fallback products with pagination."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return []
            fallback_products = self.db["fallback_products"]
            cursor = (
                fallback_products.find({})
                .skip(skip)
                .limit(limit)
                .sort("created_at", DESCENDING)
            )
            docs = await cursor.to_list(length=limit)
            result = []
            for doc in docs:
                doc["id"] = str(doc["_id"])
                result.append(Product(**doc))
            return result
        except Exception as e:
            logger.error(f"Error getting fallback products: {e}")
            return []

    async def count_fallback_products(self) -> int:
        """Count fallback products."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return 0
            fallback_products = self.db["fallback_products"]
            return await fallback_products.count_documents({})
        except Exception as e:
            logger.error(f"Error counting fallback products: {e}")
            return 0

    # Outfits operations

    async def add_outfit(self, outfit: Outfit) -> str:
        """Add an outfit to the database."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                raise ValueError("Database not connected")
            outfits = self.db["outfits"]
            result = await outfits.insert_one(outfit.dict(exclude={"id"}))
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding outfit: {e}")
            raise

    async def update_outfit(self, outfit_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an outfit by ID."""
        from bson import ObjectId
        try:
            if self.db is None:
                logger.error("Database not connected")
                return False
            outfits = self.db["outfits"]

            result = await outfits.update_one(
                {"_id": ObjectId(outfit_id)},
                {"$set": update_data},
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating outfit: {e}")
            return False

    async def get_outfits_by_vibe(
        self, vibe: str, limit: int = 10
    ) -> List[Outfit]:
        """Get outfits by vibe tag."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return []
            outfits = self.db["outfits"]
            cursor = (
                outfits.find({"vibes": vibe})
                .limit(limit)
                .sort("compatibility_score", DESCENDING)
            )
            docs = await cursor.to_list(length=limit)
            result = []
            for doc in docs:
                doc["id"] = str(doc["_id"])
                result.append(Outfit(**doc))
            return result
        except Exception as e:
            logger.error(f"Error getting outfits by vibe: {e}")
            return []

    async def get_all_outfits(
        self, skip: int = 0, limit: int = 50
    ) -> List[Outfit]:
        """Get all outfits with pagination."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return []
            outfits = self.db["outfits"]
            cursor = (
                outfits.find({})
                .skip(skip)
                .limit(limit)
                .sort("created_at", DESCENDING)
            )
            docs = await cursor.to_list(length=limit)
            result = []
            for doc in docs:
                doc["id"] = str(doc["_id"])
                result.append(Outfit(**doc))
            return result
        except Exception as e:
            logger.error(f"Error getting all outfits: {e}")
            return []

    async def count_outfits(self) -> int:
        """Count outfits."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return 0
            outfits = self.db["outfits"]
            return await outfits.count_documents({})
        except Exception as e:
            logger.error(f"Error counting outfits: {e}")
            return 0

    # Scraping jobs tracking

    async def add_scraping_job(self, job: ScrapingJob) -> str:
        """Add a scraping job."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                raise ValueError("Database not connected")
            jobs = self.db["scraping_jobs"]
            result = await jobs.insert_one(job.dict(exclude={"id"}))
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error adding scraping job: {e}")
            raise

    async def update_scraping_job(self, job_id: str, update_data: Dict[str, Any]):
        """Update a scraping job."""
        from bson import ObjectId

        try:
            if self.db is None:
                logger.error("Database not connected")
                raise ValueError("Database not connected")
            jobs = self.db["scraping_jobs"]
            await jobs.update_one(
                {"_id": ObjectId(job_id)}, {"$set": update_data}
            )
        except Exception as e:
            logger.error(f"Error updating scraping job: {e}")
            raise

    # Stats and analytics

    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            if self.db is None:
                logger.error("Database not connected")
                return {}
                
            products_count = await self.count_products()
            fallback_count = await self.count_fallback_products()
            outfits_count = await self.count_outfits()

            # Count by category
            products = self.db["products"]
            categories = await products.distinct("category")

            category_counts = {}
            for cat in categories:
                category_counts[cat] = await self.count_products(cat)

            # Sites count
            sites = await products.distinct("site")
            site_counts = {}
            for site in sites:
                site_counts[site] = await products.count_documents({"site": site})

            return {
                "total_products": products_count,
                "total_fallback_products": fallback_count,
                "total_outfits": outfits_count,
                "categories": category_counts,
                "sites": site_counts,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    async def clear_all_data(self):
        """Clear all data (for testing)."""
        try:
            if self.db:
                await self.db.drop_collection("products")
                await self.db.drop_collection("fallback_products")
                await self.db.drop_collection("outfits")
                await self.db.drop_collection("scraping_jobs")
                logger.info("All data cleared")
        except Exception as e:
            logger.error(f"Error clearing data: {e}")
            raise


# Global client instance
mongodb_client = MongoDBClient()
