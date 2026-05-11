"""
API route definitions.
The compiled agent is injected via app.state at startup (see main.py).
"""

import asyncio
import json
import threading
from collections import deque
from statistics import median
from time import perf_counter

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from ..schemas import ChatRequest, ChatResponse
from ..agent.nodes import _current_stream, _current_stream_lock

router = APIRouter()
_latency_lock = threading.Lock()
_stream_latency_ms = deque(maxlen=200)
_chat_latency_ms = deque(maxlen=200)
_stream_req_count = 0
_chat_req_count = 0


def _percentile(values, p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((len(s) - 1) * p))))
    return float(s[idx])


def _record_latency(kind: str, elapsed_ms: float) -> None:
    global _stream_req_count, _chat_req_count
    with _latency_lock:
        if kind == "stream":
            _stream_latency_ms.append(elapsed_ms)
            _stream_req_count += 1
            values = list(_stream_latency_ms)
            n = _stream_req_count
            label = "/chat/stream"
        else:
            _chat_latency_ms.append(elapsed_ms)
            _chat_req_count += 1
            values = list(_chat_latency_ms)
            n = _chat_req_count
            label = "/chat"
    if n % 5 == 0:
        p50 = _percentile(values, 0.50)
        p95 = _percentile(values, 0.95)
        print(f"[LATENCY] {label} rolling n={len(values)} p50={p50:.1f}ms p95={p95:.1f}ms")


def _build_history_messages(chat_history):
    """Convert plain dicts to LangChain message objects."""
    history_messages = []
    for msg in chat_history:
        if msg.get("type") == "human":
            history_messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("type") == "ai":
            history_messages.append(AIMessage(content=msg.get("content", "")))
    return history_messages


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: Request, body: ChatRequest):
    """
    Main chat endpoint.
    Accepts a user question and rolling conversation history,
    invokes the LangGraph agent, and returns the answer.
    """
    agent = request.app.state.agent

    history_messages = _build_history_messages(body.chat_history)

    initial_state = {
        "question": body.question,
        "chat_history": history_messages,
        "query": "",
        "result": "",
        "retries": 0,
        "task_details": {},
        "answer": "",
        "intent": "",
    }

    started_at = perf_counter()
    final_state = agent.invoke(initial_state)
    elapsed_ms = (perf_counter() - started_at) * 1000
    print(f"[TIMING] /chat total={elapsed_ms:.1f}ms")
    _record_latency("chat", elapsed_ms)

    return ChatResponse(
        answer=final_state.get("answer", "Sorry, I encountered an error.")
    )


@router.post("/chat/stream")
async def chat_with_agent_stream(request: Request, body: ChatRequest):
    """Stream the final answer token-by-token using Server-Sent Events."""
    agent = request.app.state.agent
    history_messages = _build_history_messages(body.chat_history)

    initial_state = {
        "question": body.question,
        "chat_history": history_messages,
        "query": "",
        "result": "",
        "retries": 0,
        "task_details": {},
        "answer": "",
        "intent": "",
    }

    async def event_stream():
        loop = asyncio.get_running_loop()
        token_q: asyncio.Queue = asyncio.Queue()
        started_at = perf_counter()

        def put_token(token: str) -> None:
            loop.call_soon_threadsafe(token_q.put_nowait, token)

        def put_status(msg: str) -> None:
            loop.call_soon_threadsafe(token_q.put_nowait, {"status": msg})

        def _run():
            # Register callbacks for the active streaming request.
            with _current_stream_lock:
                _current_stream["token"] = put_token
                _current_stream["status"] = put_status
            try:
                return agent.invoke(initial_state)
            finally:
                with _current_stream_lock:
                    _current_stream["token"] = None
                    _current_stream["status"] = None
                # Always send the sentinel so the queue reader can exit.
                loop.call_soon_threadsafe(token_q.put_nowait, None)

        agent_future = loop.run_in_executor(None, _run)
        streamed = False

        try:
            while True:
                item = await token_q.get()
                if item is None:  # sentinel — agent finished
                    break
                if isinstance(item, dict):  # status message from a node
                    yield f"data: {json.dumps(item)}\n\n"
                else:  # token string from runnable.stream()
                    streamed = True
                    yield f"data: {json.dumps({'chunk': item})}\n\n"

            result = await agent_future
            if not streamed and isinstance(result, dict):
                answer = result.get("answer", "")
                if answer:
                    yield f"data: {json.dumps({'chunk': answer})}\n\n"

        except Exception as exc:
            print(f"[stream] error: {exc!r}")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        finally:
            elapsed_ms = (perf_counter() - started_at) * 1000
            print(f"[TIMING] /chat/stream total={elapsed_ms:.1f}ms")
            _record_latency("stream", elapsed_ms)
            yield f"data: {json.dumps({'done': True})}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=headers,
    )
