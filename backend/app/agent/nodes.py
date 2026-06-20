"""
LangGraph node functions.
Each function receives AgentState and returns a partial state update dict.
"""

import hashlib
import json
import ast
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
try:
    # LangChain < 0.2
    from langchain.agents import AgentExecutor, create_openai_functions_agent
except ImportError:
    # LangChain >= 0.2 moved AgentExecutor
    from langchain.agents.agent import AgentExecutor
    from langchain.agents import create_openai_functions_agent
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool

from .state import AgentState, DatabaseQuery, Conversation, TaskCreation
from .memory import load_memory, save_memory, now_iso
from .tools import get_current_datetime, get_datetime_from_query
from ..core.config import settings

# Global single-slot callbacks for the active streaming request.
# Set by routes.py before agent.invoke(); cleared in the finally block.
# Works regardless of which thread LangGraph calls nodes from.
_current_stream: dict = {"token": None, "status": None}
_current_stream_lock = threading.Lock()


def _get_token_cb():
    """Return the active put_token callback, or None."""
    with _current_stream_lock:
        return _current_stream["token"]


def _send_status(msg: str) -> None:
    with _current_stream_lock:
        cb = _current_stream["status"]
    print(f"[STATUS] {msg!r}  callback_set={cb is not None}")
    if cb:
        cb(msg)


# These are injected at graph-build time via build_nodes()
_llm = None
_db = None
_execute_query_tool = None
_intent_llm = None
_summary_llm = None
_sql_llm = None

# Schema cache — populated once at startup, never re-fetched
_schema_full_cache: str = ""
_schema_per_table: dict = {}

# SQL query cache — normalized question → generated SQL (in-memory, cleared on restart)
_sql_query_cache: dict = {}

# Table sets for keyword-based routing
_TASK_TABLES = {"Delegation", "Checklist"}
_PO_TABLES = {"PO Pending", "Purchase Intransit", "Purchase Receipt"}
_SALES_TABLES = {"Orders Pending", "Sales Invoices"}
_PROD_TABLES = {"Production Orders", "Job Card Production"}
_STOCK_TABLES = {"FG Stock", "RM Stock", "Store OUT", "Store IN"}
_FINANCE_TABLES = {"Collection Pending", "Payments"}
_EMP_TABLES = {"Employee Details"}
_ENQ_TABLES = {"Enquirys"}

OUT_OF_SCOPE_RESPONSE = (
    "Sorry, main sirf connected database ke data se related questions answer kar sakti hoon. "
    "Please database, reports, tasks, PO, stock, sales, collection, payments, employees, ya enquiries se related question poochiye."
)

_OUT_OF_SCOPE_KEYWORDS = {
    "algorithm", "api", "bug", "capital", "class", "code", "coding", "compile",
    "css", "debug", "essay", "factorial", "function", "game", "html", "java",
    "javascript", "joke", "leap year", "news", "prime number", "program",
    "python", "react", "recipe", "rust", "translate", "typescript", "weather",
}

_DB_SCOPE_KEYWORDS = {
    "checklist", "collection", "database", "delegation", "employee", "enquiry",
    "invoice", "order", "payment", "pending", "po", "purchase", "report", "sales",
    "stock", "task", "vendor", "kaam", "lena", "dena", "paisa",
}


def build_nodes(llm, db):
    """Inject shared resources before the graph is compiled."""
    global _llm, _db, _execute_query_tool, _schema_full_cache, _schema_per_table, _sql_query_cache
    _llm = llm
    _db = db
    _execute_query_tool = QuerySQLDataBaseTool(db=db)
    # Cache full schema once so every request avoids a DB roundtrip
    _schema_full_cache = db.get_table_info()
    for tname in db.get_usable_table_names():
        try:
            _schema_per_table[tname] = db.get_table_info(table_names=[tname])
        except Exception:
            pass
    # Restore persisted SQL cache — only load entries that are dicts (new format).
    # Old plain-string entries are silently dropped (they have no sig, so they'd miss anyway).
    for k, v in load_memory().get("sql_cache", {}).items():
        if isinstance(v, dict) and "sql" in v and "sig" in v:
            _sql_query_cache[k] = v


def set_aux_llms(intent_llm=None, summary_llm=None, sql_llm=None):
    """Inject optional fast/specialised LLMs."""
    global _intent_llm, _summary_llm, _sql_llm
    _intent_llm = intent_llm
    _summary_llm = summary_llm
    _sql_llm = sql_llm


def _get_relevant_tables(question: str) -> list:
    """Return only the tables relevant to this question to keep the SQL prompt small."""
    q = _normalize_text(question)
    tables: set = set()

    if any(k in q for k in ("task", "kaam", "delegation", "checklist", "assigned", "doer")):
        if "delegation" in q:
            tables.add("Delegation")
        elif "checklist" in q:
            tables.add("Checklist")
        else:
            tables.update(_TASK_TABLES)

    if re.search(r'\bpo\b', q) or any(k in q for k in ("purchase order", "indent", "vendor", "purchase")):
        tables.update(_PO_TABLES)

    if any(k in q for k in ("sales", "invoice", "delivery", "revenue")):
        tables.update(_SALES_TABLES)
    if re.search(r'\border\b', q):
        tables.update(_SALES_TABLES)

    if any(k in q for k in ("production", "job card", "manufacture")):
        tables.update(_PROD_TABLES)

    if any(k in q for k in ("stock", "inventory", "store")):
        tables.update(_STOCK_TABLES)
    if re.search(r'\bfg\b', q):
        tables.add("FG Stock")
    if re.search(r'\brm\b', q):
        tables.add("RM Stock")

    if "collection" in q:
        tables.add("Collection Pending")
    if "payment" in q:
        tables.add("Payments")

    if any(k in q for k in ("employee", "staff", "salary", "payroll")):
        tables.update(_EMP_TABLES)

    if any(k in q for k in ("enquiry", "enquiries", "lead")):
        tables.update(_ENQ_TABLES)

    known = set(_schema_per_table.keys())
    return [t for t in tables if t in known]


