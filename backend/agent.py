"""
LangGraph-based conversational agent for Google Drive file search.
Uses tool-calling to translate natural language into Drive API queries.
"""

import os
import logging
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from drive_tool import drive_search

logger = logging.getLogger(__name__)

# ── Tools ──────────────────────────────────────────────────────────────────────
TOOLS = [drive_search]

# ── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are DriveBot, a Google Drive search assistant.

Translate user requests into Google Drive API q parameter strings and call drive_search.

CRITICAL: Always use double quotes " for string values, never single quotes '
Always include trashed = false in every query.

Key mimeTypes:
- PDF: application/pdf
- Google Doc: application/vnd.google-apps.document  
- Google Sheet: application/vnd.google-apps.spreadsheet
- Google Slides: application/vnd.google-apps.presentation
- Folder: application/vnd.google-apps.folder
- Images: mimeType contains "image/"
- Videos: mimeType contains "video/"

Search types:
- Partial name: name contains "keyword"
- Exact name: name = "filename"
- File content: fullText contains "keyword"
- Date: modifiedTime > "2024-01-01T00:00:00"
- Combine with: and

ALWAYS show the complete tool output. Never summarize results.
After results, suggest 1-2 follow-up searches.
If no results, suggest alternatives.
"""
# ── State ──────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# ── LLM setup ─────────────────────────────────────────────────────────────────
def get_llm_with_tools():
    """Return an LLM bound to the drive_search tool."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        from langchain_groq import ChatGroq
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=gemini_key,
            temperature=0.2,
        )
        logger.info("Using Groq LLaMA 3.3 70B")
    elif openai_key:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=openai_key,
            temperature=0.2,
        )
        logger.info("Using GPT-4o-mini")
    else:
        raise ValueError(
            "No LLM API key found. Set GEMINI_API_KEY or OPENAI_API_KEY."
        )

    return llm.bind_tools(TOOLS)


# ── Graph nodes ────────────────────────────────────────────────────────────────
def agent_node(state: AgentState, config: RunnableConfig) -> AgentState:
    """The main LLM reasoning node."""
    llm_with_tools = get_llm_with_tools()
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = llm_with_tools.invoke(messages, config)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """Router: if the last message has tool calls, go to tools; else end."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# ── Build graph ────────────────────────────────────────────────────────────────
def build_graph():
    tool_node = ToolNode(TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# Singleton compiled graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_agent(user_message: str, history: list[dict]) -> str:
    graph = get_graph()

   # Only keep last 6 messages to save tokens
    recent_history = history[-6:] if len(history) > 6 else history

    # Convert history to LangChain messages
    lc_messages: list[BaseMessage] = []
    for msg in recent_history:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))

    lc_messages.append(HumanMessage(content=user_message))

    result = graph.invoke({"messages": lc_messages})

    # Return tool output directly if tool was called
    for msg in reversed(result["messages"]):
        if isinstance(msg, ToolMessage):
            final_ai = result["messages"][-1]
            ai_content = final_ai.content if isinstance(final_ai, AIMessage) else ""
            return f"{msg.content}\n\n{ai_content}" if ai_content else msg.content

    # No tool called, return AI response
    final_message = result["messages"][-1]
    if isinstance(final_message, AIMessage):
        return final_message.content
    return str(final_message.content)