from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.database import Base

class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    store_url = Column(String(255), unique=True, index=True, nullable=False)
    brand_name = Column(String(255), index=True)
    brand_context = Column(Text, nullable=True)
    
    # Store dictionaries as JSON for simplicity
    policies = Column(JSON)
    social_handles = Column(JSON)
    important_links = Column(JSON)
    contact_emails = Column(JSON)
    contact_phones = Column(JSON)
    faqs = Column(JSON, nullable=True)
    
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    # This creates the one-to-many relationship
    products = relationship("Product", back_populates="brand")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id")) # Foreign key to the brands table
    
    shopify_product_id = Column(Integer, unique=True)
    title = Column(String(255), nullable=False)
    vendor = Column(String(255))
    product_type = Column(String(255))
    price = Column(Float)
    sku = Column(String(100), nullable=True)
    image_url = Column(String(512), nullable=True)

    # This creates the link back to the Brand object
    brand = relationship("Brand", back_populates="products")