def _normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\bpensding\b|\bpanding\b|\bpendng\b", "pending", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z]+", _normalize_text(text)) if len(t) >= 3]


def _contains_keyword(text: str, keywords: set[str]) -> bool:
    for keyword in keywords:
        if " " in keyword:
            if keyword in text:
                return True
        elif len(keyword) <= 3:
            if re.search(rf"\b{re.escape(keyword)}\b", text):
                return True
        elif keyword in text:
            return True
    return False


def _rule_intent(question: str) -> str | None:
    q = _normalize_text(question)
    if _contains_keyword(q, {"create task", "assign task", "new task", "task banao"}):
        return "TaskCreation"
    if _is_clear_out_of_scope(question):
        return "Conversation"
    if _contains_keyword(q, _DB_SCOPE_KEYWORDS):
        return "DatabaseQuery"
    if _contains_keyword(q, {"hi", "hello", "thanks", "thank you"}):
        return "Conversation"
    return None


def _is_clear_out_of_scope(question: str) -> bool:
    """Catch obvious non-database requests before learned rules or the LLM can route them."""
    q = _normalize_text(question)
    if not q:
        return False
    if _contains_keyword(q, _DB_SCOPE_KEYWORDS):
        return False
    return _contains_keyword(q, _OUT_OF_SCOPE_KEYWORDS)


def _match_rule_score(rule_tokens: list[str], query_tokens: list[str]) -> float:
    if not rule_tokens or not query_tokens:
        return 0.0
    rule = set(rule_tokens)
    query = set(query_tokens)
    overlap = len(rule.intersection(query))
    return overlap / max(1, len(rule))


def _get_learned_intent(question: str) -> str | None:
    memory = load_memory()
    query_tokens = _tokenize(question)
    now = datetime.now(timezone.utc)
    best_intent = None
    best_score = 0.0
    for rule in memory.get("intent_rules", []):
        if not rule.get("enabled", True):
            continue
        expires_at = rule.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(expires_at) < now:
                    continue
            except Exception:
                pass
        # Support both "pattern_tokens" (new format) and "tokens" (legacy format).
        # Migrate old key in-place so it's normalized after the next save.
        if "tokens" in rule and "pattern_tokens" not in rule:
            rule["pattern_tokens"] = rule.pop("tokens")
        score = _match_rule_score(rule.get("pattern_tokens", []), query_tokens)
        threshold = float(rule.get("confidence", 0.75))
        if score >= threshold and score > best_score:
            best_score = score
            best_intent = rule.get("intent")
            rule["hit_count"] = int(rule.get("hit_count", 0)) + 1
            rule["last_used_at"] = now_iso()
    if best_intent:
        save_memory(memory)
    return best_intent


def _record_fallback_candidate(question: str, intent: str) -> None:
    tokens = _tokenize(question)[:8]
    if len(tokens) < 2:
        return
    memory = load_memory()
    candidates = memory.setdefault("intent_candidates", [])
    for cand in candidates:
        if cand.get("intent") == intent and cand.get("pattern_tokens") == tokens:
            cand["hit_count"] = int(cand.get("hit_count", 0)) + 1
            cand["last_used_at"] = now_iso()
            break
    else:
        candidates.append(
            {
                "pattern_tokens": tokens,
                "intent": intent,
                "hit_count": 1,
                "created_at": now_iso(),
                "last_used_at": now_iso(),
            }
        )
    # Promote candidates after enough repeated hits.
    rules = memory.setdefault("intent_rules", [])
    for cand in list(candidates):
        if int(cand.get("hit_count", 0)) >= 3:
            rules.append(
                {
                    "id": f"r-{len(rules)+1}",
                    "pattern_tokens": cand.get("pattern_tokens", []),
                    "intent": cand.get("intent", "DatabaseQuery"),
                    "confidence": 0.7,
                    "source": "llm_promoted",
                    "hit_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "created_at": now_iso(),
                    "last_used_at": now_iso(),
                    "expires_at": None,
                    "enabled": True,
                }
            )
            candidates.remove(cand)
    save_memory(memory)


def _is_simple_result(result_text: str) -> bool:
    if not result_text:
        return True
    # Heuristic: small tuple list typically under this size.
    return len(result_text) <= 1800


def _render_simple_template(state: AgentState) -> str:
    return (
        "### Result\n\n"
        f"- Query executed successfully.\n"
        f"- Preview data:\n\n`{str(state.get('result') or '')[:1400]}`"
    )


def _is_list_query(question: str) -> bool:
    q = _normalize_text(question)
    # Aggregate questions want a number, not a paginated list — skip the list-preview path.
    if any(k in q for k in ("total", "count", "how many", "kitne", "kitna", "sum", "average", "avg")):
        return False
    markers = ("list", "show", "pending", "tasks", "records", "entries", "kaam", "do")
    return any(m in q for m in markers)


