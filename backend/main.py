"""
Luvfits Backend API - Async FastAPI application
Provides RESTful endpoints for vibe-based outfit search and management
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from database.db import mongodb_client
from database.models import (
    SearchRequest,
    RefreshResponse,
)
from logic.embedding_search import embedding_service
from logic.outfit_builder import outfit_builder
from logic.search_logic import search_outfits as search_outfits_ai
from logic.outfit_matcher import search_outfits_async
from scripts.refresh_worker import (
    refresh_worker,
    start_refresh_worker,
    stop_refresh_worker,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app lifecycle: startup and shutdown."""
    # Startup
    logger.info("Starting Luvfits API...")
    await mongodb_client.connect()
    start_refresh_worker()
    logger.info("API started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Luvfits API...")
    stop_refresh_worker()
    await mongodb_client.disconnect()
    logger.info("API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Luvfits API",
    version="3.0",
    description="Vibe-based outfit recommendation engine",
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health & Status Endpoints
# ============================================================================


@app.get("/", tags=["Health"])
async def root():
    """Root health check endpoint."""
    return {
        "message": "Luvfits Backend API v3.0",
        "status": "running",
        "version": "3.0",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health status."""
    try:
        stats = await mongodb_client.get_stats()
        return {
            "status": "healthy",
            "database": "connected",
            "products": stats.get("total_products", 0),
            "outfits": stats.get("total_outfits", 0),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")


# ============================================================================
# Search Endpoints
# ============================================================================


@app.post("/search", tags=["Search"])
async def search_outfits(request: SearchRequest):
    """
    Search for outfits by vibe query.
    
    Args:
        request: SearchRequest with query and optional parameters
        
    Returns:
        List of matching outfits
    """
    try:
        logger.info(f"Search query: {request.query}")
        query_lower = request.query.lower()

        # Get all outfits from database
        all_outfits = await mongodb_client.get_all_outfits(limit=500)
        logger.info(f"Total outfits in database: {len(all_outfits)}")
        
        # Filter outfits by matching query with vibes
        if request.include_vibes and request.query.strip():
            # Match outfits where query matches any vibe
            filtered = []
            for outfit in all_outfits:
                # Check if query matches any vibe tag in the outfit
                matching_vibes = [
                    vibe for vibe in outfit.vibes
                    if query_lower in vibe.lower() or vibe.lower() in query_lower
                ]
                if matching_vibes:
                    filtered.append(outfit)
            
            results = filtered[:request.limit]
            logger.info(f"Found {len(results)} outfits matching '{request.query}'")
        else:
            results = all_outfits[:request.limit]
        
        # Serialize outfits properly
        serialized_results = [
            {
                "id": outfit.id,
                "top_id": outfit.top_id,
                "bottom_id": outfit.bottom_id,
                "shoe_id": outfit.shoe_id,
                "accessory_id": outfit.accessory_id,
                "vibes": outfit.vibes,
                "compatibility_score": outfit.compatibility_score,
                "color_harmony": outfit.color_harmony,
                "total_price": outfit.total_price,
                "created_at": outfit.created_at.isoformat() if hasattr(outfit.created_at, 'isoformat') else str(outfit.created_at),
            }
            for outfit in results
        ]

        return {
            "status": "success",
            "query": request.query,
            "results": serialized_results,
            "count": len(serialized_results),
        }

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# add a oufit search using embeddings of query and vibes of outfits
@app.post("/search/similar", tags=["Search"])
async def search_outfits_embedding(request: SearchRequest):
    """
    Search for outfits using embeddings.
    
    Args:
        request: SearchRequest with query and optional parameters
        
    Returns:
        List of matching outfits
    """
    try:
        logger.info(f"Embedding similarity search query: {request.query}")

        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        matches = await embedding_service.search_outfits_by_query(
            query=request.query,
            limit=request.limit,
        )

        serialized_results = [
            {
                "id": match["outfit"].id,
                "top_id": match["outfit"].top_id,
                "bottom_id": match["outfit"].bottom_id,
                "shoe_id": match["outfit"].shoe_id,
                "accessory_id": match["outfit"].accessory_id,
                "vibes": match["outfit"].vibes,
                "compatibility_score": match["outfit"].compatibility_score,
                "color_harmony": match["outfit"].color_harmony,
                "total_price": match["outfit"].total_price,
                "similarity_score": match["similarity"],
                "created_at": (
                    match["outfit"].created_at.isoformat()
                    if hasattr(match["outfit"].created_at, "isoformat")
                    else str(match["outfit"].created_at)
                ),
            }
            for match in matches
        ]

        return {
            "status": "success",
            "query": request.query,
            "results": serialized_results,
            "count": len(serialized_results),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Embedding similarity search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search/products", tags=["Search"])
async def search_products(
    query: str = Query(..., description="Product search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    category: str = Query(None, description="Filter by category"),
):
    """
    Search products by keyword and optional category.
    
    Args:
        query: Search term
        limit: Max results
        category: Optional category filter
        
    Returns:
        List of matching products
    """
    try:
        # Get products
        all_products = await mongodb_client.get_all_products(limit=limit * 2)

        # Filter by query
        query_lower = query.lower()
        filtered = [
            p for p in all_products
            if query_lower in p.name.lower()
            or query_lower in p.description.lower()
        ]

        # Filter by category if specified
        if category:
            filtered = [p for p in filtered if p.category == category]

        return {
            "status": "success",
            "query": query,
            "category": category,
            "results": filtered[:limit],
            "count": len(filtered[:limit]),
        }

    except Exception as e:
        logger.error(f"Product search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products", tags=["Products"])
async def get_products(
    category: str = Query(None, description="Filter by category (Tops, Bottoms, Shoes, Accessories)"),
    site: str = Query(None, description="Filter by site (amazon, h&m, nordstrom)"),
    limit: int = Query(50, ge=1, le=400, description="Max results"),
):
    """
    Get all products, optionally filtered by category or site.
    
    Args:
        category: Optional category filter
        site: Optional site filter
        limit: Max results
        
    Returns:
        List of products
    """
    try:
        # Get all products
        all_products = await mongodb_client.get_all_products(limit=limit)
        
        # Filter by category if specified
        if category:
            all_products = [p for p in all_products if p.category == category]
        
        # Filter by site if specified
        if site:
            all_products = [p for p in all_products if p.site.lower() == site.lower()]
        
        # Convert to dict for JSON response
        products_list = [
            {
                "id": str(p.id) if hasattr(p, 'id') else p.get("_id"),
                "name": p.name if hasattr(p, 'name') else p.get("name"),
                "category": p.category if hasattr(p, 'category') else p.get("category"),
                "site": p.site if hasattr(p, 'site') else p.get("site"),
                "price": p.price if hasattr(p, 'price') else p.get("price"),
                "product_url": p.product_url if hasattr(p, 'product_url') else p.get("product_url"),
                "image_url": p.image_url if hasattr(p, 'image_url') else p.get("image_url"),
                "description": p.description if hasattr(p, 'description') else p.get("description"),
                "tags": p.tags if hasattr(p, 'tags') else p.get("tags"),
            }
            for p in all_products
        ]
        
        return {
            "status": "success",
            "category": category,
            "site": site,
            "results": products_list,
            "count": len(products_list),
        }

    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/outfit", tags=["Search"])
async def search_outfit_ai(request: SearchRequest):
    """
    Generate an outfit using AI-powered tag extraction.
    
    Uses the BART model to extract vibes from the query, then finds products
    with matching tags and builds the best outfit combination.
    
    Args:
        request: SearchRequest with query and optional parameters
        
    Returns:
        Generated outfit with top, bottom, shoes, and accessory
    """
    try:
        logger.info(f"AI outfit search query: '{request.query}'")
        
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Use AI-powered search to generate outfit
        outfit = await search_outfits_ai(request.query)
        
        # Parse the outfit response
        if outfit:
            return {
                "status": "success",
                "query": request.query,
                "outfit": {
                    "top": outfit.get("top"),
                    "bottom": outfit.get("bottom"),
                    "accessory": outfit.get("accessory"),
                    "shoe": outfit.get("shoe"),
                    "compatibility_score": outfit.get("compatibility_score", 0.0),
                    "matched_tags": outfit.get("matched_tags", []),
                },
            }
        else:
            raise HTTPException(status_code=404, detail="Could not generate outfit for this query")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI outfit search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/search/outfit/matcher", tags=["Search"])
async def search_outfit_matcher(request: SearchRequest):
    """
    Generate an outfit using the OutfitMatcher with AI tag extraction.
    
    Alternative implementation using OutfitMatcher class.
    
    Args:
        request: SearchRequest with query and optional parameters
        
    Returns:
        Generated outfit with matching tags
    """
    try:
        logger.info(f"OutfitMatcher query: '{request.query}'")
        
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Use OutfitMatcher
        outfit = await search_outfits_async(request.query)
        
        if outfit and any(outfit.values()):
            return {
                "status": "success",
                "query": request.query,
                "outfit": outfit,
            }
        else:
            raise HTTPException(status_code=404, detail="Could not generate outfit for this query")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OutfitMatcher search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ============================================================================
# Outfit Endpoints
# ============================================================================


@app.get("/outfits", tags=["Outfits"])
async def get_outfits(
    vibe: str = Query(None, description="Filter by vibe"),
    limit: int = Query(10, ge=1, le=200),
):
    """
    Get all outfits, optionally filtered by vibe.
    
    Args:
        vibe: Optional vibe to filter by
        limit: Max results
        
    Returns:
        List of outfits
    """
    try:
        if vibe:
            outfits = await mongodb_client.get_outfits_by_vibe(
                vibe.lower(), limit
            )
        else:
            outfits = await mongodb_client.get_all_outfits(limit=limit)
        
        # Ensure outfits are properly serialized
        outfit_list = [
            {
                "id": outfit.id,
                "top_id": outfit.top_id,
                "bottom_id": outfit.bottom_id,
                "shoe_id": outfit.shoe_id,
                "accessory_id": outfit.accessory_id,
                "vibes": outfit.vibes,
                "compatibility_score": outfit.compatibility_score,
                "color_harmony": outfit.color_harmony,
                "total_price": outfit.total_price,
                "created_at": outfit.created_at.isoformat() if hasattr(outfit.created_at, 'isoformat') else str(outfit.created_at),
            }
            for outfit in outfits
        ]
            
        return {
            "status": "success",
            "vibe": vibe,
            "outfits": outfit_list,
            "count": len(outfit_list),
        }

    except Exception as e:
        logger.error(f"Error fetching outfits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/outfits/{outfit_id}", tags=["Outfits"])
async def get_outfit_detail(outfit_id: str):
    """Get detailed outfit information."""
    try:
        # Get outfit
        all_outfits = await mongodb_client.get_all_outfits(limit=1000)
        outfit = next((o for o in all_outfits if o.id == outfit_id), None)

        if not outfit:
            raise HTTPException(status_code=404, detail="Outfit not found")

        # Get component products
        top = await mongodb_client.get_product(outfit.top_id)
        bottom = await mongodb_client.get_product(outfit.bottom_id)
        shoes = await mongodb_client.get_product(outfit.shoe_id)
        accessory = await mongodb_client.get_product(outfit.accessory_id)

        # Serialize outfit properly
        outfit_data = {
            "id": outfit.id,
            "top_id": outfit.top_id,
            "bottom_id": outfit.bottom_id,
            "shoe_id": outfit.shoe_id,
            "accessory_id": outfit.accessory_id,
            "vibes": outfit.vibes,
            "compatibility_score": outfit.compatibility_score,
            "color_harmony": outfit.color_harmony,
            "total_price": outfit.total_price,
            "created_at": outfit.created_at.isoformat() if hasattr(outfit.created_at, 'isoformat') else str(outfit.created_at),
        }

        return {
            "status": "success",
            "outfit": outfit_data,
            "products": {
                "top": top,
                "bottom": bottom,
                "shoes": shoes,
                "accessory": accessory,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching outfit detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Data Management Endpoints
# ============================================================================


@app.post("/refresh", tags=["Data Management"])
async def trigger_refresh():
    """
    Trigger on-demand data refresh: scrape and generate outfits.
    
    Returns:
        Refresh status and results
    """
    try:
        logger.info("On-demand refresh triggered via API")

        from scrapers.scraper_manager import ScraperManager

        manager = ScraperManager()
        results = await manager.refresh_all_data()

        # Get updated stats
        await mongodb_client.connect()
        try:
            stats = await mongodb_client.get_stats()
        finally:
            await mongodb_client.disconnect()

        return RefreshResponse(
            status="success",
            message="Data refresh completed successfully",
            products_total=stats.get("total_products", 0),
            outfits_generated=results.get("outfits_generated", 0),
        )

    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embeddings/backfill", tags=["Data Management"])
async def backfill_embeddings():
    """Backfill missing embeddings for existing products and outfits."""
    try:
        logger.info("Embedding backfill triggered via API")
        results = await embedding_service.backfill_embeddings()

        return {
            "status": "success",
            "message": "Embedding backfill completed",
            "results": results,
        }
    except Exception as e:
        logger.error(f"Embedding backfill error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", tags=["Data Management"])
async def get_statistics():
    """
    Get database statistics.
    
    Returns:
        Stats on products, categories, sites, and outfits
    """
    try:
        stats = await mongodb_client.get_stats()

        return {
            "status": "success",
            "statistics": {
                "total_products": stats.get("total_products", 0),
                "total_outfits": await mongodb_client.count_outfits(),
                "by_category": stats.get("categories", {}),
                "by_site": stats.get("sites", {}),
            },
        }

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/worker/status", tags=["Data Management"])
def get_worker_status():
    """Get background refresh worker status."""
    return refresh_worker.get_status()


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return {
        "status": "error",
        "detail": exc.detail,
        "status_code": exc.status_code,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
