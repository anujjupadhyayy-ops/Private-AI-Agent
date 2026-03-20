# 🔒 Private AI Engine

A fully local, privacy-first AI agent built from scratch on Apple Silicon. No cloud. No subscriptions. No data leaving your machine.

## What This Is

A complete AI agent stack built entirely from open-source tools — reasoning model, vector knowledge base, tool system, persistent memory, multi-user authentication, and a native Mac dock app. Every architectural decision was made deliberately, with full understanding of the trade-offs.

This is not a wrapper around someone else's tool. Every layer was built, debugged, and understood.

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| AI Reasoning | Ollama + Mistral 7B / Ollama 3.2 | Local inference, no API key, swappable |
| Agent Framework | LangGraph + LangChain | ReAct loop, tool calling, model abstraction |
| Document Search | ChromaDB + nomic-embed-text | Semantic vector search, local embeddings |
| Memory & Audit | PostgreSQL | Persistent conversations, full audit trail |
| UI | Streamlit | Python-native, rapid iteration |
| Dock App | Tauri | Native Mac .app, WebKit-based, ~15MB |
| Auth | bcrypt | Password hashing, session isolation |
| Containerisation | Docker + docker-compose | Portable deployment |

---

## Architecture

```
User Input
    ↓
Streamlit UI (port 8501)
    ↓
LangGraph Agent (ReAct loop)
    ↓
Tool Registry ──────────────────────────────────────────────
    ├── query_knowledge   → ChromaDB (personal/finance/work domains)
    ├── query_excel       → Direct Excel file parsing
    ├── search_web        → DuckDuckGo (private, no API key)
    ├── fetch_from_api    → PMS REST API (X-API-Key auth)
    ├── create_file       → outputs/ folder
    ├── create_structured_report → formatted reports
    ├── read_file         → private-ai folder (sandboxed)
    ├── list_folder       → private-ai folder (sandboxed)
    └── get_weather       → wttr.in (free, no key)
    ↓
Ollama (localhost:11434) — Mistral 7B
    ↓
PostgreSQL — messages, tool_calls, web_log, file_log, users
```

---

## Features

**Privacy by Design**
- All AI inference runs locally — no OpenAI, no Anthropic, no cloud
- Every web search query logged to audit database before execution
- File system access sandboxed to project folder only
- Private documents never included in web search queries

**Document Intelligence (RAG)**
- Three domain collections: `personal_docs`, `finance_docs`, `work_docs`
- Automatic domain detection from folder structure on ingest
- Supports: PDF, Excel, Word, HTML, Markdown, CSV, JSON, code files, URLs
- nomic-embed-text embeddings via Ollama — no external embedding API

**Multi-User Authentication**
- bcrypt password hashing — deliberately slow, brute-force resistant
- Per-user session isolation — conversation history never crosses users
- Role-based access (admin/user)
- CLI user management tool

**Full Audit Trail**
- Every message stored with timestamp and session ID
- Every tool call logged with inputs and outputs
- Every web search recorded before execution
- Every file operation tracked
- Queryable via DB Browser for SQLite or psql

**Native Mac Dock App**
- Tauri wrapper — uses macOS WebKit, ~15MB app
- macOS Launch Agent for auto-start on login
- No Terminal required for daily use

---

## Project Structure

```
private-ai/
├── app.py              — Streamlit UI with login, chat, voice
├── agent.py            — LangGraph agent, memory, SYSTEM_PROMPT
├── tools.py            — All agent tools (9 tools)
├── ingest.py           — Document ingestion (all file types)
├── db.py               — PostgreSQL connection (single source)
├── setup_db.py         — SQLite schema (local dev)
├── setup_postgres.py   — PostgreSQL schema
├── migrate_to_postgres.py — SQLite → PostgreSQL migration
├── create_user.py      — User management CLI
├── voice.py            — Whisper speech-to-text
├── Dockerfile          — Container definition
├── docker-compose.yml  — Full stack orchestration
├── .dockerignore       — Excludes secrets and data
├── .env.example        — Environment variable template
├── documents/
│   ├── personal/       — CV, travel docs
│   ├── finance/        — Financial reports, expenses
│   └── work/           — Architecture, API docs, session notes
├── outputs/            — Agent-created files
├── vectorstore/        — ChromaDB collections
└── logs/               — Streamlit logs
```

