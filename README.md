# Botivate AI

> A conversational AI assistant backed by LangGraph + GPT-4 that answers database queries, generates SQL reports, and creates tasks — served through a clean FastAPI backend and a pure HTML/CSS/JS frontend.

---

## Project Structure

```
botivate-ai/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              ← FastAPI app factory + lifespan
│   │   ├── db.py                ← SQLAlchemy engine + LangChain SQLDatabase
│   │   ├── schemas.py           ← Pydantic request / response models
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes.py        ← POST /chat  endpoint
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py        ← All env vars in one place (Settings class)
│   │   └── agent/
│   │       ├── __init__.py
│   │       ├── state.py         ← AgentState TypedDict + intent Pydantic models
│   │       ├── tools.py         ← Custom LangChain @tool functions
│   │       ├── nodes.py         ← All LangGraph node functions
│   │       ├── edges.py         ← Conditional edge / routing functions
│   │       └── graph.py         ← StateGraph compilation  (build_agent)
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── index.html               ← Semantic HTML shell
│   ├── css/
│   │   └── style.css            ← All styles
│   └── js/
│       ├── config.js            ← API URL + constants (edit here for deploy)
│       ├── ui.js                ← DOM helpers (addMessage, buildChatHistory…)
│       ├── api.js               ← fetch wrapper for the backend
│       └── app.js               ← Event wiring + main logic
│
└── README.md
```

---

## Architecture

```
Browser (frontend)
      │  POST /chat  { question, chat_history }
      ▼
FastAPI (backend/app/main.py)
      │
      └─► POST /chat  →  routes.py
                │
                └─► LangGraph Agent (agent/graph.py)
                          │
                    ┌─────▼──────┐
                    │  classify  │  intent: DatabaseQuery | TaskCreation | Conversation
                    └─────┬──────┘
                 ┌────────┼────────────┐
          DB Query    Task Flow    Conversation
                │          │            │
         generate SQL  analyze /    handle_conversation
         execute SQL   followup /   (tools: datetime)
         summarize     create_task
                │
              answer
                │
      ◄─────────────── JSON { "answer": "…" }
```

---

## Prerequisites

| Requirement      | Version  |
|-----------------|----------|
| Python          | 3.11 +   |
| PostgreSQL      | 13 +     |
| Node (optional) | any      |

---

## Backend Setup

### 1. Clone & create a virtual environment

```bash
cd botivate-ai/backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
DATABASE_URI=postgresql+psycopg2://user:password@localhost:5432/yourdb
OPENAI_API_KEY=sk-...
```

All available settings:

| Variable          | Required | Default    | Description                                    |
|-------------------|----------|------------|------------------------------------------------|
| `DATABASE_URI`    | ✅ Yes   | —          | Full PostgreSQL connection URI                 |
| `OPENAI_API_KEY`  | ✅ Yes   | —          | Your OpenAI API key                            |
| `LLM_MODEL`       | No       | `gpt-4.1`  | OpenAI model name                              |
| `LLM_TEMPERATURE` | No       | `0`        | LLM temperature (0 = deterministic)            |
| `ALLOWED_ORIGINS` | No       | `*`        | Comma-separated CORS origins                   |

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now live at **http://localhost:8000**

#### Available endpoints

| Method | Path      | Description                     |
|--------|-----------|---------------------------------|
| POST   | `/chat`   | Main chat endpoint              |
| GET    | `/health` | Returns `{"status": "ok"}`      |
| HEAD   | `/`       | Uptime / load-balancer check    |

#### Example request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many pending tasks are in the delegation list?",
    "chat_history": []
  }'
```

---

## Frontend Setup

The frontend is a **static site** — no build step required.

### Option A: Open directly in browser

```
open frontend/index.html
```

> **Note:** Some browsers block `fetch()` from `file://` URLs due to CORS. Use Option B for local dev.

### Option B: Serve with any static server (recommended for local dev)

```bash
# Python (built-in)
cd frontend
python -m http.server 5500

# Or Node live-server
npx live-server frontend --port=5500
```

Then visit **http://localhost:5500**

### Changing the backend URL

Edit **`frontend/js/config.js`**:

```js
const CONFIG = {
    API_BASE_URL: "http://localhost:8000",   // ← change this
    ...
};
```

| Environment    | Value                                |
|----------------|--------------------------------------|
| Local dev      | `"http://localhost:8000"`            |
| Production     | `"https://your-api.yourdomain.com"`  |

---

## Deployment

### Backend (e.g. Railway, Render, Fly.io)

1. Set environment variables (`DATABASE_URI`, `OPENAI_API_KEY`) in the platform dashboard.
2. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set `ALLOWED_ORIGINS` to your frontend's URL.

### Frontend (e.g. Netlify, Vercel, GitHub Pages)

1. Update `API_BASE_URL` in `frontend/js/config.js` to the deployed backend URL.
2. Deploy the `frontend/` folder as a static site — no build step.

---

## Agent Logic

The agent is a [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` with the following nodes:

| Node                   | Responsibility                                              |
|------------------------|-------------------------------------------------------------|
| `classify_intent`      | Routes to DatabaseQuery / TaskCreation / Conversation       |
| `handle_conversation`  | Small talk, greetings, general knowledge                    |
| `generate_query`       | Writes a PostgreSQL query from the user's question          |
| `execute_query`        | Runs the query against the database                         |
| `summarize_result`     | Converts raw SQL results into a readable Markdown answer    |
| `handle_error`         | Apologises gracefully after > 7 failed query retries        |
| `analyze_query`        | Extracts task fields from the conversation                  |
| `ask_followup`         | Asks for missing task fields one at a time                  |
| `create_task`          | Inserts the completed task into `Ai_Tasks` table            |

---

## Adding / Modifying Agent Behaviour

| What you want to change       | File to edit                          |
|-------------------------------|---------------------------------------|
| Intent classification logic   | `backend/app/agent/nodes.py`          |
| SQL generation prompts        | `backend/app/agent/nodes.py`          |
| Routing / retry logic         | `backend/app/agent/edges.py`          |
| Graph topology                | `backend/app/agent/graph.py`          |
| New custom tools               | `backend/app/agent/tools.py`          |
| API request/response schema   | `backend/app/schemas.py`              |
| CORS / env config             | `backend/app/core/config.py`          |
| Frontend API URL              | `frontend/js/config.js`               |
| Frontend UI / styles          | `frontend/css/style.css`              |
| Frontend DOM helpers          | `frontend/js/ui.js`                   |

---

## Troubleshooting

| Symptom                               | Likely cause & fix                                                    |
|---------------------------------------|-----------------------------------------------------------------------|
| `DATABASE_URI is not set`             | Missing `.env` file or env var — copy `.env.example` and fill it in  |
| `CORS error` in browser console       | Add frontend origin to `ALLOWED_ORIGINS` in `.env`                   |
| `fetch` fails from `file://`          | Serve frontend with a local HTTP server (see Option B above)         |
| SQL query keeps failing               | Check `DATABASE_URI`; verify table names match the schema            |
| Task creation silently fails          | Ensure the `Ai_Tasks` table exists with the expected columns         |

---

## License

MIT — free to use and modify.