def _parse_result_rows(raw_result):
    if isinstance(raw_result, list):
        return raw_result
    if isinstance(raw_result, str):
        try:
            parsed = ast.literal_eval(raw_result)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def _render_list_preview(result_dict: dict) -> str:
    total = int(result_dict.get("total_count", 0) or 0)
    cols = result_dict.get("preview_columns") or []
    rows = result_dict.get("preview_rows") or []
    if not rows:
        return (
            "### Result Preview\n\n"
            f"- Total records: **{total}**\n"
            "- Showing preview: **first 20 rows**\n\n"
            "_No preview rows available for this result._"
        )

    header_line = "| " + " | ".join(cols) + " |"
    sep_line = "|" + "|".join(["---"] * len(cols)) + "|"
    body = []
    for row in rows[:20]:
        body.append("| " + " | ".join(_format_value(v, col) for v, col in zip(row, cols)) + " |")

    return (
        "### Result Preview\n\n"
        f"- Total records: **{total}**\n"
        "- Showing preview: **first 20 rows**\n\n"
        + "\n".join([header_line, sep_line] + body)
    )


_CURRENCY_KEYWORDS = {"amount", "value", "price", "payment", "paisa", "balance", "bal",
                      "receipt", "collection", "pending_amount", "total_amount", "lena", "dena"}


def _format_value(v, col_name: str = "") -> str:
    """Format a single DB cell value for display in a markdown table."""
    if v is None:
        return "-"
    cls = type(v).__name__
    col_lower = col_name.lower()
    is_currency = cls == "Decimal" or any(k in col_lower for k in _CURRENCY_KEYWORDS)

    if cls in ("Decimal", "int", "float") and is_currency:
        num = float(v)
        if num >= 10_000_000:
            return f"₹{num / 10_000_000:.2f} Cr"
        if num >= 100_000:
            return f"₹{num / 100_000:.2f} L"
        if num >= 1_000:
            return f"₹{num:,.0f}"
        return f"₹{num:.2f}"

    if cls in ("int", "float"):
        num = float(v)
        if num >= 10_000_000:
            return f"{num / 10_000_000:.2f} Cr"
        if num >= 100_000:
            return f"{num / 100_000:.2f} L"
        if num >= 1_000:
            return f"{num:,.0f}"
        return str(int(num)) if num == int(num) else f"{num:.2f}"

    if cls in ("date", "datetime"):
        return v.strftime("%d-%m-%Y")
    s = str(v).replace("\n", " ").strip()
    return (s[:78] + "…") if len(s) > 80 else s


def _render_table(result_dict: dict) -> str:
    """Render a structured non-list query result as a markdown table."""
    cols = result_dict.get("columns") or []
    rows = result_dict.get("rows") or []
    if not rows:
        return "### Result\n\n_No data found._"
    # Single scalar — render as a clean key-value line, not a 1-row table.
    if len(rows) == 1 and len(cols) == 1:
        label = cols[0].replace("_", " ").title()
        return f"### Result\n\n**{label}:** {_format_value(rows[0][0], cols[0])}"
    header = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    body = [
        "| " + " | ".join(_format_value(v, col) for v, col in zip(row, cols)) + " |"
        for row in rows
    ]
    count_line = f"- Total rows: **{len(rows)}**\n\n" if len(rows) > 1 else ""
    return "### Result\n\n" + count_line + "\n".join([header, sep] + body)


def _stream_template_answer(answer: str, put_token) -> None:
    """Send template content line-by-line with a small delay for smooth rendering.
    Avoids the char-by-char flood that makes streaming appear stuck."""
    lines = answer.split('\n')
    for i, line in enumerate(lines):
        chunk = line + ('\n' if i < len(lines) - 1 else '')
        put_token(chunk)
        time.sleep(0.012)  # 12ms per line ≈ smooth typewriter effect


def _learn_summary_pattern(question: str, template_id: str) -> None:
    tokens = sorted(_tokenize(question)[:5])
    if not tokens:
        return
    key = ",".join(tokens)
    memory = load_memory()
    patterns = memory.setdefault("summary_patterns", {})
    item = patterns.get(key, {"template_id": template_id, "uses": 0})
    item["template_id"] = template_id
    item["uses"] = int(item.get("uses", 0)) + 1
    item["last_used_at"] = now_iso()
    patterns[key] = item
    save_memory(memory)


def _get_learned_summary_template(question: str) -> str | None:
    """Return the template_id learned for this question pattern, or None if unknown/unseen."""
    tokens = sorted(_tokenize(question)[:5])
    if not tokens:
        return None
    key = ",".join(tokens)
    memory = load_memory()
    item = memory.get("summary_patterns", {}).get(key)
    if item and int(item.get("uses", 0)) >= 2:
        return item.get("template_id")
    return None


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def classify_intent_node(state: AgentState):
    """Classifies the user's question by forcing the LLM to call a specific tool."""
    _send_status("Analysing your question...")
    print("--- Classifying Intent (with Function Calling) ---")
    question = state["question"]
    rule_intent = _rule_intent(question)
    if rule_intent:
        print(f"Intent: {rule_intent} (rule)")
        return {"intent": rule_intent}
    learned_intent = _get_learned_intent(question)
    if learned_intent:
        print(f"Intent: {learned_intent} (learned-rule)")
        return {"intent": learned_intent}

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are a strict intent classifier for a database-only assistant. "
                    "Call DatabaseQuery only when the user asks for information that should be fetched "
                    "from the connected business database, such as reports, pending tasks, PO, stock, "
                    "sales, collection, payments, employees, or enquiries. "
                    "Call TaskCreation only when the user wants to create or update a task in the database. "
                    "For coding requests, programming examples, general knowledge, explanations, advice, "
                    "or anything not answerable from the connected database, call Conversation."
                ),
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    tools = [DatabaseQuery, Conversation, TaskCreation]
    llm_with_tools = (_intent_llm or _llm).bind_tools(tools)
    runnable = prompt | llm_with_tools
    ai_message = runnable.invoke(
        {
            "question": state["question"],
            "chat_history": state.get("chat_history", []),
        }
    )
    intent = (
        "Conversation"
        if not ai_message.tool_calls
        else ai_message.tool_calls[0]["name"]
    )
    if intent == "DatabaseQuery" and _is_clear_out_of_scope(question):
        intent = "Conversation"
    _record_fallback_candidate(question, intent)
    print(f"Intent: {intent}")
    return {"intent": intent}


