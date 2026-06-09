# Botivate AI - Architecture & Deployment

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Browser                              │
│  (Chrome, Firefox, Safari, etc.)                                    │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    HTTP(S) Requests & Responses
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
        ┌───────▼─────────────┐        ┌──────────▼──────────┐
        │  Static Frontend    │        │  FastAPI Backend    │
        │  (Render Static)    │        │  (Render Web)       │
        │                     │        │                     │
        │ • HTML/CSS/JS       │        │ • LangGraph Agent   │
        │ • Responsive UI     │        │ • Chat Endpoints    │
        │ • Auto-detect API   │        │ • Streaming SSE     │
        │ • Load history      │        │ • Health checks     │
        │                     │        │                     │
        │ Hosted at:          │        │ Hosted at:          │
        │ botivate-           │        │ botivate-           │
        │ frontend.onrender   │        │ backend.onrender    │
        │ .com                │        │ .com                │
        └─────────────────────┘        └──────────┬──────────┘
                                                  │
                                     PostgreSQL Protocol
                                                  │
                                    ┌─────────────▼──────────┐
                                    │  Supabase PostgreSQL   │
                                    │  (AWS AP-Northeast-1)  │
                                    │                        │
                                    │ • Tasks database       │
                                    │ • User data            │
                                    │ • Conversation logs    │
                                    │                        │
                                    │ Host: aws-1-ap-        │
                                    │ northeast-1.pooler     │
                                    │ .supabase.com:6543     │
                                    └────────────────────────┘
```

## Request Flow

### 1. Page Load
```
User visits botivate-frontend.onrender.com
    │
    ├─ Download index.html
    ├─ Load CSS styles
    ├─ Load JavaScript (config.js → test-connection.js → ui.js → api.js → app.js)
    │
    └─ JavaScript detects environment:
       • If localhost → API_BASE_URL = "http://localhost:8000"
       • If production → API_BASE_URL = same origin (current domain)
```

### 2. Chat Message Flow
```
User types message and clicks Send
    │
    ├─ Frontend validates input
    ├─ Build payload: { question, chat_history }
    │
    ├─ Choose endpoint:
    │  ├─ /chat (full response at once)
    │  └─ /chat/stream (token-by-token streaming)
    │
    ├─ POST to API_BASE_URL/chat/stream
    │  └─ Headers: { Content-Type: application/json }
    │
    └─ Backend receives request
         │
         ├─ Load chat history messages
         ├─ Build LangGraph state
         ├─ Initialize agent with LLM
         │
         ├─ Agent flow:
         │  1. Classify intent (HR/Inventory/etc)
         │  2. Generate SQL if needed
         │  3. Query database
         │  4. Generate response
         │  5. Stream tokens to frontend
         │
         └─ Stream response via Server-Sent Events
             │
             data: {"status": "Querying database..."}
             data: {"chunk": "We"}
             data: {"chunk": " have"}
             data: {"chunk": " 5"}
             data: {"chunk": " tasks"}
             data: {"done": true}
             │
             └─ Frontend renders response in real-time
```

## File Structure

```
botivate-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── db.py                # Database connection
│   │   ├── schemas.py           # Request/response models
│   │   ├── core/
│   │   │   └── config.py        # Environment configuration
│   │   ├── api/
│   │   │   └── routes.py        # /chat and /chat/stream endpoints
│   │   └── agent/
│   │       ├── __init__.py      # Agent builder
│   │       ├── nodes.py         # LangGraph nodes
│   │       └── runtime_memory.json
│   └── requirements.txt         # Python dependencies
│
├── frontend/
│   ├── index.html               # Main HTML file
│   ├── css/
│   │   └── style.css            # Styling
│   ├── js/
│   │   ├── config.js            # Configuration (API_BASE_URL detection)
│   │   ├── test-connection.js   # Connection test utility
│   │   ├── api.js               # API calls (sendChatMessage, stream)
│   │   ├── ui.js                # UI rendering (buildChatHistory, displayMessage)
│   │   └── app.js               # App initialization
│   └── B PNG (1).png            # Botivate logo
│
├── .git/                        # Git repository
├── .python-version              # Python version specification
├── .gitignore                   # Git ignore rules
│
├── render.yaml                  # Render IaC configuration (optional)
├── Procfile                     # Web service process definition
├── build.sh                     # Build script
│
├── DEPLOYMENT.md                # Full deployment guide
├── RENDER_SETUP.md              # Quick Render setup guide
├── ARCHITECTURE.md              # This file
└── README.md                    # Project README
```

## Environment Configuration

### Local Development (localhost:8000)
```
Frontend Config:
  API_BASE_URL = "http://localhost:8000"
  
Backend Config:
  DATABASE_URI = postgresql://... (from .env)
  OPENAI_API_KEY = sk-proj-... (from .env)
  ALLOWED_ORIGINS = "*"
  LLM_MODEL = gpt-4o
```

### Production (Render)
```
Frontend Config:
  API_BASE_URL = "https://botivate-frontend.onrender.com"
  (Auto-detected as same-origin)
  
Backend Config:
  DATABASE_URI = postgresql://... (from Render env var)
  OPENAI_API_KEY = sk-proj-... (from Render env var)
  ALLOWED_ORIGINS = "*"
  LLM_MODEL = gpt-4o
