"""
Database connection singleton.
Imported by nodes that need direct engine access (e.g. create_task_node).
"""

from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase

from .core.config import settings

if not settings.DATABASE_URI:
    raise ValueError(
        "DATABASE_URI is not set. "
        "Please add it to your .env file or environment variables."
    )

engine = create_engine(settings.DATABASE_URI)
db = SQLDatabase(engine=engine)
