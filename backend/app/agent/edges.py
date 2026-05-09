"""
Conditional edge (routing) functions for the LangGraph agent.
"""

from .state import AgentState


def decide_intent_path(state: AgentState) -> str:
    if state["intent"] == "DatabaseQuery":
        return "generate_query"
    if state["intent"] == "TaskCreation":
        return "analyze_query"
    return "handle_conversation"


def decide_result_status(state: AgentState) -> str:
    result_text = str(state.get("result") or "")
    retries = int(state.get("retries") or 0)
    if "Error:" in result_text:
        print("--- Query failed. Looping back to generate a new query. ---")
        return "handle_error" if retries > 7 else "generate_query"
    return "summarize_result"


def decide_response_type(state: AgentState) -> str:
    """Decides whether to ask a follow-up or create the task."""
    description = state["task_details"].get("description", None)
    timestamp = state["task_details"].get("timestamp", None)
    planned_date = state["task_details"].get("planned_date", None)
    department = state["task_details"].get("department", None)
    doer_name = state["task_details"].get("doer_name", None)

    if not all((description, timestamp, planned_date, department, doer_name)):
        return "ask_followup"
    return "create_task"