---

## Quick Start

### Prerequisites
- Mac with Apple Silicon (M1/M2/M3/M4)
- Homebrew
- Python 3.12
- Ollama

### Local Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/private-ai.git
cd private-ai

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your values

# Pull AI models
ollama pull mistral
ollama pull nomic-embed-text

# Set up database
python3 setup_db.py

# Create your first user
python3 create_user.py add yourname yourpassword admin

# Start the app
streamlit run app.py
```

### Docker Setup (Full Stack)

```bash
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD at minimum

docker-compose up --build

# Pull models into Ollama container
docker exec -it private-ai-ollama-1 ollama pull mistral
docker exec -it private-ai-ollama-1 ollama pull nomic-embed-text

# Create your first user
docker exec -it private-ai-app-1 python3 create_user.py add yourname yourpassword admin
```

---

## Ingesting Documents

```bash
# Ingest by domain — domain auto-detected from folder
python3 ingest.py documents/personal/your_cv.pdf
python3 ingest.py documents/finance/annual_report.pdf
python3 ingest.py documents/work/architecture.md

# Ingest a web page
python3 ingest.py https://example.com

# Update a document (delete old chunks first)
python3 ingest.py --delete filename.pdf personal_docs
python3 ingest.py documents/personal/filename.pdf
```

---

## User Management

```bash
python3 create_user.py add username password
python3 create_user.py add username password admin
python3 create_user.py list
python3 create_user.py delete username
python3 create_user.py password username newpassword
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# PostgreSQL
POSTGRES_PASSWORD=changeme
POSTGRES_URL=postgresql://privateai_user:changeme@localhost:5432/privateai

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# PMS API (optional — your own application)
PMS_API_KEY=your_key_here
PMS_BASE_URL=http://localhost:3000/api/v1
```

---

## What I Learned

Building this from scratch — not following a tutorial, not using a pre-built tool — taught me:

**Architecture over abstraction** — Understanding why LangGraph sits above Ollama, why ChromaDB is separate from PostgreSQL, why Tauri wraps Streamlit rather than replacing it. Every layer has one job.

**RAG is the most critical piece** — The difference between an AI that hallucinates and one that reasons over your actual data is entirely in the embedding quality, the chunking strategy, and the domain separation. ChromaDB with nomic-embed-text on properly structured domains is a different product from a single undifferentiated collection.

**Models are swappable components** — Not a revelation to engineers, but genuinely understanding it through implementation — changing one line in `agent.py` to swap from LLaMA to Mistral to Gemma — means you're never locked in.

**Small models have real limitations** — 3B and 7B parameter models running locally don't reliably follow complex tool calling instructions. This is a hard constraint, not a configuration problem. Production use requires either larger local models (requires significant hardware) or cloud API models.

**Audit by design** — Every tool call logged before execution. Every web query recorded. Every file operation tracked. This isn't an afterthought — it's the foundation of a trustworthy system.

---

## Known Limitations & Refinement Path

| Limitation | Root Cause | Solution |
|---|---|---|
| Inconsistent tool calling | 7B model size | GPT-4o / Claude 3.5 via API, or llama3.1:70b on GPU hardware |
| Model hallucinates | Same | Better models, stricter SYSTEM_PROMPT, output validation layer |
| Voice not in Docker | ffmpeg path in container | Mount Mac audio device or use cloud STT |
| Single user session ID | Hardcoded "main" for local | S3.2 login system already built — connect session_id to user.id |

---

## Roadmap

- [ ] Connect session_id to authenticated user in local mode
- [ ] Add output validation — reject responses that contain placeholders
- [ ] Upgrade to llama3.1:70b or GPT-4o API for reliable tool calling
- [ ] Add scheduled automations via n8n
- [ ] Add text-to-speech for voice responses (Coqui TTS — local)
- [ ] Multi-tenant isolation for team deployment
- [ ] Stripe billing hooks connected to tool_calls audit table

---

## License

MIT — use it, extend it, build on it.

---

*Built by Anuj Upadhyay — March 2026*
*Apple Silicon M-series · Python 3.12 · LangGraph 1.0 · Ollama 0.18*