```

## API Endpoints

### POST /chat
**Single response endpoint**
- Request: `{ question, chat_history }`
- Response: `{ answer }`
- Use when: You want the complete response at once
- Example:
  ```javascript
  const response = await sendChatMessage("What are my tasks?", []);
  console.log(response); // Full answer string
  ```

### POST /chat/stream
**Streaming response endpoint**
- Request: `{ question, chat_history }`
- Response: Server-Sent Events (SSE) stream
- Use when: You want to show tokens as they arrive (better UX)
- Events:
  - `{"status": "message"}` - Progress updates
  - `{"chunk": "token"}` - Response tokens
  - `{"done": true}` - Stream complete
  - `{"error": "message"}` - Error occurred

### GET /health
**Health check endpoint**
- Response: `{ status: "ok" }`
- Use when: Monitoring uptime, debugging connectivity

### GET /
**Root endpoint (Frontend)**
- Response: index.html (served by backend)
- Used when: User visits base URL

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      Frontend (JavaScript)                       │
│                                                                   │
│  1. User Input                                                   │
│     └─ Text message typed into textarea                          │
│                                                                   │
│  2. Build Payload                                                │
│     ├─ question: user's message                                  │
│     └─ chat_history: array of {type, content} objects           │
│                                                                   │
│  3. Choose Method                                                │
│     ├─ await sendChatMessage() → full response                  │
│     └─ await sendChatMessageStream() → tokens                   │
│                                                                   │
│  4. Network Request                                              │
│     ├─ POST /chat or /chat/stream                               │
│     ├─ Headers: Content-Type: application/json                  │
│     └─ Body: JSON payload                                        │
│                                                                   │
│  5. Display Response                                             │
│     ├─ Append message to chat history                           │
│     ├─ Scroll to bottom                                         │
│     └─ Show loading indicator while waiting                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP POST
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│                                                                   │
│  1. Receive Request                                              │
│     ├─ Parse JSON payload                                       │
│     ├─ Validate using ChatRequest schema                        │
│     └─ Extract question and history                             │
│                                                                   │
│  2. Build Agent State                                            │
│     ├─ Convert history to LangChain messages                    │
│     ├─ Initialize state dict                                    │
│     └─ Add question and empty fields                            │
│                                                                   │
│  3. Process with Agent                                           │
│     ├─ Load compiled LangGraph agent                            │
│     ├─ Run state through agent workflow                        │
│     │  ├─ Node 1: Classify intent                               │
│     │  ├─ Node 2: Generate SQL query                            │
│     │  ├─ Node 3: Execute on database                          │
│     │  ├─ Node 4: Generate response                             │
│     │  └─ Stream tokens via callback                            │
│     └─ Return final state                                       │
│                                                                   │
│  4. Stream Response                                              │
│     ├─ For each token: emit `data: {chunk}`                     │
│     ├─ For status updates: emit `data: {status}`                │
│     └─ When done: emit `data: {done: true}`                     │
│                                                                   │
│  5. Return to Client                                             │
│     └─ SSE stream as text/event-stream                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ Server-Sent Events
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Frontend (JavaScript)                       │
│                                                                   │
│  1. Parse Events                                                 │
│     ├─ Read SSE stream line-by-line                             │
│     ├─ Extract JSON from "data:" prefix                         │
│     └─ Handle different payload types                           │
│                                                                   │
│  2. Handle Tokens                                                │
│     ├─ Append chunk to response text                            │
│     ├─ Re-render message                                        │
│     └─ Parse markdown and sanitize HTML                         │
│                                                                   │
│  3. Handle Status Updates                                        │
│     ├─ Show in UI (e.g., "Querying database...")               │
│     ├─ Update latency metrics                                   │
│     └─ Change UI state                                          │
│                                                                   │
│  4. Handle Completion                                            │
│     ├─ Hide loading indicator                                   │
│     ├─ Enable send button                                       │
│     ├─ Log latency metrics                                      │
│     └─ Focus input for next message                             │
│                                                                   │
│  5. Display Final Response                                       │
│     └─ Full markdown-rendered message in chat                  │
└──────────────────────────────────────────────────────────────────┘
```

## Key Features

### Frontend
- ✅ Auto-detects API URL based on environment
- ✅ Responsive chat UI with markdown rendering
- ✅ Message history with conversation context
- ✅ Real-time streaming responses (SSE)
- ✅ Error handling and connection testing
- ✅ Latency metrics and status indicators

### Backend
- ✅ FastAPI with async/await
- ✅ LangGraph agent with multi-step reasoning
- ✅ SQL database integration
- ✅ OpenAI GPT-4 powered responses
- ✅ Server-Sent Events streaming
- ✅ CORS configuration for cross-origin requests
- ✅ Health check endpoints
- ✅ Latency monitoring and logging

### Infrastructure
- ✅ Render-ready with Procfile and render.yaml
- ✅ Environment-based configuration
- ✅ Database connection pooling
- ✅ Proper error handling and logging

## Deployment Checklist

- [ ] Environment variables configured on Render
- [ ] Database connection working
- [ ] Frontend loads and renders
- [ ] Backend health check passes
- [ ] Frontend can reach backend
- [ ] Chat messages process successfully
- [ ] Streaming responses work
- [ ] No CORS errors in browser console
- [ ] Logs show expected messages

---

**Status**: Ready for production deployment! 🚀