def handle_conversation_node(state: AgentState):
    """Refuses anything outside the database-backed assistant scope."""
    _send_status("Thinking...")
    print("--- Handling Conversation ---")
    print(f"Final Answer: {OUT_OF_SCOPE_RESPONSE}")
    return {"answer": OUT_OF_SCOPE_RESPONSE}


def analyze_query_node(state: AgentState):
    """Handles task creation from user."""
    _send_status("Understanding task details...")
    task = state.get("task_details", {})

    system_prompt = """Your job is to analyze user's queries, and extract the information for creating a task and return a json with following keys.

    description (required): The description of the task that is to be extracted from conversation. It should be short
    timestamp (optional, default: current_date): Use the `get_current_datetime` tool when user doesn't want to mention any timestamp, or wants to use current timestamp, like saying "aaj" or "now". Or use `get_datetime_from_query` when user provides a date time in natural language.
    planned_date (required): Use the `get_current_datetime` tool when user wants to use current timestamp. Or use `get_datetime_from_query` when user provides a date time in natural language. 
    department (optional, default: Not Provided): The department that needs to respond, extracted from converstation.
    doer_name (required): The person who should do the task (assignee).

    The current state of user task creation is,
    description: {description}
    timestamp: {timestamp}
    planned_date: {planned_date}
    department: {department}
    doer_name: {doer_name}

    ----
    **IMPORTANT:** Do not use default values until you are sure that user won't provide any other data based on conversation. Once the user provides some sort of confirmation, set the values to there default if empty.
    **IMPORTANT:** If a field is empty at the current point, dont add it to the JSON.
    **IMPORTANT:** Without context, do not assume `planned_date` and `timestamp`.
    **IMPORTANT:** Don't use any tool, until not required.
    ---

    When user ask to create a task, no data is provided. So just return open and closed curly braces

    ---
    Here is a list of valid queries for date parser in
    "tomorrow"
    "next week"
    "in 6 days"
    "next Monday"
    "on Friday"
    "2 weeks from now"
    "by the end of this month"
    "next year"
    "October 29, 2025"
    "in 3 hours"

    Use these to alter the user's date related queries and give in english.
    ---
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    tools = [get_current_datetime, get_datetime_from_query]
    agent_runnable = create_openai_functions_agent(_llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent_runnable, tools=tools, verbose=True)
    result = agent_executor.invoke(
        {
            "question": state["question"],
            "chat_history": state.get("chat_history", []),
            "description": task.get("description", ""),
            "timestamp": task.get("timestamp", ""),
            "planned_date": task.get("planned_date", ""),
            "department": task.get("department", ""),
            "doer_name": task.get("doer_name", ""),
        }
    )

    try:
        extracted = json.loads(
            result["output"].strip().replace("```json", "").replace("```", "")
        )
    except Exception:
        extracted = {
            "description": None,
            "planned_date": None,
            "department": None,
            "timestamp": None,
            "doer_name": None,
        }

    print("Extracted Task Details:", extracted)
    return {"task_details": extracted}


def ask_followup_node(state: AgentState):
    """Asks user follow-up based on current state."""
    _send_status("Preparing follow-up question...")
    task = state["task_details"]
    description = task.get("description")
    timestamp = task.get("timestamp")
    planned_date = task.get("planned_date")
    department = task.get("department")
    doer_name = task.get("doer_name")

    def _try_fmt(iso_str, fmt):
        if not iso_str:
            return ""
        try:
            return datetime.fromisoformat(iso_str).strftime(fmt)
        except (ValueError, TypeError):
            return iso_str  # fall back to raw string if unparseable

    timestamp_display = _try_fmt(timestamp, '%d-%m-%Y %I:%M %p')
    planned_date_display = _try_fmt(planned_date, '%d-%m-%Y')

    state_lines = []
    if description:
        state_lines.append(f"**Task Description:** {description}")
    if department:
        state_lines.append(f"**Department to Respond:** {department}")
    if doer_name:
        state_lines.append(f"**Assigned To:** {doer_name}")
    if timestamp_display:
        state_lines.append(f"**Timestamp:** {timestamp_display}")
    if planned_date_display:
        state_lines.append(f"**Planned Date:** {planned_date_display}")

    current_state_instruction = ""
    if state_lines:
        current_state_instruction = (
            "After your follow-up question, append the following EXACTLY (do not modify it):\n\n"
            "### **Current State:**\n"
            + "\n".join(state_lines)
        )

    system_prompt = """
    Based on the current state of the task, ask user a follow up question. Keep it short.

    The current state of user task creation is,
    description: {description} - Description of task
    timestamp: {timestamp} - When the task was created
    planned_date: {planned_date} - Supposed Planned date
    department: {department} - Department to Respond
    doer_name: {doer_name} - Person who will do the task

    The follow up question should be about one of these fields, and nothing else.
    if a field is filled don't ask about it.
    You can only ask follow up questions.

    -> Use Hinglish or English, on the basis of User query.
    -> Always ask a question about the next about whats left to be filled. Based on the provided details.
    -> Clearly mention what field the question is about.

    ---
    Use below format to ask for timestamp, change the words according to context.
    - Do you want to set a different timestamp or should I set to current time?

    {current_state_instruction}
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    runnable = prompt | _llm
    invoke_kwargs = {
        "question": state["question"],
        "chat_history": state.get("chat_history", []),
        "description": description or "",
        "timestamp": timestamp or "",
        "planned_date": planned_date or "",
        "department": department or "",
        "doer_name": doer_name or "",
        "current_state_instruction": current_state_instruction,
    }
    put_token = _get_token_cb()
    if put_token:
        followup = ""
        for chunk in runnable.stream(invoke_kwargs):
            token = chunk.content
            if token:
                put_token(token)
                followup += token
    else:
        followup = runnable.invoke(invoke_kwargs).content
    print(f"Follow Up: {followup}")
    return {"answer": followup}


