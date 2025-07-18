from sqlalchemy.orm import Session
from app import db_models, models

def save_brand_insights(db: Session, insights: models.BrandInsights):
    """
    Saves the scraped BrandInsights data to the database.
    This function will update an existing brand or create a new one.
    """
    # Check if the brand already exists
    db_brand = db.query(db_models.Brand).filter(db_models.Brand.store_url == str(insights.store_url)).first()
    
    if not db_brand:
        # Create a new Brand record
        db_brand = db_models.Brand(store_url=str(insights.store_url))
        db.add(db_brand)
    
    # Update the brand's fields from the scraped insights
    db_brand.brand_name = insights.product_catalog[0].vendor if insights.product_catalog else "Unknown"
    db_brand.brand_context = insights.brand_context
    db_brand.policies = {name: policy.model_dump(mode='json') for name, policy in insights.policies.items()}
    db_brand.social_handles = {k: str(v) for k, v in insights.social_handles.items()}
    db_brand.important_links = {k: str(v) for k, v in insights.important_links.items()}
    db_brand.contact_emails = insights.contact_details.emails
    db_brand.contact_phones = insights.contact_details.phone_numbers
    db_brand.faqs = insights.faqs
    
    # Clear old products for this brand to avoid duplicates on re-scrape
    db.query(db_models.Product).filter(db_models.Product.brand_id == db_brand.id).delete()

    # Add the new products
    for product_pydantic in insights.product_catalog:
        db_product = db_models.Product(
            shopify_product_id=product_pydantic.id,
            title=product_pydantic.title,
            vendor=product_pydantic.vendor,
            product_type=product_pydantic.product_type,
            price=product_pydantic.price,
            sku=product_pydantic.sku,
            image_url=str(product_pydantic.image_url),
            brand=db_brand # This links the product to the brand
        )
        db.add(db_product)
        
    db.commit()
    db.refresh(db_brand)
    return db_brand