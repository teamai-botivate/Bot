"""
Pydantic schemas for the FastAPI request and response bodies.
"""

from pydantic import BaseModel
from typing import List, Dict


class ChatRequest(BaseModel):
    question: str
    chat_history: List[Dict[str, str]]  # e.g. [{"type": "human", "content": "hi"}]


class ChatResponse(BaseModel):
    answer: str
