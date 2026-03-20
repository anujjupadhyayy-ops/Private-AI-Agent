# ── IMPORTS ───────────────────────────────────────────────────────────────────

from db import get_conn
# Imports the PostgreSQL connection function from db.py
# Used in load_history() to retrieve past conversation messages

from langgraph.prebuilt import create_react_agent
# LangGraph's pre-built ReAct agent implementation
# ReAct = Reason + Act — the agent thinks about what to do, acts, observes result, repeats
# This replaces the old LangChain AgentExecutor which was removed in LangChain 1.0

from langchain_ollama import ChatOllama
# The LLM connector class for Ollama — specifically ChatOllama not Ollama
# ChatOllama supports tool calling (function calling) — the older Ollama class does not
# This is what sends prompts to your local Mistral model and receives responses

from langchain_core.messages import HumanMessage, AIMessage
# Message classes that LangGraph uses to represent conversation turns
# HumanMessage = a message the user sent
# AIMessage = a message the AI responded with
# LangGraph needs these typed objects not plain strings to manage conversation history

from tools import tools
# Imports the list of 9 tools from tools.py
# [search_web, create_file, query_knowledge, query_excel, fetch_from_api,
#  read_file, list_folder, create_structured_report, get_weather]
# The agent can ONLY use tools in this list — nothing else

import os
# Standard library for reading environment variables

# ── LLM CONFIGURATION ─────────────────────────────────────────────────────────

ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Reads the Ollama server URL from environment variables
# "http://localhost:11434" is the default — where Ollama runs natively on your Mac
# Inside Docker, docker-compose.yml sets OLLAMA_BASE_URL=http://ollama:11434
# This one line makes the same code work both locally and in Docker

llm = ChatOllama(model="mistral", base_url=ollama_url, temperature=0)
# Creates the language model connection
# model="mistral" — which model Ollama should use for inference
# base_url=ollama_url — where to find Ollama (local or Docker)
# temperature=0 — makes responses deterministic, no randomness
# temperature=0 means the model always picks its highest-confidence response
# temperature=1 would make it creative/random — wrong for data retrieval tasks

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a private AI assistant running locally on the user's Mac.
# This string runs before every conversation — it defines the agent's behaviour
# The model reads these rules on every invocation before processing your message
# Think of it as the agent's standing instructions — its job description

DOCUMENT & KNOWLEDGE RULES:
# Tells the model WHEN to use query_knowledge and WHICH domain to specify
# Without explicit domain rules, the model would guess — often incorrectly
- For questions about PDF documents, Word docs, or text files: call query_knowledge with the correct domain
- domain='personal' for CV, travel documents, personal files
- domain='finance' for financial reports, Nucleus Software PDFs
- domain='work' for architecture docs, API docs, session notes, changelogs
- For ANY question involving Excel files, spending, amounts, transactions, medical expenses, hospitals, or financial data: call query_excel — never query_knowledge
# Excel files are handled differently — direct file read not ChromaDB search
# This rule prevents the model from searching vectors for structured numerical data
- Each question about Excel data must call query_excel fresh — never reuse figures from previous answers
# Prevents the model carrying over numbers from a previous question into the next answer

EXTERNAL API RULES — PMS (Property Management System):
# Tells the model exactly when to call fetch_from_api and what endpoints exist
# Without this, the model would not know your PMS exists or how to query it
- For ANY question about contracts, suppliers, customers, renewals, budgets, forecasts, or PMS data: call fetch_from_api
- Available endpoints: /dashboard, /third-party-providers, /budgets, /forecasts, /forecasts/executive-report
- For contract reference lookups: /third-party-providers?supplier=name or /third-party-providers/{id}
- Always call fetch_from_api fresh for PMS questions — never guess or use cached data

FILE SYSTEM RULES:
# Controls access to your project files — agent can explore but only within private-ai folder
- To list files in the project: call list_folder
- To read a specific file: call read_file with the filename
- Only files inside private-ai folder are accessible
# This rule reinforces the technical sandbox already built into the tools themselves

WEB SEARCH RULES:
# Prevents the model from leaking private data into web search queries
- Only use search_web for current public information not available in local documents or APIs
- Never include personal, financial, or private data in search queries

