from fastapi import FastAPI, HTTPException, Depends
from httpx import RequestError
from sqlalchemy.orm import Session

# Import everything we've just created
from app.models import StoreRequest, BrandInsights
from app.scraper import ShopifyScraper
from app.database import SessionLocal, engine
from app import crud, db_models

# This line creates the tables in your database file if they don't exist yet.
# It should be run once when the application starts.
db_models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Shopify Store Insights-Fetcher",
    description="An API to fetch and structure data from Shopify websites, with database persistence.",
    version="1.1.0", # Bump version
)

# --- Dependency for database session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    """Root endpoint to welcome users and check API health."""
    return {"message": "Welcome to the Shopify Insights API! The server is running."}

@app.post("/v1/insights", response_model=BrandInsights, tags=["Insights"])
async def get_store_insights(
    request: StoreRequest,
    db: Session = Depends(get_db) # Inject the database session
):
    """
    Accepts a Shopify store URL, scrapes for insights, saves the results
    to the database, and returns the structured JSON object.
    """
    try:
        scraper = ShopifyScraper(url=str(request.website_url))
        insights = await scraper.run()
        
        # If no products were found, it's likely not a valid Shopify store
        if not insights.product_catalog:
             raise HTTPException(
                status_code=404,
                detail="Could not find a valid product catalog. The URL may not be a Shopify store or is inaccessible."
            )

        # --- Save to database ---
        crud.save_brand_insights(db=db, insights=insights)
        
        return insights
        
    except RequestError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Website not found or failed to connect: {e.request.url}"
        )
    except Exception as e:
        import traceback
        traceback.print_exc() # Print full error for debugging
        raise HTTPException(
            status_code=500, 
            detail=f"An internal error occurred: {str(e)}"
        )