def create_task_node(state: AgentState):
    """Creates the task in the SQL database using the existing engine."""
    _send_status("Creating task in database...")
    from sqlalchemy import text
    from ..db import engine  # imported here to avoid circular imports

    task_details = state["task_details"].copy()

    def _to_date(iso_str):
        """Convert an ISO timestamp string to a date object for DATE columns."""
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str).date()
        except (ValueError, TypeError):
            return None

    now = datetime.now(timezone.utc)
    delegation_data = {
        "Timestamp": task_details.get("timestamp") or now.isoformat(),  # TIMESTAMP column
        "Department_Name": task_details.get("department"),
        "Given_By": "AI",
        "Doer_Name": task_details.get("doer_name"),
        "Task_Description": task_details.get("description"),
        "Task_Start_Date": _to_date(task_details.get("timestamp")) or now.date(),  # DATE column; task start ≠ deadline
        "Planned_Date": _to_date(task_details.get("planned_date")),  # DATE column
        "Status": "Pending",
        "Update_Date": now.date(),  # DATE column; tracks when the record was last written
    }

    try:
        print("--- Executing SQL Insert (Delegation) ---")
        print(f"--- With Parameters: {delegation_data} ---")

        insert_delegation_sql = (
            "INSERT INTO \"Delegation\" "
            "(\"Timestamp\", \"Department_Name\", \"Given_By\", \"Doer_Name\", "
            "\"Task_Description\", \"Task_Start_Date\", \"Planned_Date\", \"Status\", \"Update_Date\") "
            "VALUES (:Timestamp, :Department_Name, :Given_By, :Doer_Name, "
            ":Task_Description, :Task_Start_Date, :Planned_Date, :Status, :Update_Date) "
            "RETURNING \"id\", \"Task_Description\", \"Planned_Date\""
        )

        with engine.begin() as conn:
            result = conn.execute(text(insert_delegation_sql), [delegation_data])
            created_task = result.fetchone()

            if created_task:
                print(f"SQL Success: {created_task}")
                planned = created_task[2]
                planned_str = planned.strftime('%d-%m-%Y') if planned else "Not set"
                answer = (
                    f"Task Created Successfully!\n\n"
                    f"**Task:** {created_task[1]}\n"
                    f"\n**Planned Date:** {planned_str}"
                )
            else:
                answer = "I'm sorry, I tried to create the task but something went wrong and I didn't get a result back."

    except Exception as e:
        print(f"SQL/Python Exception: {e}")
        answer = f"I'm sorry, I tried to create the task but failed. Error: {e}"

    return {"answer": answer, "task_details": {}}


