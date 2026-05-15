# 🗂️ TailorTalk — Google Drive AI Assistant

A conversational AI agent that helps users search, filter, and discover files within a designated Google Drive folder using natural language.

---

## 📐 Architecture

```
User (Browser)
     │
     ▼
┌─────────────────────┐
│  Streamlit Frontend  │  (Streamlit Cloud)
│     frontend/app.py  │
└──────────┬──────────┘
           │  HTTP POST /chat
           ▼
┌─────────────────────┐
│  FastAPI Backend     │  (Railway / Render)
│   backend/main.py    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  LangGraph Agent     │
│   backend/agent.py   │
│                      │
│  ┌────────────────┐  │
│  │  Gemini LLM    │  │
│  │ (tool calling) │  │
│  └───────┬────────┘  │
│          │           │
│  ┌───────▼────────┐  │
│  │ DriveSearchTool│  │
│  │ drive_tool.py  │  │
│  └───────┬────────┘  │
└──────────┼──────────┘
           │
           ▼
┌─────────────────────┐
│  Google Drive API   │
│   files.list + q    │
│  (Service Account)  │
└─────────────────────┘
```

**Key design decisions:**
- LangGraph handles agent reasoning loop (agent → tools → agent → END)
- The LLM translates natural language into Drive API `q` parameter strings via tool calling
- Conversation history is stored client-side in Streamlit session state and passed on every request (stateless backend)

---

## 🚀 Quick Start (Local)

### Prerequisites
- Python 3.11+
- A Google Cloud project with Drive API enabled
- A Service Account with Drive access
- Gemini API key (free at https://aistudio.google.com)

---

### Step 1 — Google Drive Setup

1. **Copy the sample folder** to your Google Drive:  
   https://drive.google.com/drive/folders/1qkx58doSeYrcLjHPDysJyVJ36PsSqqlt  
   → Right-click → "Make a copy" (note the new folder ID from its URL)

2. **Create a Google Cloud Service Account:**
   - Go to https://console.cloud.google.com
   - Create a new project (or use existing)
   - Enable **Google Drive API**: APIs & Services → Enable APIs → search "Drive API"
   - Go to IAM & Admin → Service Accounts → Create Service Account
   - Name it (e.g. `tailortalk-drive`), click Create
   - Skip role assignment, click Done
   - Click the service account → Keys tab → Add Key → JSON
   - Download the JSON file

3. **Share the Drive folder with the service account:**
   - Open your copied Drive folder
   - Click Share
   - Paste the service account email (looks like `name@project.iam.gserviceaccount.com`)
   - Give **Viewer** access

---

### Step 2 — Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Paste the entire contents of your service account JSON as one line
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}

# The folder ID from your copied Drive folder URL
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here

# Your Gemini API key
GEMINI_API_KEY=your_gemini_key_here
```

> **Tip for GOOGLE_SERVICE_ACCOUNT_JSON:** Open the downloaded JSON, select all, and paste it as a single line. Or set `GOOGLE_SERVICE_ACCOUNT_FILE=path/to/service_account.json` instead.

Start the backend:

```bash
uvicorn main:app --reload --port 8000
```

Visit http://localhost:8000/docs to confirm it's working.

---

### Step 3 — Frontend Setup

```bash
cd frontend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```env
BACKEND_URL=http://localhost:8000
```

Start Streamlit:

```bash
streamlit run app.py
```

Visit http://localhost:8501 🎉

---

## ☁️ Deployment

### Backend → Railway (recommended)

1. Push the `backend/` folder to a GitHub repo
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Select your repo
4. Add these environment variables in Railway dashboard:
   - `GEMINI_API_KEY` = your key
   - `GOOGLE_SERVICE_ACCOUNT_JSON` = full JSON content (one line)
   - `GOOGLE_DRIVE_FOLDER_ID` = your folder ID
5. Railway auto-detects Python and uses `railway.toml` start command
6. Copy the deployed URL (e.g. `https://tailortalk-backend.up.railway.app`)

### Backend → Render (alternative)

1. Push `backend/` to GitHub
2. New Web Service at https://render.com
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add the same 3 environment variables
6. Deploy and copy URL

### Frontend → Streamlit Cloud

1. Push the entire repo (or just `frontend/`) to GitHub
2. Go to https://share.streamlit.io → New app
3. Select repo and set **Main file path** to `frontend/app.py`
4. Under **Advanced settings → Secrets**, add:
   ```toml
   BACKEND_URL = "https://your-backend.up.railway.app"
   ```
5. Deploy → get your public Streamlit URL ✅

---

## 🧪 Example Queries

| User says | Drive query generated |
|---|---|
| "Find all PDF files" | `mimeType = 'application/pdf' and trashed = false` |
| "Show me spreadsheets about budget" | `name contains 'budget' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false` |
| "Files modified this week" | `modifiedTime > '2025-01-08T00:00:00' and trashed = false` |
| "Documents containing 'invoice'" | `fullText contains 'invoice' and trashed = false` |
| "Find the Q3 financial report PDF" | `name contains 'Q3' and name contains 'financial' and mimeType = 'application/pdf' and trashed = false` |
| "Show me all images" | `mimeType contains 'image/' and trashed = false` |

---

## 📁 Project Structure

```
tailortalk/
├── backend/
│   ├── main.py          # FastAPI app, /chat endpoint
│   ├── agent.py         # LangGraph agent (StateGraph)
│   ├── drive_tool.py    # DriveSearchTool + Drive API client
│   ├── requirements.txt
│   ├── railway.toml     # Railway deployment config
│   ├── render.yaml      # Render deployment config
│   └── .env.example
├── frontend/
│   ├── app.py           # Streamlit chat UI
│   ├── requirements.txt
│   └── .streamlit/
│       ├── config.toml  # Dark theme config
│       └── secrets.toml.example
├── .gitignore
└── README.md
```

---

## 🔧 Environment Variables Reference

### Backend

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes* | Google Gemini API key |
| `OPENAI_API_KEY` | Yes* | OpenAI API key (alternative to Gemini) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes** | Service account JSON as string |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Yes** | Path to service account JSON file |
| `GOOGLE_DRIVE_FOLDER_ID` | Recommended | Drive folder ID to search within |

*One of Gemini or OpenAI required  
**One of JSON string or file path required

### Frontend

| Variable | Required | Description |
|---|---|---|
| `BACKEND_URL` | Yes | Full URL to the FastAPI backend |

---

## 🛠️ How It Works

1. User types a message in Streamlit chat
2. Frontend sends `POST /chat` with message + full conversation history
3. FastAPI passes it to the LangGraph agent
4. **LangGraph agent loop:**
   - LLM receives system prompt + conversation history
   - LLM decides to call `drive_search` tool with a `q` parameter string
   - `ToolNode` executes the Drive API `files.list` call
   - LLM receives results and formulates a natural language response
   - If no tool call is needed (follow-up conversation), LLM responds directly
5. Response sent back to Streamlit and displayed in chat

The `q` parameter is built by the LLM itself — it's prompted with Drive API query syntax and translates user intent into valid queries like `name contains 'report' and mimeType = 'application/pdf' and trashed = false`.
