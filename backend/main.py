from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from database.models import init_db
from logic.outfit_matcher import OutfitMatcher
from scrapers.scraper_manager import ScraperManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Luvfits API", version="2.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    logger.info("Database initialized")

@app.get("/")
def read_root():
    """Health check endpoint"""
    return {
        "message": "Luvfits Backend API v2.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    """Health status endpoint"""
    return {"status": "healthy"}

@app.get("/outfits")
def get_outfits(query: str = "casual"):
    """
    Search for outfits based on vibe/query
    
    Args:
        query: Vibe to search for (e.g., "Date Night", "casual", "90s")
    
    Returns:
        Outfit with top, bottom, accessory, shoe and compatibility score
    """
    try:
        matcher = OutfitMatcher()
        outfit = matcher.search_outfits(query)
        matcher.close()
        return {
            "success": True,
            "query": query,
            "outfit": outfit
        }
    except Exception as e:
        logger.error(f"Error searching outfits: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/refresh")
def refresh_data():
    """
    Trigger complete data refresh from all sources
    This will scrape H&M, Amazon, and Nordstrom
    """
    try:
        manager = ScraperManager()
        results = manager.refresh_all_data()
        return {
            "success": True,
            "message": "Data refresh completed",
            "results": results
        }
    except Exception as e:
        logger.error(f"Error during refresh: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/stats")
def get_statistics():
    """Get database statistics"""
    try:
        from database.models import SessionLocal, Product
        session = SessionLocal()
        
        stats = {
            "total_products": session.query(Product).count(),
            "by_category": {},
            "by_site": {},
            "by_color_family": {}
        }
        
        # Group by category
        for category in ["Tops", "Bottoms", "Accessories", "Shoes"]:
            count = session.query(Product).filter(Product.category == category).count()
            stats["by_category"][category] = count
        
        # Group by site
        for site in ["H&M", "Amazon", "Nordstrom"]:
            count = session.query(Product).filter(Product.site == site).count()
            stats["by_site"][site] = count
        
        # Group by color family
        color_families = session.query(Product.color_family).distinct().all()
        for (color_family,) in color_families:
            count = session.query(Product).filter(Product.color_family == color_family).count()
            stats["by_color_family"][color_family] = count
        
        session.close()
        return {"success": True, "statistics": stats}
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return {"success": False, "error": str(e)}