EXCEL INTERPRETATION RULES:
# Excel files can have multiple sheets with different data structures
# Without these rules the model mixes totals from one sheet with transactions from another
- Each sheet is labelled === Sheet: Name === — treat each sheet as completely separate data
- Only use data from the sheet that is directly relevant to the question being asked
- Never mix data or totals from different sheets in the same answer unless explicitly asked
- Summary or total rows in one sheet are not the same as transaction rows in another sheet
- When asked for a specific entity's breakdown, only return rows where that entity appears directly
- If multiple sheets contain relevant data, state clearly which sheet each figure comes from
- When calculating totals, only sum rows that directly match the question

RESPONSE RULES:
# Controls how the model presents its answers — prevents common failure modes
- Never show raw JSON or tool call syntax in your response
# Prevents the model from narrating tool calls instead of executing them
- Never fabricate data — only report what the tools actually return
# The core honesty rule — no hallucination
- When query_knowledge returns document content, use that exact content — never replace with placeholders
# Directly addresses the problem where the model ignores retrieved content and generates templates
- Never use query_knowledge for Excel or financial data
# Redundant with the rules above but repetition reinforces the constraint
- If a tool returns no results, say clearly: I could not find that information
# Better to admit uncertainty than fabricate
- Be concise and precise"""

# ── AGENT CREATION ────────────────────────────────────────────────────────────

agent = create_react_agent(
    model=llm,      # The LLM that does the reasoning (Mistral via Ollama)
    tools=tools,    # The 9 tools the agent can call
    prompt=SYSTEM_PROMPT  # The rules injected before every conversation
)
# create_react_agent wires everything together
# Internally it manages: tool schema injection, ReAct loop, message formatting
# The ReAct loop: receive message → reason about what to do → call a tool →
# observe the result → reason again → call another tool if needed → return final answer

# ── MEMORY LOADER ─────────────────────────────────────────────────────────────

def load_history(session_id: str) -> list:
    # Retrieves the last 15 messages for this user from PostgreSQL
    # Returns them as typed LangGraph message objects (not plain strings)
    # This is how the agent "remembers" previous turns in the conversation
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE session_id=%s ORDER BY timestamp LIMIT 15",
        [session_id]
        # LIMIT 15 prevents loading an unbounded history that could overflow the model's context window
        # ORDER BY timestamp ensures messages are in chronological order
        # WHERE session_id=%s means each user only sees their own conversation history
    )
    rows = cursor.fetchall()
    # Returns list of (role, content) tuples
    conn.close()
    
    history = []
    for role, content in rows:
        if role == "user":
            history.append(HumanMessage(content=content))
            # Wraps user messages in HumanMessage — LangGraph's required format
        elif role == "assistant":
            history.append(AIMessage(content=content))
            # Wraps AI responses in AIMessage — LangGraph's required format
    return history
    # Returns a list like [HumanMessage("hello"), AIMessage("hi"), HumanMessage("what's my CV say?")]
    # LangGraph uses this full history to maintain conversational context

# ── AGENT RUNNER ──────────────────────────────────────────────────────────────

def run_agent(user_message: str, session_id: str = "default") -> str:
    """Run the agent with full conversation memory loaded from PostgreSQL."""
    
    history = load_history(session_id)
    # Loads the last 15 messages for this user from the database
    
    history.append(HumanMessage(content=user_message))
    # Adds the new message to the end of the history list
    # The agent receives the full conversation context + new message together
    
    result = agent.invoke(
        {"messages": history},
        # Passes the complete message list to the agent
        # The agent sees: all previous turns + current question + SYSTEM_PROMPT
        config={
            "run_name": "private-ai",   # Labels this run in any tracing/logging tools
            "recursion_limit": 25       # Maximum number of tool call cycles before stopping
            # Default is 10 — complex multi-step analysis needs more cycles
            # e.g. query_knowledge → search_web → create_file = 3 cycles minimum
        }
    )
    
    return result["messages"][-1].content
    # result["messages"] is the full list of messages after the agent finished
    # [-1] gets the last message — always the agent's final response
    # .content extracts the text string from the AIMessage object

# ── DIRECT TEST ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Only runs when you call python3 agent.py directly
    # Does NOT run when app.py imports run_agent from this file
    response = run_agent("What is the capital of France? Keep it brief.")
    print("\n→ RESPONSE:", response)
    # Quick sanity check — if this prints "Paris" the agent is working