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
            if product.embedding:
                continue

            # Create embedding text from product metadata
            embedding_text = (
                f"{product.name} {product.description} "
                f"{product.category} {product.color} {' '.join(product.tags)}"
            )

            embedding = self.generate_embedding(embedding_text)

            if embedding:
                product.embedding = embedding
                if product.id:
                    await mongodb_client.update_product(
                        product.id,
                        {"embedding": embedding},
                    )
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

    async def search_outfits_by_query(
        self, query: str, limit: int = 10, min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search outfits by query embedding similarity.

        Returns:
            List of dicts with keys: outfit, similarity
        """
        if not self.model or not query.strip():
            return []

        query_embedding = self.generate_embedding(query)
        if not query_embedding:
            return []

        all_outfits = await mongodb_client.get_all_outfits(limit=1000)
        scored_outfits = []

        for outfit in all_outfits:
            outfit_embedding = outfit.embedding

            # Fallback for outfits without persisted embeddings.
            if not outfit_embedding and outfit.vibes:
                outfit_embedding = self.generate_embedding(" ".join(outfit.vibes))

            if not outfit_embedding:
                continue

            similarity = float(
                self.cosine_similarity(query_embedding, outfit_embedding)
            )
            if similarity >= min_similarity:
                scored_outfits.append(
                    {
                        "outfit": outfit,
                        "similarity": similarity,
                    }
                )

        scored_outfits.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_outfits[:limit]

    async def backfill_embeddings(self) -> Dict[str, int]:
        """Backfill missing embeddings for products, fallback products, and outfits."""
        if not self.model:
            logger.error("Embedding model not available for backfill")
            return {
                "products_updated": 0,
                "fallback_products_updated": 0,
                "outfits_updated": 0,
            }

        products_updated = 0
        fallback_updated = 0
        outfits_updated = 0
        batch_size = 200

        all_products: List[Product] = []
        all_fallback_products: List[Product] = []

        # Backfill products embeddings
        skip = 0
        while True:
            batch = await mongodb_client.get_all_products(skip=skip, limit=batch_size)
            if not batch:
                break
            all_products.extend(batch)

            for product in batch:
                if product.embedding or not product.id:
                    continue
                embedding_text = (
                    f"{product.name} {product.description} "
                    f"{product.category} {product.color} {' '.join(product.tags)}"
                ).strip()
                embedding = self.generate_embedding(embedding_text)
                if not embedding:
                    continue
                updated = await mongodb_client.update_product(
                    product.id,
                    {"embedding": embedding},
                )
                if updated:
                    product.embedding = embedding
                    products_updated += 1

            skip += batch_size

        # Backfill fallback product embeddings
        skip = 0
        while True:
            batch = await mongodb_client.get_all_fallback_products(
                skip=skip, limit=batch_size
            )
            if not batch:
                break
            all_fallback_products.extend(batch)

            for product in batch:
                if product.embedding or not product.id:
                    continue
                embedding_text = (
                    f"{product.name} {product.description} "
                    f"{product.category} {product.color} {' '.join(product.tags)}"
                ).strip()
                embedding = self.generate_embedding(embedding_text)
                if not embedding:
                    continue
                updated = await mongodb_client.update_fallback_product(
                    product.id,
                    {"embedding": embedding},
                )
                if updated:
                    product.embedding = embedding
                    fallback_updated += 1

            skip += batch_size

        # Build product map for outfit embedding generation
        products_map: Dict[str, Product] = {}
        for product in all_products + all_fallback_products:
            if product.id:
                products_map[product.id] = product

        # Backfill outfit embeddings
        skip = 0
        while True:
            outfits_batch = await mongodb_client.get_all_outfits(
                skip=skip, limit=batch_size
            )
            if not outfits_batch:
                break

            for outfit in outfits_batch:
                if outfit.embedding or not outfit.id:
                    continue
                embedding = await self.generate_outfit_embedding(outfit, products_map)
                if not embedding:
                    continue
                updated = await mongodb_client.update_outfit(
                    outfit.id,
                    {"embedding": embedding},
                )
                if updated:
                    outfits_updated += 1

            skip += batch_size

        return {
            "products_updated": products_updated,
            "fallback_products_updated": fallback_updated,
            "outfits_updated": outfits_updated,
        }


# Global embedding service instance
embedding_service = EmbeddingService()
