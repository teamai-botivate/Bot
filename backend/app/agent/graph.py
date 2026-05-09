"""
Builds and compiles the LangGraph StateGraph agent.
Call `build_agent()` once at startup; it returns the compiled graph.
"""

from langgraph.graph import StateGraph, END

from .state import AgentState
from .nodes import (
    build_nodes,
    classify_intent_node,
    handle_conversation_node,
    analyze_query_node,
    ask_followup_node,
    create_task_node,
    generate_query_node,
    execute_query_node,
    summarize_result_node,
    handle_error_node,
)
from .edges import decide_intent_path, decide_result_status, decide_response_type


def build_agent(llm, db):
    """
    Inject LLM + DB resources into the node layer, then compile the graph.

    Args:
        llm: A LangChain LLM instance (e.g. ChatOpenAI).
        db:  A LangChain SQLDatabase instance.

    Returns:
        Compiled LangGraph CompiledStateGraph ready to .invoke().
    """
    # Inject shared resources into the nodes module
    build_nodes(llm, db)

    graph = StateGraph(AgentState)

    # --- Register Nodes ---
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("handle_conversation", handle_conversation_node)
    graph.add_node("analyze_query", analyze_query_node)
    graph.add_node("ask_followup", ask_followup_node)
    graph.add_node("create_task", create_task_node)
    graph.add_node("generate_query", generate_query_node)
    graph.add_node("execute_query", execute_query_node)
    graph.add_node("summarize_result", summarize_result_node)
    graph.add_node("handle_error", handle_error_node)

    # --- Entry Point ---
    graph.set_entry_point("classify_intent")

    # --- Edges ---
    graph.add_conditional_edges(
        "classify_intent",
        decide_intent_path,
        {
            "generate_query": "generate_query",
            "handle_conversation": "handle_conversation",
            "analyze_query": "analyze_query",
        },
    )
    graph.add_conditional_edges(
        "analyze_query",
        decide_response_type,
        {
            "ask_followup": "ask_followup",
            "create_task": "create_task",
        },
    )
    graph.add_edge("generate_query", "execute_query")
    graph.add_conditional_edges(
        "execute_query",
        decide_result_status,
        {
            "generate_query": "generate_query",
            "summarize_result": "summarize_result",
            "handle_error": "handle_error",
        },
    )
    graph.add_edge("handle_conversation", END)
    graph.add_edge("ask_followup", END)
    graph.add_edge("create_task", END)
    graph.add_edge("handle_error", END)
    graph.add_edge("summarize_result", END)

    return graph.compile()
