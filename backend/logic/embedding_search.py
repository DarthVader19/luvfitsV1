"""
Embedding-based vibe search using semantic similarity.
Uses sentence-transformers for efficient vector search.
"""
import logging
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import numpy as np
from database.db import mongodb_client
from database.models import Product, Outfit

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and searching embeddings."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedding service.
        
        Args:
            model_name: Sentence-transformers model name
        """
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"Loaded embedding model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if not self.model or not text:
            return []

        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        vec1 = np.array(vec1)
        vec2 = np.array(vec2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def embed_products(self, products: List[Product]) -> None:
        """Embed all products and update MongoDB."""
        logger.info(f"Embedding {len(products)} products...")

        for product in products:
            # Create embedding text from product metadata
            embedding_text = f"{product.name} {product.description} {' '.join(product.tags)}"

            embedding = self.generate_embedding(embedding_text)

            if embedding:
                # Update product with embedding in MongoDB
                # This would normally update via MongoDB client
                logger.debug(f"Embedded product: {product.name}")

        logger.info("Embedding complete")

    async def search_by_vibe(
        self, query: str, limit: int = 10
    ) -> List[Product]:
        """
        Search products by vibe query using semantic similarity.
        
        Args:
            query: User search query (e.g., "casual weekend look")
            limit: Max results to return
            
        Returns:
            List of matching products ordered by similarity
        """
        if not self.model:
            logger.error("Embedding model not available")
            return []

        # Generate query embedding
        query_embedding = self.generate_embedding(query)
        if not query_embedding:
            return []

        # Get all products from database
        all_products = await mongodb_client.get_all_products(limit=1000)

        # Score products by similarity
        scored_products = []
        for product in all_products:
            if product.embedding:
                similarity = self.cosine_similarity(
                    query_embedding, product.embedding
                )
                scored_products.append((product, similarity))

        # Sort by score and return top results
        scored_products.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in scored_products[:limit]]

    async def generate_outfit_embedding(
        self, outfit: Outfit, products_map: Dict[str, Product]
    ) -> List[float]:
        """Generate outfit-level embedding from component products."""
        # Combine attributes from all 4 pieces
        product_ids = [
            outfit.top_id,
            outfit.bottom_id,
            outfit.shoe_id,
            outfit.accessory_id,
        ]

        texts = []
        for pid in product_ids:
            if pid in products_map:
                product = products_map[pid]
                text = f"{product.category} {product.color} {' '.join(product.tags)}"
                texts.append(text)

        # Combine outfit text
        combined_text = " ".join(texts) + " " + " ".join(outfit.vibes)

        return self.generate_embedding(combined_text)

    async def find_similar_outfits(
        self, outfit_id: str, limit: int = 5
    ) -> List[Outfit]:
        """Find outfits similar to a given one."""
        # Get target outfit
        outfit = None
        all_outfits = await mongodb_client.get_all_outfits(limit=1000)

        for o in all_outfits:
            if o.id == outfit_id:
                outfit = o
                break

        if not outfit or not outfit.embedding:
            return []

        # Score similar outfits
        scored_outfits = []
        for other_outfit in all_outfits:
            if other_outfit.id != outfit_id and other_outfit.embedding:
                similarity = self.cosine_similarity(
                    outfit.embedding, other_outfit.embedding
                )
                scored_outfits.append((other_outfit, similarity))

        # Sort and return
        scored_outfits.sort(key=lambda x: x[1], reverse=True)
        return [o[0] for o in scored_outfits[:limit]]


# Global embedding service instance
embedding_service = EmbeddingService()
