from db import get_conn
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from tools import tools
import os
ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
llm = ChatOllama(model="mistral", base_url=ollama_url, temperature=0)

SYSTEM_PROMPT = """You are a private AI assistant running locally on the user's Mac.

DOCUMENT & KNOWLEDGE RULES:
- For questions about PDF documents, Word docs, or text files: call query_knowledge with the correct domain
- domain='personal' for CV, travel documents, personal files
- domain='finance' for financial reports, Nucleus Software PDFs
- domain='work' for architecture docs, API docs, session notes, changelogs
- For ANY question involving Excel files, spending, amounts, transactions, medical expenses, hospitals, or financial data: call query_excel — never query_knowledge
- Each question about Excel data must call query_excel fresh — never reuse figures from previous answers

EXTERNAL API RULES — PMS (Property Management System):
- For ANY question about contracts, suppliers, customers, renewals, budgets, forecasts, or PMS data: call fetch_from_api
- Available endpoints: /dashboard, /third-party-providers, /budgets, /forecasts, /forecasts/executive-report
- For contract reference lookups: /third-party-providers?supplier=name or /third-party-providers/{id}
- Always call fetch_from_api fresh for PMS questions — never guess or use cached data

FILE SYSTEM RULES:
- To list files in the project: call list_folder
- To read a specific file: call read_file with the filename
- Only files inside private-ai folder are accessible

WEB SEARCH RULES:
- Only use search_web for current public information not available in local documents or APIs
- Never include personal, financial, or private data in search queries

EXCEL INTERPRETATION RULES:
- Each sheet is labelled === Sheet: Name === — treat each sheet as completely separate data
- Only use data from the sheet that is directly relevant to the question being asked
- Never mix data or totals from different sheets in the same answer unless explicitly asked to combine them
- Summary or total rows in one sheet are not the same as transaction rows in another sheet
- When asked for a specific entity's breakdown (e.g. a hospital, a category, a person), only return rows where that entity appears directly — do not include unrelated totals from other sheets
- If multiple sheets contain relevant data, state clearly which sheet each figure comes from
- When calculating totals, only sum rows that directly match the question — never include summary rows that aggregate other data

RESPONSE RULES:
- Never show raw JSON or tool call syntax in your response
- Never fabricate data — only report what the tools actually return
- When query_knowledge returns document content, use that exact content in your response — never replace it with placeholders or templates
- Never use query_knowledge for Excel or financial data
- If a tool returns no results, say clearly: I could not find that information
- Be concise and precise"""

agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=SYSTEM_PROMPT
)
def load_history(session_id: str) -> list:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE session_id=%s ORDER BY timestamp LIMIT 15",
        [session_id]
    )
    rows = cursor.fetchall()
    conn.close()
    history = []
    for role, content in rows:
        if role == "user":
            history.append(HumanMessage(content=content))
        elif role == "assistant":
            history.append(AIMessage(content=content))
    return history

def run_agent(user_message: str, session_id: str = "default") -> str:
    """Run the agent with full conversation memory loaded from SQLite."""

    # Build message list: all past messages + the new one
    history = load_history(session_id)
    history.append(HumanMessage(content=user_message))

    # Run — verbose equivalent: config shows internal steps in Terminal
    result = agent.invoke(
        {"messages": history},
        config={"run_name": "private-ai","recursion_limit": 25}
    )

    return result["messages"][-1].content

# Test when run directly
if __name__ == "__main__":
    response = run_agent("What is the capital of France? Keep it brief.")
    print("\n→ RESPONSE:", response)