"""
State definitions for the LangGraph agent.
"""

from typing import List, TypedDict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pydantic models used for intent classification (tool-calling)
# ---------------------------------------------------------------------------

class DatabaseQuery(BaseModel):
    """The user is asking about data that exists in the connected business database and must be answered by querying that database."""
    pass


class Conversation(BaseModel):
    """The user is greeting, making small talk, asking coding/general knowledge, or asking anything outside the connected database scope."""
    pass


class TaskCreation(BaseModel):
    """The user is trying to create a new task, or add more details to a task in progress"""
    pass


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class Task(TypedDict):
    description: str
    timestamp: str
    planned_date: str
    department: str
    doer_name: str


class AgentState(TypedDict):
    question: str
    chat_history: List[BaseMessage]
    query: str
    result: str
    retries: int
    task_details: Task
    answer: str
    intent: str
