"""
API route definitions.
The compiled agent is injected via app.state at startup (see main.py).
"""

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from ..schemas import ChatRequest, ChatResponse
from ..agent.nodes import _current_stream, _current_stream_lock

router = APIRouter()


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

    final_state = agent.invoke(initial_state)

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