def generate_query_node(state: AgentState):
    """Takes the user's question, generates a SQL query, and adds it to the state."""
    print("--- Generating SQL Query ---")

    system_prompt = """You are an AI expert in writing PostgreSQL queries.
    Given a user question and conversation history, create a syntactically correct PostgreSQL query.
    The query should fullfill user's query.
    The query should work on the given schema.
    {schema}

    --- Querying Rules ---
    1.  **SINGLE RESULT SET:** Always return all data in ONE query. Never write multiple separate SELECT statements — the database tool only returns the last result set and silently drops the rest.
    2.  **`UNION ALL` when combining tables:** When combining Delegation and Checklist in a single result:
        - NEVER use `SELECT *` — columns and types differ between tables.
        - **Select ONLY the columns needed to answer the question** (typically 4–8 columns). Do NOT select all columns from both tables.
        - Always include `'TableName'::text AS source` so each row knows its origin.
        - For columns that exist in one table but not the other, use a `NULL` cast matching the real column's type, e.g. `NULL::date AS "Planned_Date"`.
        - Ensure EVERY column position has the SAME data type on both sides — check each position before writing the query.
        - Minimal example: `SELECT 'Delegation'::text AS source, "Doer_Name", "Task_Description", "Planned_Date", "Status" FROM "Delegation" UNION ALL SELECT 'Checklist'::text AS source, "Doer_Name", "Task_Description", NULL::date AS "Planned_Date", "Status" FROM "Checklist"`.
    3.  Use advanced matching techniques to respond to more flexible queries.
    4.  **Case-insensitive grouping:** When using `GROUP BY` on name columns like `"Doer_Name"`, always group on `LOWER("Doer_Name")` and select `INITCAP(MAX("Doer_Name"))` so that "ahitesh tandan" and "Ahitesh Tandan" merge into one group instead of appearing as separate rows.

    --- Database Descriptions ---
    - When a user asks about "tasks" or "kaam", they are referring to entries where a table has fields relevant to tasks, like "TaskID", or "Task Description". You MUST query one of given tables that is related to tasks. DO NOT invent or query a non-existent table named "tasks".
    - When a user asks about "orders" or "po", they are usually referring to entries where a table has fields relevant to Purchase Orders like "Quantity", "PO Number" or "Indent Number".
    - When a user asks about "po pending" or "pending po", they are referring to the orders that are pending.
    - When a user refers to sheets they are actually talking about tables.
    - The database deals with several types of data: Tasks, Purchase Orders, Sales, Production, Inventory, Finance, Employees, and Enquiries.
    - Here is a list of tables that fall in each category:
        - **Tasks**
            - **Checklist**: contains **recurring/periodic** tasks on a fixed schedule (daily, weekly, monthly, yearly). Each scheduled occurrence is a separate row. Do NOT use this table when the user says "delegation" or asks about one-time assigned tasks.
              - **IMPORTANT Checklist pending rule**: For Checklist "pending" queries, ALWAYS add `AND "Task_Start_Date" <= CURRENT_DATE` to the WHERE clause. This excludes future-scheduled occurrences that haven't happened yet and would otherwise flood results with hundreds of irrelevant rows.
            - **Delegation**: contains **one-time assigned or AI-created tasks**. Use this table when the user says "delegation", "delegate", "assigned tasks", or asks about tasks Given_By a person.
            - **Keyword routing rules (STRICT)**:
              - If the user says **"delegation"** (e.g., "delegation tasks", "delegation pending") → query **ONLY** the **Delegation** table. Do NOT touch Checklist.
              - If the user says **"checklist"** → query **ONLY** the **Checklist** table.
              - If the user says **"tasks"** or **"kaam"** without either keyword → combine both tables using `UNION ALL` with a `source` column ('Delegation' or 'Checklist'). Use Querying Rule #2 for proper type alignment.
            - When using `UNION ALL` across both tables, always include the Checklist date filter (`"Task_Start_Date" <= CURRENT_DATE` for pending queries) to prevent hundreds of future-scheduled rows from flooding the result.
        - **Purchase Orders**
            - **PO Pending**: contains purchase order information, including products, quantities, rates, total amounts, and current fulfillment status.
            - **Purchase Intransit**: contains purchase material not yet received in the plant but in transit.
            - **Purchase Receipt**: contains material that has been received in the plant.
        - **Sales**
            - **Orders Pending**: contains pending sales order details.
            - **Sales Invoices** (formerly 'Delivery Invoices'): contains company sales invoices generated for deliveries; use for sales totals, tax, and revenue reporting.
        - **Production**
            - **Production Orders**: contains production order details.
            - **Job Card Production**: contains job card details related to production.
        - **Inventory**
            - **FG Stock**: contains information about Finished Goods stock levels.
            - **RM Stock**: contains information about Raw Material stock levels.
            - **Store OUT**: records materials issued from the store.
            - **Store IN**: records materials received into the store.
        - **Finance**
            - **Collection Pending**: deals with collections that are yet to be received (unpaid/partially paid invoices and amounts).
            - **Payments**: contains details about payments made or received.
        - **Employees**
            - **Employee Details**: contains information about company employees.
        - **Enquiries**
            - **Enquirys**: contains details about order related enquiries from customers.
    - Do not take table as there names suggest. Use the above guide to get the relevant table.
    - When user asks query based on some identity, that can be present in other tables, and there is no previous context for choosing a table, give data, or all occurances.
    ------------------------
    
    --- Data Dictionary ---
    - The "Status" column:
      - **Complete** values: 'Completed', 'Yes', 'Done' (case-insensitive).
      - **Pending** values: NULL, empty string '', 'Not Complete', 'Pending', or any value that does not match a complete value.
      - **Canonical SQL for pending tasks** (use this exact pattern for consistency):
        `("Status" IS NULL OR TRIM("Status") = '' OR ("Status" NOT ILIKE 'done' AND "Status" NOT ILIKE 'completed' AND "Status" NOT ILIKE 'yes'))`
      - **Canonical SQL for completed tasks**:
        `("Status" ILIKE 'done' OR "Status" ILIKE 'completed' OR "Status" ILIKE 'yes')`
      - Always use these exact patterns — never mix ILIKE and NOT IN or other variants.
    - The "Priority" column: 'High', 'Urgent', 'H' all mean high priority. 'Low' and 'L' mean low priority.
    -----------------------

    --- Instructions ---
    - Report queries should include
        - Total number of relevant entries
        - Total amount pending (if applicable)
        - Total completed (if applicable)
        - Total pending (if applicable)
        - Other relevant data points based on the columns in the table.
        - Not all data points are directly available from columns names, some data points need to be generated using SQL functions like COUNT, SUM, etc. on relevant columns.
        - And a small table with aggregate data based on given by, vendors or parties and there products etc. showing insight on the data. Though data points are more important.
        - Calculate quantities, amounts, etc. based on different columns in the table. For example, 
            - total amount pending can be calculated using SUM of "Amount" column where "Status" is 'Pending'.
            - total quantity can be calculated using different columns of the row related to quantity like "Quantity", "Total Lifted", "Order Cancelled Quantity", etc. ex Pending Quantity = Quantity - Total Lifted Quantity.
            - Make sure to calculate these data not just SUM("COLUMN_NAME") everywhere.
            - Show all the relevant columns in the final table.
    - Make sure that the output of SQL query gives all data at once. Only give one query.
    --------------------
    - **IMPORTANT:** Do NOT add comments to the SQL query. Return the SQL only.
    - **IMPORTANT:** Only return the SQL query. Do not add any other text or explanation.
    - **IMPORTANT:** If a table or column name contains a space or is a reserved keyword, you MUST wrap it in double quotes. For example: "Task Description".
    - **IMPORTANT:** Use the columns provided in the schema, if user mention a column that is not in schema, try to find the closest relevant column in the schema.
    - **IMPORTANT:** "PO Pending" or "Pending PO" mean orders that are pending. just "PO" means get data from PO pending table.
    """

    # Signature = hash of prompt rules + full schema.
    # If either changes (prompt update, schema change), every entry auto-invalidates.
    cache_sig = hashlib.md5(
        (system_prompt + _schema_full_cache).encode("utf-8", errors="replace")
    ).hexdigest()[:8]

    retries = state.get("retries") or 0

    # Cache check: on first attempt, reuse SQL if sig still matches.
    # On retry (retries>0) always regenerate — cached SQL may have caused the error.
    if retries == 0:
        cache_key = _normalize_text(state["question"])
        entry = _sql_query_cache.get(cache_key)
        if isinstance(entry, dict) and entry.get("sig") == cache_sig:
            _send_status("Writing SQL query...")
            print(f"Generated Query (cache hit, sig={cache_sig}): {entry['sql'][:120]}...")
            # Refresh last-used timestamp for LRU ordering
            entry["used_at"] = now_iso()
            return {"query": entry["sql"], "retries": 1}
        elif entry is not None:
            print(f"Cache entry stale (sig mismatch), regenerating.")

    _send_status("Retrying SQL query..." if retries > 0 else "Writing SQL query...")

    result_text = state.get("result") or ""
    if "Error:" in result_text:
        system_prompt += """
        \n---
        The previous query you wrote failed with this exact error:
        {error}
        Read the error carefully and fix the root cause. Common causes:
        - Type mismatch in UNION (e.g., a date column vs a text column) — cast the mismatched column explicitly, e.g. "Delay"::text or NULL::text
        - Using UNION when the keyword routing rules require a single table
        - Wrong column name or table name
        Write a new corrected SQL query that fixes the specific error above.
        ---
        """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    runnable = prompt | (_sql_llm or _llm)
    relevant_tables = _get_relevant_tables(state["question"])
    if relevant_tables:
        schema_str = "\n\n".join(_schema_per_table[t] for t in relevant_tables)
    else:
        schema_str = _schema_full_cache
    raw_query = runnable.invoke(
        {
            "question": state["question"],
            "chat_history": state.get("chat_history", []),
            "schema": schema_str,
            "error": result_text,
        }
    ).content
    sql_query = raw_query.strip().replace("```sql", "").replace("```", "").strip()
    print(f"Generated Query: {sql_query}")
    # Persist cache entry with sig. Stale/old entries for this key are replaced.
    if retries == 0:
        cache_key = _normalize_text(state["question"])
        new_entry = {"sql": sql_query, "sig": cache_sig, "used_at": now_iso()}
        _sql_query_cache[cache_key] = new_entry
        mem = load_memory()
        sql_cache = mem.setdefault("sql_cache", {})
        sql_cache[cache_key] = new_entry
        # LRU eviction: keep max 200 entries, drop least recently used
        if len(sql_cache) > 200:
            oldest_key = min(
                sql_cache,
                key=lambda k: sql_cache[k].get("used_at", "") if isinstance(sql_cache[k], dict) else ""
            )
            del sql_cache[oldest_key]
            _sql_query_cache.pop(oldest_key, None)
        save_memory(mem)
    return {"query": sql_query, "retries": int(retries) + 1}


