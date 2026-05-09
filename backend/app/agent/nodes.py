"""
LangGraph node functions.
Each function receives AgentState and returns a partial state update dict.
"""

import json
import threading
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


def build_nodes(llm, db):
    """Inject shared resources before the graph is compiled."""
    global _llm, _db, _execute_query_tool
    _llm = llm
    _db = db
    _execute_query_tool = QuerySQLDataBaseTool(db=db)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def classify_intent_node(state: AgentState):
    """Classifies the user's question by forcing the LLM to call a specific tool."""
    _send_status("Analysing your question...")
    print("--- Classifying Intent (with Function Calling) ---")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an intent classifier. Call the appropriate tool based on the user's last message.",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    tools = [DatabaseQuery, Conversation, TaskCreation]
    llm_with_tools = _llm.bind_tools(tools)
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
    print(f"Intent: {intent}")
    return {"intent": intent}


def handle_conversation_node(state: AgentState):
    """Creates natural conversation with the user."""
    _send_status("Thinking...")
    print("--- Handling Conversation ---")
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a friendly assistant solves user's database related queries, Diya, for Mr. Satyendra, you refer him as Satyendra Sir. Reply to the user politely with a short relevant relevant response. Reply in English or Hindi based on user's question. All currencies are in Rupees until mentioned other wise. Greet user according to current time, i.e., 'Good Morning', 'Good Evening', etc. when needed. Don't just greet on every response. Show the units when needed.",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    tools = [get_current_datetime]
    agent_runnable = create_openai_functions_agent(_llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent_runnable, tools=tools, verbose=True)
    result = agent_executor.invoke(
        {"question": state["question"], "chat_history": state.get("chat_history", [])}
    )
    print(f"Final Answer: {result['output']}")
    return {"answer": result["output"]}


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
    - **IMPORTANT:** Add comments in the SQL query to explain your logic where necessary.
    - **IMPORTANT:** Only return the SQL query. Do not add any other text or explanation.
    - **IMPORTANT:** If a table or column name contains a space or is a reserved keyword, you MUST wrap it in double quotes. For example: "Task Description".
    - **IMPORTANT:** Use the columns provided in the schema, if user mention a column that is not in schema, try to find the closest relevant column in the schema.
    - **IMPORTANT:** "PO Pending" or "Pending PO" mean orders that are pending. just "PO" means get data from PO pending table.
    """

    retries = state.get("retries") or 0
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
    runnable = prompt | _llm
    raw_query = runnable.invoke(
        {
            "question": state["question"],
            "chat_history": state.get("chat_history", []),
            "schema": _db.get_table_info(),
            "error": result_text,
        }
    ).content
    sql_query = raw_query.strip().replace("```sql", "").replace("```", "").strip()
    print(f"Generated Query: {sql_query}")
    return {"query": sql_query, "retries": int(retries) + 1}


def execute_query_node(state: AgentState):
    """Executes the SQL query and returns the result."""
    _send_status("Fetching data from database...")
    print("--- Executing SQL Query ---")
    query = state["query"]
    result = _execute_query_tool.invoke(query)
    print(f"Query Result: {result}")
    return {"result": result}


def summarize_result_node(state: AgentState):
    """Takes the query result and creates a natural language answer."""
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
    runnable = prompt | _llm
    invoke_kwargs = {
        "question": state["question"],
        "query": state["query"],
        "result": state["result"],
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
