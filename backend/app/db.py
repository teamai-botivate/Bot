"""
Database connection singleton.
Imported by nodes that need direct engine access (e.g. create_task_node).
"""

from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase

from .core.config import settings

db = None
engine = None

if settings.DATABASE_URI:
    try:
        engine = create_engine(settings.DATABASE_URI, pool_pre_ping=True)
        db = SQLDatabase(engine=engine)
        print("✅ Database connected successfully")
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        print("Running in demo mode without database")
        db = None
        engine = None
else:
    print("⚠️  DATABASE_URI not set. Running in demo mode.")