def execute_query_node(state: AgentState):
    """Executes the SQL query and returns the result."""
    _send_status("Fetching data from database...")
    print("--- Executing SQL Query ---")
    query = (state["query"] or "").strip().rstrip(";")

    if _is_list_query(state.get("question", "")):
        _send_status("Counting total records...")
        from sqlalchemy import text
        from ..db import engine

        count_query = f'SELECT COUNT(*) AS total_count FROM ({query}) AS counted_rows'
        preview_query = f'SELECT * FROM ({query}) AS preview_rows LIMIT 20'

        def _run_count():
            with engine.connect() as conn:
                row = conn.execute(text(count_query)).fetchone()
                return int(row[0]) if row and row[0] is not None else 0

        def _run_preview():
            with engine.connect() as conn:
                res = conn.execute(text(preview_query))
                return [str(k) for k in res.keys()], [tuple(r) for r in res.fetchall()]

        with ThreadPoolExecutor(max_workers=2) as ex:
            count_f = ex.submit(_run_count)
            preview_f = ex.submit(_run_preview)
            total_count = count_f.result()
            preview_columns, preview_rows = preview_f.result()

        result = {
            "is_list_preview": True,
            "total_count": total_count,
            "preview_columns": preview_columns,
            "preview_rows": preview_rows,
        }
    else:
        # Use SQLAlchemy directly so we get column names + typed values (not a raw string).
        # On error, fall back to a string starting with "Error:" so retry logic still works.
        try:
            from sqlalchemy import text
            from ..db import engine
            with engine.connect() as conn:
                res = conn.execute(text(query))
                cols = [str(k) for k in res.keys()]
                rows = [tuple(r) for r in res.fetchall()]
            result = {"is_table": True, "columns": cols, "rows": rows}
        except Exception as exc:
            result = f"Error: {exc}"

    print(f"Query Result: {result}")
    return {"result": result}


