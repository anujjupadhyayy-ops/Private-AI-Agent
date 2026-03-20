# Tech Stack — Prerequisite Understanding

> *"Before you look at any of the code in this repo, read this. I spent two weeks understanding and building every layer."*
> 
> — Anuj Upadhyay, March 2026 · Infra - Apple Silicon (M4) · Local AI Agent (Privacy & Customisation focused)

---

## Why This Document Exists

I built this because I wanted to understand each layer involved in building an AI agent. I wanted to move beyond simply calling the "OpenAI API" level; I believe to truly build / manage something you need to understand how it works, for me it was to understand each layer involved from infrastructure level to the application level. 
What runs the model? How does it find relevant information? How do tools get called? How does memory work? How does a chat interface become a native app?

Every technology in this stack was chosen deliberately. Not because it was the most popular, but to build something using that is available in the market to learners like me, and understand the impact of it in real time, that's how we can best learn. This document explains each one — what it is, what problem it solves, why I chose it over the alternatives, and most importantly, when you should and shouldn't use it.

---

## The Stack at a Glance

```
🖥️  Tauri             — Native Mac dock app wrapper
        ↕
💬  Streamlit         — Chat interface (localhost:8501)
        ↕
⚡  LangGraph         — Agent loop (ReAct: reason → act → observe → repeat)
        ↕
🔥  Ollama + Mistral  — Local AI model (no internet, no API key)
        ↕
🔧  Tools             — search_web, query_knowledge, query_excel, fetch_from_api...
        ↕
🔮  ChromaDB          — Vector knowledge base (your documents as searchable meaning)
        ↕
🗄️  PostgreSQL        — Memory, audit trail, users, every action logged
```

---

## 1. Ollama — The Brain

**Layer: Local AI inference · No API key · Apple Silicon optimised**

When people say they're "using AI", they usually mean they're sending text to a server somewhere — OpenAI's, Anthropic's, Google's. The model runs on their hardware, their costs, their terms. You're renting intelligence.

Ollama is different. It's a local server that downloads open-source AI models and runs them entirely on your own hardware. It starts when your Mac starts, sits quietly in the menu bar, and exposes a simple API at `localhost:11434`. When your agent needs to think, it sends a request to that local address. The model runs on your processor. No data leaves your system, no cost to run an agent. 

Ollama is like running your own private OpenAI server on your Mac. Same concept — you send it a message, it sends back a response. The difference is it never leaves your machine.

For my setup I explored different reasoning and embedding models — Mistral 7B, LLaMA 3.1/LLaMA 3.2. These are small size LLMs so come with their own limitations, but the fact that they run locally with zero setup is a game-changer for personal AI agents. The trade-off is that they don't have the same reasoning quality as GPT-4o or Claude 3.5 Sonnet — but for many use cases, especially when privacy is a concern, it's worth it.

**Use Ollama when:** Privacy is non-negotiable. Legal documents, personal finances, anything you wouldn't paste into ChatGPT. Medical records. Client data. Anything under NDA.

You can also use Claude or GPT models with Ollama if you have API keys, but the point of Ollama is to avoid that dependency. The models I used in this project are all open-source and run entirely locally.

**What Ollama does in this project:**
- `mistral` — the main reasoning model. Reads your questions, decides which tools to call, writes the final response
- `nomic-embed-text` — the embedding model. Converts document text into vectors for ChromaDB. A completely different job from reasoning — this model never generates text, it only creates mathematical representations of meaning

---

## 2. LangGraph — The Conductor

**Layer: Agent framework · ReAct loop · Tool orchestration**

A language model on its own is a text transformer. You give it text, it gives you text back. It has no memory, no tools, no ability to take actions in the world. That's not an agent — that's autocomplete with a big vocabulary.

LangGraph is what turns a language model into an agent. It implements the ReAct pattern — **Re**ason, **Act**, Observe, repeat. The agent reads your message, reasons about what it needs to do, picks a tool to call, calls it, reads the result, reasons again about whether that was enough, and either calls another tool or gives you the final answer.

> **The ReAct loop in plain English:**
> 
> You ask: *"What did I spend on Hospital bills?"*
> 
> Agent thinks: *"This is a financial question about an Excel file. I should call query_excel."*
> 
> Agent calls: `query_excel("Medical_Expenses.xlsx", "Hospital")`
> 
> Agent reads result: *[gets back the raw cell data from the spreadsheet]*
> 
> Agent thinks: *"I have the data. I can answer now."*
> 
> Agent responds: *"The total spent on Hospital bills was ₹95,530..."*

The `create_react_agent` function in LangGraph handles all of this. You hand it the model, the list of tools, and a system prompt. It manages the loop, the tool call formatting, the context window, and the message history internally. Without it, you'd write several hundred lines of state management code to achieve the same thing.

**Use LangGraph when:**
- You need an agent that can call multiple tools in sequence based on what it finds
- You want model swap-ability — change the underlying model without rewriting agent logic
- You need conversation memory managed cleanly alongside tool calling
- You're building anything more complex than a simple chatbot

---

## 3. ChromaDB — The Knowledge Base

