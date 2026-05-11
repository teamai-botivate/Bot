"""
FastAPI application entry point.

Start the server:
    uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_openai import ChatOpenAI

from .core.config import settings
from .db import db
from .agent import build_agent
from .agent.nodes import set_aux_llms
from .api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the agent once at startup and store it in app.state."""
    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        api_key=settings.OPENAI_API_KEY,
        streaming=True,
    )
    fast_llm = ChatOpenAI(
        model=settings.FAST_LLM_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        streaming=True,
    )
    # SQL generation never streams tokens to the user — non-streaming avoids SSE overhead.
    # max_tokens caps output to prevent runaway verbose queries.
    sql_llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        streaming=False,
        max_tokens=1000,
    )
    set_aux_llms(intent_llm=fast_llm, summary_llm=fast_llm, sql_llm=sql_llm)
    app.state.agent = build_agent(llm, db)
    print("✅  Botivate AI agent compiled and ready.")
    yield
    # (optional teardown here)


app = FastAPI(title="Botivate RAG Agent API", lifespan=lifespan)

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(router)
@app.get("/")
async def serve_frontend():
    """Serve the frontend from the same origin."""
    return FileResponse(
        FRONTEND_DIR / "index.html",
        headers={"Cache-Control": "no-store"},
    )



@app.head("/")
async def status_check():
    """Health-check used by load-balancers / uptime monitors."""
    return Response(status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok"}