def summarize_result_node(state: AgentState):
    """Takes the query result and creates a natural language answer."""
    question = state.get("question", "")
    result = state.get("result")
    learned = _get_learned_summary_template(question)

    # Fast-path: learned template routes us directly, skipping all shape checks.
    if learned == "list_preview_v1" and isinstance(result, dict) and result.get("is_list_preview"):
        _send_status("Preparing answer...")
        answer = _render_list_preview(result)
        put_token = _get_token_cb()
        if put_token:
            _stream_template_answer(answer, put_token)
        _learn_summary_pattern(question, "list_preview_v1")
        print(f"Final Answer: {answer}")
        return {"answer": answer}

    if learned == "table_template_v1" and isinstance(result, dict) and result.get("is_table"):
        _send_status("Preparing answer...")
        answer = _render_table(result)
        put_token = _get_token_cb()
        if put_token:
            _stream_template_answer(answer, put_token)
        _learn_summary_pattern(question, "table_template_v1")
        print(f"Final Answer: {answer}")
        return {"answer": answer}

    # No learned template (or llm_summary_v1) — fall through to shape checks.
    if isinstance(result, dict) and result.get("is_list_preview"):
        _send_status("Preparing answer...")
        answer = _render_list_preview(result)
        put_token = _get_token_cb()
        if put_token:
            _stream_template_answer(answer, put_token)
        _learn_summary_pattern(question, "list_preview_v1")
        print(f"Final Answer: {answer}")
        return {"answer": answer}

    if isinstance(result, dict) and result.get("is_table"):
        _send_status("Preparing answer...")
        answer = _render_table(result)
        put_token = _get_token_cb()
        if put_token:
            _stream_template_answer(answer, put_token)
        _learn_summary_pattern(question, "table_template_v1")
        print(f"Final Answer: {answer}")
        return {"answer": answer}

    if _is_simple_result(str(result or "")):
        _send_status("Preparing answer...")
        answer = _render_simple_template(state)
        put_token = _get_token_cb()
        if put_token:
            _stream_template_answer(answer, put_token)
        _learn_summary_pattern(question, "simple_template_v1")
        print(f"Final Answer: {answer}")
        return {"answer": answer}

    system_prompt = """
    You are a helpful AI assistant, Diya. 
    Your job is to answer the user's question in concise manner, based on the data provided, which should be easy and fast to read, with markup and lists and tables if needed. 
    Only reply in English or Hindi based on user's question. 
    Do not give any clarification about how you got the result. 
    Never reply with more than 20 rows of data, whether that be in list or tables.
    Show data points in readable format.
    All currencies are in Rupees until mentioned otherwise. Show the relevant units wherever possible.
    Keep the large numbers in human readable format, and use indian number system (lakhs, crores) and commas.
    In reports, based on data points, give bite sized insights on the data. Bold the important numbers and details.
    Show information related to all rows seprately, if needed use tables or lists in reports.
    The structure of report should be,
        1. The table or list of data (if applicable)
        2. The data points summary
        3. The insights on the data.
    """

    _send_status("Preparing answer...")
    print("--- Summarizing Result ---")
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                """Based on the user's question: "{question}"
        The following SQL query was generated: "{query}"
        And here is the result from the database: "{result}"
        Please provide a clear, natural language answer.
        Normalize table names, and remove _ in between words.
        """,
            ),
        ]
    )
    runnable = prompt | (_summary_llm or _llm)
    invoke_kwargs = {
        "question": question,
        "query": state["query"],
        "result": result,
    }
    put_token = _get_token_cb()
    if put_token:
        answer = ""
        for chunk in runnable.stream(invoke_kwargs):
            token = chunk.content
            if token:
                put_token(token)
                answer += token
    else:
        answer = runnable.invoke(invoke_kwargs).content
    _learn_summary_pattern(question, "llm_summary_v1")
    print(f"Final Answer: {answer}")
    return {"answer": answer}


def handle_error_node(state: AgentState):
    """Handles cases where the agent gives up after multiple retries."""
    _send_status("Having trouble, preparing response...")
    print("--- Agent failed after multiple retries ---")
    error_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful AI assistant, Diya, for a SQL database. The query you generated failed multiple times. Just say to the user that you couldn't find the answer. Resturn small easy to read with markup response. All currencies are in Rupees until mentioned otherwise. Show the units wherever possible.",
            ),
            (
                "human",
                """The user asked: "{question}"
        Your last attempted SQL query was: "{query}"
        It failed with the error: "{error}"
        Please provide a clear, natural language response apologizing for the failure and offering advice.""",
            ),
        ]
    )
    runnable = error_prompt | _llm
    invoke_kwargs = {
        "question": state["question"],
        "query": state["query"],
        "error": state.get("result", "Unknown error"),
    }
    put_token = _get_token_cb()
    if put_token:
        answer = ""
        for chunk in runnable.stream(invoke_kwargs):
            token = chunk.content
            if token:
                put_token(token)
                answer += token
    else:
        answer = runnable.invoke(invoke_kwargs).content
    print(f"Final Answer: {answer}")
    return {"answer": answer}
