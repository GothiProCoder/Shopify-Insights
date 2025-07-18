from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional

# --- Input Model (What our API will accept) ---

class StoreRequest(BaseModel):
    website_url: HttpUrl # Pydantic automatically validates that this is a proper URL

# --- Output Models (The structure of our final JSON response) ---

class Product(BaseModel):
    id: int
    title: str
    vendor: str
    product_type: str
    handle: str # The URL-friendly version of the product title
    created_at: str
    price: float # We'll parse this from the product's variants
    sku: Optional[str] = None
    image_url: Optional[HttpUrl] = None
    
class Policy(BaseModel):
    url: Optional[HttpUrl] = None
    content: Optional[str] = None

class ContactDetails(BaseModel):
    emails: List[str] = []
    phone_numbers: List[str] = []

class BrandInsights(BaseModel):
    store_url: HttpUrl
    product_catalog: List[Product] = []
    hero_products: List[str] = [] # Can be product titles or handles
    policies: Dict[str, Policy] = {} # e.g., {"Privacy Policy": "url", ...}
    faqs: List[Dict[str, str]] = [] # e.g., [{"question": "...", "answer": "..."}]
    social_handles: Dict[str, Optional[HttpUrl]] = {} # e.g., {"instagram": "url", ...}
    contact_details: ContactDetails
    brand_context: Optional[str] = None # "About Us" text
    important_links: Dict[str, Optional[HttpUrl]] = {} # e.g., {"Order Tracking": "url", ...}