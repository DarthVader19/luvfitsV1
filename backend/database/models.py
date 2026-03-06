"""
MongoDB models using Pydantic for type safety and validation.
"""
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId


class Product(BaseModel):
    """Product model for MongoDB storage."""
    id: Optional[str] = Field(None, alias="_id")
    name: str
    price: float
    currency: str = "USD"
    color: str
    color_family: str  # neutral, warm, cool, primary
    description: str
    image_url: str
    product_url: str  # Unique constraint handled by MongoDB
    category: str  # From Google taxonomy
    subcategory: Optional[str] = None
    site: str  # H&M, Amazon, Nordstrom
    tags: List[str] = []  # Vibes: casual, party, elegant, etc.
    style_score: float = Field(default=0.5, ge=0, le=1)  # Likeability score
    embedding: Optional[List[float]] = None  # Vector embedding for vibe search
    available: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("id", mode="before")
    @classmethod
    def convert_id_to_string(cls, v: Any) -> Optional[str]:
        """Convert ObjectId to string."""
        if v is None:
            return None
        if isinstance(v, ObjectId):
            return str(v)
        return v

    class Config:
        populate_by_name = True


class Outfit(BaseModel):
    """Bundled outfit containing 4 pieces."""
    id: Optional[str] = Field(None, alias="_id")
    top_id: str
    bottom_id: str
    shoe_id: str
    accessory_id: str
    vibes: List[str] = []  # e.g., ["casual", "90s", "date night"]
    compatibility_score: float = Field(default=0.0, ge=0, le=1)
    color_harmony: float = Field(default=0.0, ge=0, le=1)
    total_price: float = 0.0
    embedding: Optional[List[float]] = None  # Vector for outfit-level search
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("id", mode="before")
    @classmethod
    def convert_id_to_string(cls, v: Any) -> Optional[str]:
        """Convert ObjectId to string."""
        if v is None:
            return None
        if isinstance(v, ObjectId):
            return str(v)
        return v

    class Config:
        populate_by_name = True


class ScrapingJob(BaseModel):
    """Track scraping jobs and their status."""
    id: Optional[str] = Field(None, alias="_id")
    site: str
    status: str  # pending, running, completed, failed
    products_scraped: int = 0
    products_stored: int = 0
    errors: List[str] = []
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def convert_id_to_string(cls, v: Any) -> Optional[str]:
        """Convert ObjectId to string."""
        if v is None:
            return None
        if isinstance(v, ObjectId):
            return str(v)
        return v

    class Config:
        populate_by_name = True


class SearchQuery(BaseModel):
    """Store search queries for analytics."""
    id: Optional[str] = Field(None, alias="_id")
    query: str
    embedding: Optional[List[float]] = None
    results_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("id", mode="before")
    @classmethod
    def convert_id_to_string(cls, v: Any) -> Optional[str]:
        """Convert ObjectId to string."""
        if v is None:
            return None
        if isinstance(v, ObjectId):
            return str(v)
        return v

    class Config:
        populate_by_name = True


# Request/Response schemas for API


class ProductResponse(BaseModel):
    """Response model for product endpoints."""
    id: str = Field(alias="_id")
    name: str
    price: float
    currency: str
    color: str
    category: str
    subcategory: Optional[str]
    site: str
    image_url: str
    product_url: str
    tags: List[str]
    style_score: float
    available: bool

    class Config:
        populate_by_name = True


class OutfitResponse(BaseModel):
    """Response model for outfit endpoints."""
    id: str = Field(alias="_id")
    top: ProductResponse
    bottom: ProductResponse
    shoes: ProductResponse
    accessory: ProductResponse
    vibes: List[str]
    compatibility_score: float
    color_harmony: float
    total_price: float

    class Config:
        populate_by_name = True


class SearchRequest(BaseModel):
    """Request body for search endpoint."""
    query: str
    limit: int = 10
    include_vibes: bool = True


class RefreshResponse(BaseModel):
    """Response from refresh endpoint."""
    status: str
    message: str
    products_total: int = 0
    outfits_generated: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)