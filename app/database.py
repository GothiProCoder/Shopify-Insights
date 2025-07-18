from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Configuration ---
# We use SQLite for ease of use in this demo environment.
# It creates a single file 'shopify_insights.db' in your project root.
SQLALCHEMY_DATABASE_URL = "sqlite:///./shopify_insights.db"

# To switch to MySQL, you would comment out the line above and use this one instead,
# after filling in your credentials.
# SQLALCHEMY_DATABASE_URL = "mysql+pymysql://user:password@host:port/dbname"

# --- Engine Setup ---
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # This connect_args is specific to SQLite and required for FastAPI.
    # It can be removed if you switch to MySQL.
    connect_args={"check_same_thread": False}
)

# --- Session Factory ---
# Each instance of SessionLocal will be a new database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Declarative Base ---
# We will inherit from this class to create each of the ORM models (database tables).
Base = declarative_base()