**Layer: Vector database · Semantic search · Local persistent**

A regular database stores text as text. If you search for "payment terms" it finds rows containing those exact words. Useful — but limited. What if the document says "when funds are due" instead? A keyword search misses it entirely.

ChromaDB is a vector database. Instead of storing text as text, it stores text as vectors/chunks — lists of numbers (usually 768 of them) that represent the *meaning* of the text in mathematical space. Two pieces of text with similar meaning have vectors that are close together in that space, even if they share no words. ChromaDB finds meaning, not keywords.

> **The analogy that actually makes sense:** Imagine a library where every book is filed not by title or author, but by what it *means*. All books about heartbreak are shelved near each other, regardless of genre, language, or publication date. ChromaDB is that library. Your questions and your documents are all filed by meaning — so the search always finds what's relevant, not just what matches.

In this project, ChromaDB stores three separate collections — `personal_docs`, `finance_docs`, and `work_docs`. This domain separation is critical. Without it, asking about your CV might surface financial report content because the words "experience" and "performance" appear in both. Separate collections eliminate that cross-contamination.

**ChromaDB strengths:** Zero setup. Runs as a library, persists to a folder on disk. Perfect for local apps. Fast for collections under a few million documents. Simple Python API.

---

## 4. RAG — The Most Important Concept

**Not a tool — a pattern. The most important concept in applied AI right now.**

RAG is not a library or a tool — it's a pattern. It is one of the core concepts of creating an AI Agent and how an agent thinks. Without RAG, your agent might have the best model in the world, but it will still hallucinate answers to questions about your specific documents. With RAG, you can ground the model's responses in real data.

The problem RAG solves: language models are trained on data up to a certain date, and they've never seen your specific documents. When you ask a question about those documents, the model has to guess based on patterns it learned during training. It might get lucky and generate something that sounds plausible, but it's not actually reading your documents — it's making an educated guess based on its training data. That's hallucination.

RAG solves this by finding the relevant parts of your documents *before* asking the model the question, and injecting them into the prompt. The model isn't guessing anymore — it's reading the actual source material and summarising it.

> **What actually happens when you ask a RAG-powered question:**
> 
> 1. Your question is converted to a vector using the same embedding model
> 2. ChromaDB finds the 4 most semantically similar chunks from your documents
> 3. Those chunks are injected into the prompt: *"Given this context: [chunk 1] [chunk 2]... answer this question: [your question]"*
> 4. The model reads the actual context and answers based on it
> 5. The answer is grounded in your real data — not generated from thin air

The quality of a RAG system depends on three things: the quality of the embedding model (how well it understands meaning), the chunking strategy (how you split documents before storing them), and the domain separation (making sure you only search relevant collections).
---

## 5. FastAPI — The API Layer

**Layer: HTTP interface · REST endpoints · Separation of concerns**

FastAPI is the bridge between your Python agent and the outside world. FastAPI creates a layer that exposes your agent as HTTP endpoints. `POST /chat` — send a message, get a response. `GET /history` — retrieve conversation history. Any application that can make HTTP requests can now use your agent, regardless of what language it's written in. 

> **Why this matters architecturally:**
> 
> Separating the agent from the UI is one of the most important architectural decisions you can make.
> 
> - **Streamlit is replaced by a React app?** The agent doesn't change.
> - **You add a mobile app?** It calls the same FastAPI endpoints.
> - **A colleague wants to integrate your agent?** Give them the API URL and endpoint docs.
> 
> Without this separation, every new interface requires touching the agent code. With it, interfaces are plug-and-play.

FastAPI was chosen over Flask because it's faster, has automatic API documentation built in, and handles async operations natively — important when your agent is making multiple tool calls that could run in parallel.

**FastAPI becomes essential when:**
- You want multiple UIs connecting to the same agent
- You need other services or applications to call your agent programmatically
- You're moving toward multi-user deployment on a server
- You want rate limiting, authentication headers, or request logging at the HTTP layer

---

## 6. Streamlit — The Interface

**Layer: Python UI · Rapid prototyping · No frontend skills needed**

Building a frontend is a completely separate skill; With my limited coding experience (can envision / design systems), creating a fullblown frontend would have been a significant challenge. Streamlit eliminates that entirely — you write Python code that describes your interface, and Streamlit renders it as a web app.

The real power of Streamlit for this project was speed. The entire chat interface — including login, sidebar, voice button, clear conversation, logout — took a few hours to build. With a traditional frontend that would have been several days minimum.

> **The honest limitation:** Streamlit is a prototyping tool, not a production UI framework. You have limited control over styling, animations, and layout. If you want a polished product that looks like a real application rather than a data science dashboard, you'll eventually replace Streamlit with a proper frontend (React, Vue, or plain HTML/CSS/JS served by FastAPI). The agent code doesn't change — only the interface changes. That's the payoff of the FastAPI separation.

**Streamlit was right for my project because:**
- I needed a working UI quickly to test my agent before worrying about polish
- I wanted to verify the tools, db, APIs, LLM interaction, etc were working as intended before investing time in a frontend refinement. 

---

## 7. Tauri — The Native Shell

