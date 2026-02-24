from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./luvfits.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    color = Column(String, index=True)
    description = Column(String)
    image_url = Column(String)
    product_url = Column(String, unique=True, index=True)
    category = Column(String, index=True)  # Tops, Bottoms, Accessories, Shoes
    site = Column(String, index=True)  # hm, amazon, nordstrom
    tags = Column(String)  # comma separated tags for vibes
    style_score = Column(Float, default=0.5)  # Likeability score 0-1
    color_family = Column(String)  # primary, neutral, warm, cool
    available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'color': self.color,
            'description': self.description,
            'image_url': self.image_url,
            'product_url': self.product_url,
            'category': self.category,
            'site': self.site,
            'tags': self.tags,
            'style_score': self.style_score,
            'color_family': self.color_family
        }

def init_db():
    Base.metadata.create_all(bind=engine)