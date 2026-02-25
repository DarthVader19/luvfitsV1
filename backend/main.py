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
from logic.outfit_builder import outfit_matcher
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
    Search for outfits by vibe query using semantic embeddings.
    
    Args:
        request: SearchRequest with query and optional parameters
        
    Returns:
        List of matching outfits
    """
    try:
        logger.info(f"Search query: {request.query}")

        # Get outfits matching the vibe
        all_outfits = await mongodb_client.get_all_outfits(limit=request.limit)

        # Filter by vibe if specified
        if request.include_vibes:
            # Simple vibe-based filtering
            filtered = [
                o for o in all_outfits
                if any(
                    vibe.lower() in request.query.lower()
                    or request.query.lower() in vibe.lower()
                    for vibe in o.vibes
                )
            ]
            results = filtered[:request.limit]
        else:
            results = all_outfits[:request.limit]

        return {
            "status": "success",
            "query": request.query,
            "results": results,
            "count": len(results),
        }

    except Exception as e:
        logger.error(f"Search error: {e}")
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


# ============================================================================
# Outfit Endpoints
# ============================================================================


@app.get("/outfits", tags=["Outfits"])
async def get_outfits(
    vibe: str = Query(None, description="Filter by vibe"),
    limit: int = Query(10, ge=1, le=50),
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

        return {
            "status": "success",
            "vibe": vibe,
            "outfits": outfits,
            "count": len(outfits),
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

        return {
            "status": "success",
            "outfit": outfit,
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
    Trigger on-demand data refresh: scrape, embed, and generate outfits.
    
    Returns:
        Refresh status and results
    """
    try:
        logger.info("On-demand refresh triggered via API")

        # Use the refresh worker
        await mongodb_client.connect()

        try:
            from scrapers.scraper_manager import ScraperManager

            manager = ScraperManager()
            results = await manager.refresh_all_data()

            # Generate outfits
            outfits = await outfit_matcher.create_outfits(num_outfits=50)
            await outfit_matcher.save_outfits(outfits)

            stats = await mongodb_client.get_stats()

            return RefreshResponse(
                status="success",
                message="Data refresh completed successfully",
                products_total=stats.get("total_products", 0),
                outfits_generated=len(outfits),
            )

        finally:
            await mongodb_client.disconnect()

    except Exception as e:
        logger.error(f"Refresh error: {e}")
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