**Layer: Native Mac app · Rust · WebKit · ~15MB bundle**

Streamlit runs in a browser tab. That's fine technically, but it doesn't feel like a real application — it feels like a website. No dock icon, no Cmd+Tab, no proper app menu. For a tool you use every day, that friction matters.

Tauri solves this by wrapping your existing web interface in a native Mac window. It doesn't replace your Streamlit app — it creates a shell around it. The window opens at `localhost:8501` where Streamlit is running. From the outside, it looks and behaves like a real Mac application. Dock icon. Cmd+Tab. Native window controls.

The reason Tauri was chosen over Electron (used by VS Code, Slack, Figma) comes down to one thing: size and performance on Apple Silicon. Electron bundles an entire copy of Chrome — about 150MB minimum. Tauri uses macOS's built-in WebKit engine (the same one Safari uses) — already installed on every Mac. The resulting app is around 15MB and starts in under a second.

> **The picture frame analogy:** Tauri is a picture frame. The painting (your AI agent, your Streamlit UI, your tools, your database) doesn't change at all when you add the frame. You're just giving it a proper home to hang on the wall. The frame is native Mac. The painting is your Python stack.

| | Tauri | Electron |
|---|---|---|
| App size | ~15MB | ~150MB+ |
| Engine | macOS WebKit (Safari) | Bundled Chromium |
| Platforms | Mac/Windows/Linux | Mac/Windows/Linux |
| Startup | Under 1 second | 2-3 seconds |
| Best for | Mac-first personal apps | Cross-platform enterprise apps |

---

## 8. PostgreSQL — The Memory

**Layer: Relational database · Persistent memory · Audit trail · Multi-user**

The agent needs to remember conversations. Every message you send and every AI response needs to survive app restarts. Every tool call needs to be logged for audit purposes. Every user account needs to be stored securely. This is what a database is for.

The project started with SQLite — a database that is literally a single file on disk. Zero setup, built into Python, works perfectly for one user on one machine. As the project grew to include multi-user authentication, Docker deployment, and concurrent access, SQLite hit its ceiling. One file can only handle one writer at a time — fine for personal use, problematic for anything shared.

PostgreSQL is what you migrate to when SQLite isn't enough. It runs as a proper server process, handles multiple concurrent connections cleanly, has proper user authentication, and scales to millions of rows without performance degradation.

The migration from SQLite to PostgreSQL in this project changed one connection string. Nothing else. That's because the table schema was designed in standard SQL from day one.

Five tables — `messages`, `tool_calls`, `web_log`, `file_log`, `users`. Every conversation, every tool invocation, every web search, every file operation, every login. All of it queryable. Open DB Browser, connect to the database, and you can see exactly what the AI did at any moment in time. That transparency is not accidental — it was designed in from the start.

**The database design philosophy in this project:**
- **Audit by design** — every meaningful action is logged before it completes, not after
- **Standard SQL only** — no database-specific syntax, migrations are trivial
- **Session isolation** — every row tagged with session_id, users never see each other's data
- **Never store secrets as plain text** — passwords are bcrypt hashed before storage

---

## Integration - Bringing It All Together

Understanding each technology individually is important to understand why you are doing something and its role in the overall architecture you are building. Understanding how they work together is what actually matters. Here's a small example of how a user question flows through the entire stack:

**You ask:** *"What did I spend on XYZ Hospital?"*

| Step | Layer | What happens |
|---|---|---|
| 1 | **Streamlit** | Captures your input. Calls `save_msg("user", prompt)` — message written to PostgreSQL immediately, before anything else |
| 2 | **PostgreSQL** | `run_agent()` loads your last 15 messages — this is how the agent knows the context of your conversation |
| 3 | **LangGraph + Ollama** | Full message history + SYSTEM_PROMPT sent to Mistral/Llama 3.1/ 3,2 model. Model reads the rules and decides: *"Financial question — call query_excel"* |
| 4 | **Tools + PostgreSQL** | `query_excel()` reads the Excel file, returns raw cell coordinates and values. Tool call logged to `tool_calls` table |
| 5 | **Ollama** | Raw data fed back to Mistral. Model identifies XYZ Hospital rows, sums amounts, writes natural language response |
| 6 | **Streamlit + PostgreSQL** | Response rendered in chat bubble. `save_msg("assistant", response)` writes to PostgreSQL. Conversation permanently stored |

Every layer had a reason to exist. Ollama so the model runs locally. LangGraph so the reasoning loop is managed. ChromaDB so documents are semantically searchable. PostgreSQL so nothing is lost, each action is auditable, multiuser sessions are seperate and there is no spill between two conversations. Streamlit so there's an interface so I could get a quick frontend. Tauri so the interface feels native.

---

*"The idea to use AI agents confidently to build business applications / agents requires understanding each layer, its purpose, and how they interact. To drive efficiency and look at tech choices not from a "what's popular" perspective but from a "what's right for this specific use case" perspective, you need to understand the tradeoffs of each layer and how they impact the overall system. This is what I aimed to achieve with this project."*

*— Anuj Upadhyay · March 2026*
