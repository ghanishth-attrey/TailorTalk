"""
TailorTalk - Google Drive AI Assistant
Streamlit frontend
"""

import os
import time
import requests
import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TailorTalk – Drive Assistant",
    page_icon="🗂️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ── Config ─────────────────────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Overall background ─────────────────────────────────────────── */
.stApp {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    min-height: 100vh;
}

/* ── Sidebar ──────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.05) !important;
    border-right: 1px solid rgba(255,255,255,0.1);
}

/* ── Header ─────────────────────────────────────────────────────── */
.tt-header {
    text-align: center;
    padding: 1.5rem 0 0.5rem;
}
.tt-header h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(90deg, #a78bfa, #60a5fa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.tt-header p {
    color: rgba(255,255,255,0.55);
    font-size: 0.95rem;
    margin-top: 0.3rem;
}

/* ── Chat messages ──────────────────────────────────────────────── */
.msg-user {
    display: flex;
    justify-content: flex-end;
    margin: 0.6rem 0;
}
.msg-user .bubble {
    background: linear-gradient(135deg, #7c3aed, #4f46e5);
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 0.75rem 1.1rem;
    max-width: 78%;
    font-size: 0.95rem;
    line-height: 1.5;
    box-shadow: 0 4px 15px rgba(124,58,237,0.35);
}

.msg-assistant {
    display: flex;
    justify-content: flex-start;
    margin: 0.6rem 0;
    gap: 0.6rem;
    align-items: flex-start;
}
.msg-assistant .avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #a78bfa, #60a5fa);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
    flex-shrink: 0;
    margin-top: 2px;
}
.msg-assistant .bubble {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    color: rgba(255,255,255,0.92);
    border-radius: 18px 18px 18px 4px;
    padding: 0.75rem 1.1rem;
    max-width: 78%;
    font-size: 0.95rem;
    line-height: 1.6;
    backdrop-filter: blur(6px);
}

/* ── Typing indicator ────────────────────────────────────────────── */
.typing-dots span {
    display: inline-block;
    width: 7px;
    height: 7px;
    margin: 0 2px;
    background: #a78bfa;
    border-radius: 50%;
    animation: bounce 1.2s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30%            { transform: translateY(-6px); }
}

/* ── Input bar ────────────────────────────────────────────────────── */
.stChatInputContainer > div {
    border: 1px solid rgba(167,139,250,0.4) !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.06) !important;
}

/* ── Suggestion chips ─────────────────────────────────────────────── */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.8rem 0;
}
.chip {
    background: rgba(167,139,250,0.15);
    border: 1px solid rgba(167,139,250,0.4);
    color: #c4b5fd;
    border-radius: 999px;
    padding: 0.35rem 0.85rem;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all 0.2s;
}

