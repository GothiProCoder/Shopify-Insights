# Shopify Store Insights-Fetcher

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![Framework](https://img.shields.io/badge/Framework-FastAPI-green.svg)
![Database](https://img.shields.io/badge/Database-SQLAlchemy-red.svg)

An advanced backend application designed to scrape, analyze, and structure key business insights from Shopify-powered e-commerce websites. This project provides a RESTful API that accepts a store's URL and returns a comprehensive, well-structured JSON object containing valuable data about the brand and its products.

The system is built with a focus on robustness, scalability, and maintainability, adhering to modern software development best practices.

## ✨ Features

-   **Full Product Catalog Extraction:** Fetches the entire product list directly from Shopify's `/products.json` endpoint.
-   **Homepage Analysis:** Scrapes the main page to identify hero products and key brand messaging.
-   **Policy & Legal Content Extraction:** Intelligently finds links to pages like Privacy Policy, Refund Policy, and Terms of Service, and then scrapes the **full text content** from those pages.
-   **Intelligent FAQ Scraping:** Deploys a resilient, multi-layered "hunter" strategy to extract Frequently Asked Questions, handling multiple common formats:
    1.  **On-Page Accordions:** Detects and parses FAQs located directly on a single page.
    2.  **Linked/Categorized Hubs:** Identifies pages that act as a hub of links to individual question/answer pages and scrapes each one.
    3.  **Fallback Content Grab:** As a last resort, captures the full formatted text of the FAQ page if a structured format isn't found.
-   **Contact & Social Media Discovery:** Extracts contact details (emails, phone numbers) and social media handles (Instagram, Facebook, etc.) from across the site.
-   **Structured JSON Response:** All scraped data is organized into a clean, predictable, and deeply nested JSON object using Pydantic models for data validation.
-   **Database Persistence:** Saves all successfully scraped brand and product data into a SQL database using SQLAlchemy, ensuring data is not lost between requests. (Defaults to SQLite for ease of use, easily switchable to MySQL).

## 🛠️ Technology Stack

-   **Backend Framework:** **FastAPI**
-   **Data Validation:** **Pydantic**
-   **Asynchronous HTTP Client:** **HTTPX**
-   **HTML Parsing:** **BeautifulSoup4** & **LXML**
-   **Database ORM:** **SQLAlchemy**
-   **Database Driver:** **SQLite** (for development), compatible with **PyMySQL** (for production)
-   **Language:** **Python 3.9+**

## 📂 Project Structure

The project follows a clean, layered architecture to promote separation of concerns and maintainability, adhering to SOLID principles.

```
shopify-insights/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app, routes, and main logic
│   ├── models.py           # Pydantic models for API request/response
│   ├── scraper.py          # All scraping logic encapsulated in a class
│   ├── crud.py             # Database Create/Read/Update/Delete operations
│   ├── db_models.py        # SQLAlchemy models for DB tables
│   └── database.py         # Database session and engine setup
├── .env                  # Environment variables (e.g., database credentials)
├── requirements.txt      # Project dependencies
└── README.md             # This file
```

## 🚀 Getting Started

### Prerequisites

-   Python 3.9 or higher
-   Git

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/GothiProCoder/Shopify-Insights/
    cd shopify-insights
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # For Unix/macOS
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the Database:**
    The application is configured to use a local **SQLite** database by default, which requires no setup. It will create a `shopify_insights.db` file in the root directory.

    To switch to **MySQL**, open `app/database.py` and switch the comment on the `SQLALCHEMY_DATABASE_URL` variable, filling in your own credentials.

5.  **Run the application:**
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```
    The API server will now be running on `http://localhost:8000`.

## ⚙️ API Usage

The application exposes one primary endpoint for fetching insights.

### Get Store Insights

-   **Endpoint:** `POST /v1/insights`
-   **Description:** Accepts a Shopify store URL and returns a structured JSON object with all scraped insights.
-   **Body (raw JSON):**
    ```json
    {
        "website_url": "https://<shopify-store-url>.com"
    }
    ```
    *Example: `"https://memy.co.in"`*

#### ✅ Success Response (200 OK)

A successful request returns a comprehensive JSON object.
```json
{
  "store_url": "https://memy.co.in/",
  "product_catalog": [
    {
      "id": 7859...,
      "title": "Natural Look Lash 01",
      "vendor": "ME & MY",
      "price": 349.0,
      "image_url": "https://..."
    }
  ],
  "policies": {
    "Privacy Policy": {
      "url": "https://memy.co.in/policies/privacy-policy",
      "content": "This Privacy Policy describes how memy.co.in (the “Site” or “we”) collects, uses, and discloses your Personal Information..."
    }
  },
  "faqs": [
    {
        "question": "How long does shipping take?",
        "answer": "Standard shipping usually takes 3-5 business days."
    }
  ],
  "social_handles": {
    "instagram": "https://www.instagram.com/memy.co.in/"
  },
  "contact_details": {
    "emails": ["support@memy.co.in"],
    "phone_numbers": []
  },
  // ... and other fields
}
```

#### ❌ Error Responses

| Status Code | Detail                                                | Reason                                                               |
| :---------- | :---------------------------------------------------- | :------------------------------------------------------------------- |
| **404**     | `Website not found or failed to connect`              | The provided URL is unreachable or does not exist.                   |
| **404**     | `Could not find a valid product catalog...`           | The URL is likely not a standard Shopify store.                      |
| **500**     | `An internal error occurred: ...`                     | An unexpected error happened during the scraping or processing phase. |
| **422**     | `Unprocessable Entity`                                | The request body is malformed (e.g., URL is not a valid `HttpUrl`).    |

## 🧠 Architectural Decisions

-   **Layered Architecture:** The code is strictly divided into layers (API routing, data models, scraping service, database operations) to ensure high cohesion, low coupling, and easy testing.
-   **Asynchronous by Design:** Built on FastAPI and HTTPX, the application is fully asynchronous, allowing it to handle I/O-bound tasks like web scraping with high efficiency and concurrency.
-   **Data-Centric with Pydantic:** Pydantic models are used everywhere to enforce strict data schemas for API requests, responses, and internal data structures, preventing common data-related bugs.
-   **ORM for Database Independence:** SQLAlchemy provides an abstraction layer over the database, making it easy to switch from SQLite to a production-grade database like MySQL or PostgreSQL with minimal code changes.
-   **Encapsulated Scraper Logic:** All complex scraping logic is contained within the `ShopifyScraper` class, making it reusable and isolating it from the API and database concerns.

## 🔮 Future Improvements

-   **Competitor Analysis:** Implement the bonus feature to automatically find and scrape competitor websites for comparative analysis.
-   **Distributed Task Queue:** For very large-scale scraping, integrate Celery with Redis/RabbitMQ to offload scraping tasks to background workers.
-   **Caching Layer:** Implement a Redis cache to store recent results, reducing redundant scraping and improving response times for popular URLs.
-   **Containerization:** Dockerize the application for consistent deployments and easier orchestration.
-   **Enhanced Testing:** Expand the test suite to include integration tests and mock external API calls for more comprehensive validation.
