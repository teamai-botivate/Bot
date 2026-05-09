"""
Custom LangChain tools used by the agent nodes.
"""

from datetime import datetime
from langchain.tools import tool
import dateparser


@tool
def get_current_datetime() -> str:
    """Returns today's date and the current time in ISO 8601 format."""
    return datetime.now().isoformat()


@tool
def get_datetime_from_query(query: str) -> str:
    """Returns a date time in ISO 8601 format based on the query in english and suitable for parsing date time with dateparser."""
    # Strip leading prepositions that confuse dateparser (e.g. "before May 23" → "May 23")
    cleaned = query.strip()
    for prefix in ("before ", "by ", "until ", "till ", "upto ", "up to "):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    parsed = dateparser.parse(
        cleaned,
        settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": datetime.now()},
    )
    if parsed is None:
        return (
            f"Could not parse a date from '{query}'. "
            "Please rephrase as a simple date, e.g. 'May 23, 2026', 'in 2 weeks', or 'next Monday'."
        )
    return parsed.isoformat()
