"""
FastAPI backend for TailorTalk Google Drive AI Assistant.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env file
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate config and pre-build graph."""
    logger.info("Starting TailorTalk backend...")

    missing = []
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        missing.append("GEMINI_API_KEY or OPENAI_API_KEY")
    if not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and not os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"):
        missing.append("GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE")

    if missing:
        logger.warning("Missing environment variables: %s", ", ".join(missing))
    else:
        # Pre-warm the graph
        from agent import get_graph
        get_graph()
        logger.info("LangGraph agent compiled and ready.")

    yield
    logger.info("Shutting down TailorTalk backend.")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TailorTalk Drive Assistant API",
    description="Conversational AI agent for Google Drive file search",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    reply: str
    error: Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "TailorTalk Drive Assistant API is running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint for deployment platforms."""
    checks = {
        "api": "ok",
        "llm_key": "ok" if (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")) else "missing",
        "drive_credentials": "ok" if (
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        ) else "missing",
        "folder_id": os.getenv("GOOGLE_DRIVE_FOLDER_ID", "not set"),
    }
    status = "healthy" if all(v == "ok" for k, v in checks.items() if k != "folder_id") else "degraded"
    return {"status": status, "checks": checks}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Accepts a message and conversation history,
    returns the agent's reply.
    """
    try:
        from agent import run_agent

        history = [{"role": m.role, "content": m.content} for m in request.history]
        reply = run_agent(request.message, history)
        return ChatResponse(reply=reply)

    except ValueError as e:
        logger.error("Configuration error: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Agent error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/reset")
async def reset():
    """Endpoint to signal conversation reset (history is managed client-side)."""
    return {"status": "ok", "message": "Conversation reset. Start a new chat!"}
