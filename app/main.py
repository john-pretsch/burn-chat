import logging
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import config, llm, retrieve, store
from .embed import get_embedder

log = logging.getLogger("burn")
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedder = get_embedder()
    conn = store.connect()
    store.check_embed_model(conn, embedder.model_name, embedder.dim)  # raises on mismatch
    state.update(conn=conn, embedder=embedder, client=anthropic.AsyncAnthropic())
    yield
    conn.close()


app = FastAPI(title="Burn", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=config.MAX_MESSAGE_CHARS)
    model: str | None = None
    effort: str | None = None
    history: list[Turn] = []


@app.get("/healthz")
def healthz():
    n = state["conn"].execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {"ok": True, "chunks": n, "embed_model": state["embedder"].model_name}


@app.get("/api/models")
def models():
    return {
        "default": config.DEFAULT_MODEL,
        "models": [{"id": m, "default_effort": config.DEFAULT_EFFORT.get(m, "medium")} for m in config.ALLOWED_MODELS],
        "efforts": config.EFFORTS,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    model = req.model or config.DEFAULT_MODEL
    if model not in config.ALLOWED_MODELS:
        raise HTTPException(400, "Model not allowed")
    effort = req.effort or config.DEFAULT_EFFORT.get(model, "medium")
    if effort not in config.EFFORTS:
        raise HTTPException(400, "Invalid effort")
    conn = state["conn"]
    if store.spend_today(conn) >= config.DAILY_SPEND_CAP_USD:
        raise HTTPException(429, "Daily spend cap reached; try again tomorrow.")

    history = [t.model_dump() for t in req.history[-config.MAX_HISTORY_TURNS * 2:]]
    while history and history[0]["role"] != "user":
        history.pop(0)
    prior_user = next((t["content"] for t in reversed(history) if t["role"] == "user"), "")
    chunks = retrieve.search(conn, state["embedder"], f"{prior_user}\n{req.message}"[-1500:])

    def on_usage(m, usage):
        usd = llm.cost_usd(m, usage)
        store.add_spend(conn, usd)
        log.info("chat model=%s in=%s out=%s usd=%.5f", m, usage.input_tokens, usage.output_tokens, usd)

    gen = llm.stream_answer(state["client"], model=model, effort=effort, history=history,
                            question=req.message, chunks=chunks, on_usage=on_usage)
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
