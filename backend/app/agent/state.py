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
    """The user is asking a question that requires a database query, or can be solved by an sql query"""
    pass


class Conversation(BaseModel):
    """The user is greeting, making small talk, or asking a general knowledge question not related to database or cannot be handled with sql."""
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