/* ── Stats ────────────────────────────────────────────────────────── */
.stat-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 0.8rem 1rem;
    text-align: center;
    color: white;
}
.stat-card .num { font-size: 1.5rem; font-weight: 700; color: #a78bfa; }
.stat-card .lbl { font-size: 0.75rem; color: rgba(255,255,255,0.5); margin-top: 2px; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "total_searches" not in st.session_state:
    st.session_state.total_searches = 0
if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

SUGGESTIONS = [
    "📄 Show me all PDFs",
    "📊 Find spreadsheets",
    "🔍 Search for 'report'",
    "🖼️ List all images",
    "📅 Files modified this month",
    "📝 Find Google Docs",
]

WELCOME_MSG = (
    "👋 Hello! I'm **DriveBot**, your Google Drive assistant.\n\n"
    "I'm connected to the following Google Drive folder:\n"
    "📁 [TailorTalk Sample Drive](https://drive.google.com/drive/folders/1qkx58doSeYrcLjHPDysJyVJ36PsSqqlt)\n\n"
    "I can help you **search, filter, and discover files** in this Drive using natural language.\n\n"
    "Try asking me:\n"
    "- *\"Find all PDF files\"*\n"
    "- *\"Show me all folders\"*\n"
    "- *\"Find documents containing the word report\"*\n"
    "- *\"What files were modified last week?\"*\n"
    "- *\"Find all images\"*\n\n"
    "What are you looking for? 🗂️"
)

# ── API call ───────────────────────────────────────────────────────────────────
def call_backend(user_msg: str) -> str:
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]
    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat",
            json={"message": user_msg, "history": history},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["reply"]
    except requests.exceptions.ConnectionError:
        return (
            "⚠️ **Cannot connect to the backend.** "
            f"Make sure the FastAPI server is running at `{BACKEND_URL}`."
        )
    except requests.exceptions.Timeout:
        return "⏳ The request timed out. The Drive API might be slow — please try again."
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("detail", "")
        except Exception:
            pass
        return f"❌ Backend error ({e.response.status_code}): {detail or str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗂️ TailorTalk")
    st.markdown("---")

    # Stats
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""<div class='stat-card'>
                <div class='num'>{len(st.session_state.messages)}</div>
                <div class='lbl'>Messages</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""<div class='stat-card'>
                <div class='num'>{st.session_state.total_searches}</div>
                <div class='lbl'>Searches</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    st.markdown("### 💡 Quick searches")
    for s in SUGGESTIONS:
        if st.button(s, key=f"chip_{s}", use_container_width=True):
            # Strip emoji prefix for cleaner query
            clean = s.split(" ", 1)[1] if s[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" else s
            st.session_state.pending_input = clean

    st.markdown("---")

    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.total_searches = 0
        st.rerun()

    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(
        "Powered by **LangGraph** + **Gemini**\n\n"
        "Uses Google Drive API `files.list` with the `q` query parameter for precise results.",
        unsafe_allow_html=False,
    )

    # Health check
    with st.expander("🔌 Backend status"):
        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=5)
            data = r.json()
            for k, v in data.get("checks", {}).items():
                icon = "✅" if v == "ok" else "⚠️"
                st.text(f"{icon} {k}: {v}")
        except Exception:
            st.error("Cannot reach backend")


# ── Main area ──────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='tt-header'><h1>🗂️ TailorTalk</h1>"
    "<p>Your conversational Google Drive assistant</p></div>",
    unsafe_allow_html=True,
)

# Chat history container
chat_container = st.container()

with chat_container:
    # Welcome message
    if not st.session_state.messages:
        st.markdown(
            f"<div class='msg-assistant'>"
            f"<div class='avatar'>🤖</div>"
            f"<div class='bubble'>{WELCOME_MSG}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Render conversation history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f"<div class='msg-user'><div class='bubble'>{msg['content']}</div></div>",
                unsafe_allow_html=True,
            )
        else:
            # Use st.markdown inside the bubble for proper rendering of links/bold
            col_av, col_bub = st.columns([0.06, 0.94])
            with col_av:
                st.markdown(
                    "<div style='width:36px;height:36px;border-radius:50%;"
                    "background:linear-gradient(135deg,#a78bfa,#60a5fa);"
                    "display:flex;align-items:center;justify-content:center;"
                    "font-size:1.1rem;margin-top:4px;'>🤖</div>",
                    unsafe_allow_html=True,
                )
            with col_bub:
                with st.container(border=True):
                    st.markdown(msg["content"])


# ── Handle pending input from sidebar buttons ──────────────────────────────────
def process_message(user_input: str):
    """Add user message, call backend, append reply."""
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.total_searches += 1

    with st.spinner("DriveBot is thinking..."):
        reply = call_backend(user_input)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()


if st.session_state.pending_input:
    pending = st.session_state.pending_input
    st.session_state.pending_input = None
    process_message(pending)

# ── Chat input ─────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask me to find files... e.g. 'Find PDFs about Q3 report'")
if user_input:
    process_message(user_input)
