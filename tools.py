# ── IMPORTS ───────────────────────────────────────────────────────────────────

from db import get_conn
# Imports the PostgreSQL connection function — used in every tool that logs data
# All audit logging goes through this single connection point

from dotenv import load_dotenv
import os
load_dotenv()
# Loads .env file into environment — makes PMS_API_KEY, PMS_BASE_URL etc available
# Must be called before any os.getenv() calls

from langchain.tools import tool
# The @tool decorator — transforms a regular Python function into an agent-callable tool
# When you put @tool above a function:
# 1. The docstring becomes the tool's description — the agent reads this to decide when to use it
# 2. The function parameters become the tool's input schema
# 3. LangGraph can now call this function during the ReAct loop

import pathlib
# For building file paths safely across operating systems
# pathlib.Path("outputs") / "report.txt" works on Mac, Windows, Linux

from ddgs import DDGS
# DuckDuckGo Search — private web search, no API key, no tracking
# Package was renamed from duckduckgo_search to ddgs — always import from ddgs

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
# chromadb — the vector database
# OllamaEmbeddingFunction — converts text to vectors using your local Ollama model
# Both needed for query_knowledge

# ── AUDIT LOGGER ──────────────────────────────────────────────────────────────

def _log_tool(name, inp, out):
    # Private helper function — the underscore prefix means "internal use only"
    # Called by every tool after it runs — writes to the tool_calls audit table
    # This is non-negotiable by design — every tool call is recorded
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tool_calls(tool_name,input_text,output_text) VALUES(%s,%s,%s)",
        [name, str(inp), str(out)[:1000]]
        # name = which tool was called e.g. "search_web"
        # str(inp) = the input converted to string for storage
        # str(out)[:1000] = first 1000 chars of output — prevents massive database rows
        # Full outputs from web searches or Excel files can be thousands of characters
    )
    conn.commit()
    # Makes the log entry permanent immediately
    # Each tool call is committed individually — if the app crashes mid-session, prior calls are still logged

# ── TOOL 1: SEARCH WEB ────────────────────────────────────────────────────────

@tool
def search_web(query: str) -> str:
    """Search the internet for current information only.
    Never include personal names, financial figures, or private data in queries.
    Use ONLY when: the user asks about recent events, or documents
    don't contain the answer, or current data is needed."""
    # The docstring above is what the AI agent reads to decide when to call this tool
    # Specific instructions in the docstring shape the model's behaviour
    # "Never include personal data" is a privacy constraint built into the tool description
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO web_log(query) VALUES(%s)", [query])
    conn.commit()
    # Logs the search query to web_log BEFORE executing the search
    # If the app crashes during the search, the query is still recorded
    # This is your privacy audit trail — you can always verify what left your machine
    
    results = DDGS().text(query, max_results=3)
    # Sends query to DuckDuckGo and returns top 3 results
    # max_results=3 limits context — more results would use too much of the model's context window
    # DDGS() creates a new search session each call — stateless
    
    out = "\n".join([r['body'] for r in results])
    # r['body'] is the snippet text for each result
    # Joins all 3 results into one string separated by newlines
    # The model reads this string to formulate its response
    
    _log_tool("search_web", query, out)
    # Logs to tool_calls table — records both input (query) and output (results)
    return out

# ── TOOL 2: CREATE FILE ───────────────────────────────────────────────────────

@tool
def create_file(filename: str, content: str) -> str:
    """Save content to a file in the outputs folder.
    Use when the user asks to save, write, create, or draft a plain document.
    filename should be just the filename — never include 'outputs/' prefix e.g. 'report.txt' not 'outputs/report.txt'
    For structured reports with sections use create_structured_report instead."""
    
    filename = filename.replace("outputs/", "").replace("outputs\\", "")
    # Safety strip — the model sometimes passes "outputs/report.txt" as the filename
    # Without this, path becomes "outputs/outputs/report.txt" — a non-existent nested folder
    # .replace() handles both Mac/Linux forward slash and Windows backslash
    
    path = pathlib.Path("outputs") / filename
    # Builds the full path: outputs/report.txt
    # pathlib.Path / operator joins paths safely regardless of OS
    
    path.write_text(content)
    # Writes the content string to the file
    # Creates the file if it doesn't exist, overwrites if it does
    
    _log_tool("create_file", filename, f"Created {path}")
    # Logs the tool call — records what filename was created
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO file_log(filepath,action) VALUES(%s,%s)", [str(path), "create"])
    conn.commit()
    # Logs to file_log separately from tool_calls
    # file_log gives a dedicated audit trail for file system activity
    # str(path) converts the Path object to a string for database storage
    
    return f"✓ Saved: {path}"
    # Returns confirmation to the agent — agent includes this in its response to the user

# ── TOOL 3: QUERY KNOWLEDGE ───────────────────────────────────────────────────

@tool
def query_knowledge(question: str, domain: str = "work") -> str:
    """Search private documents for relevant information.
    domain options: 'personal', 'finance', 'work'
    personal — CV, travel documents, personal files
    finance — expenses, invoices, financial reports
    work — contracts, architecture docs, API docs, session notes
    Always specify the correct domain. Default is 'work' if unsure."""
    # domain parameter tells the agent WHICH ChromaDB collection to search
    # Without domain separation, a finance question might return CV content
    # The docstring teaches the agent which domain to use for each type of question
    
    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
    # Imported inside the function (lazy import) — only loads when this tool is called
    
    collection_map = {
        "personal": "personal_docs",   # documents/personal/ → personal_docs collection
        "finance":  "finance_docs",     # documents/finance/ → finance_docs collection
        "work":     "work_docs"         # documents/work/ → work_docs collection
    }
    collection_name = collection_map.get(domain, "work_docs")
    # Looks up the collection name from the domain string
    # .get(domain, "work_docs") — defaults to work_docs if an unknown domain is passed
    
    embedding_fn = OllamaEmbeddingFunction(
        model_name="nomic-embed-text",              # Same model used during ingestion
        url="http://localhost:11434/api/embeddings"  # Local Ollama endpoint
    )
    # CRITICAL: Must use the SAME embedding model for both ingestion and querying
    # If you ingest with model A and query with model B, the vectors are in different
    # mathematical spaces — search results will be meaningless
    
    client = chromadb.PersistentClient(path="./vectorstore")
    # Opens the ChromaDB database from the vectorstore folder
    
    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_fn
        )
        # get_collection (NOT get_or_create_collection) — only retrieves existing collections
        # get_or_create_collection would conflict if the embedding function differs from stored config
        # Using get_collection raises an exception if collection doesn't exist — caught below
        
        results = collection.query(query_texts=[question], n_results=4)
        # Converts the question to a vector using nomic-embed-text
        # Finds the 4 most semantically similar chunks in the collection
        # Semantic = finds meaning not just keywords
        # e.g. "when does money change hands" finds "payment terms" content
        
        chunks = results['documents'][0]
        # results['documents'] is a list of lists (one list per query)
        # [0] gets results for the first (and only) query
        # chunks is now a list of text strings — the matching document pieces
        
        out = "\n\n".join(chunks) if chunks else "No relevant documents found."
        # Joins all chunks with double newlines for readability
        # If no chunks found, returns a clear message — agent will say it couldn't find info
        
    except Exception:
        out = f"No documents ingested yet for domain: {domain}"
        # Catches errors when the collection doesn't exist
        # Happens when no documents have been ingested into that domain yet
    
    _log_tool("query_knowledge", f"{domain}: {question}", out)
    # Logs both the domain and question so audit trail shows exactly what was searched
    return out

# ── TOOL 4: FETCH FROM API ────────────────────────────────────────────────────

@tool
def fetch_from_api(url: str) -> str:
    """Fetch data from the Dexter (Property Management System) API.
    Use when the user asks about contracts, budgets, forecasts, dashboard data, or third party providers. (This section of the code allows you to interface external applications via a RestAPI with your private agent)

    Available endpoints:
    - /dashboard — overall dashboard summary
    - /third-party-providers — list all contracts, supports ?supplier=name or ?customer=name filters
    - /third-party-providers/{id} — single contract by ID
    - /budgets — all budgets
    - /budgets/{id} — single budget by ID
    - /forecasts — forecast data
    - /forecasts/executive-report — executive summary, supports ?fy=FY25/26 filter

    url should be just the endpoint path e.g. '/dashboard' or '/budgets' or '/third-party-providers?supplier=Acme'"""
    # The detailed endpoint list in the docstring is what teaches the agent
    # which URL to construct for each type of question
    
    import requests, json
    # Imported inside function — only loaded when this tool is actually called
    
    base_url = os.getenv("PMS_BASE_URL")
    api_key = os.getenv("PMS_API_KEY")
    # Reads credentials from .env file — never hardcoded in source code
    # If these were hardcoded, committing to GitHub would expose your API key
    
    if not api_key:
        return "PMS API key not configured. Check your .env file."
    if not base_url:
        return "PMS base URL not configured. Check your .env file."
    # Return helpful error messages instead of cryptic HTTP errors
    # The agent will relay these messages to the user
    
    full_url = f"{base_url}{url}" if not url.startswith("http") else url
    # Combines base URL with endpoint path
    # e.g. "http://localhost:3000/api/v1" + "/dashboard" = "http://localhost:3000/api/v1/dashboard"
    # If agent passes a full URL starting with http, use it as-is
    
    resp = requests.get(
        full_url,
        headers={"X-API-Key": api_key},
        # X-API-Key is the authentication header your PMS expects
        # Every request must include this or the server returns 401 Unauthorized
        timeout=10
        # Give up after 10 seconds — prevents the agent hanging on slow/dead endpoints
    )
    
    if resp.status_code == 401:
        return "Authentication failed — check your PMS API key in .env"
        # 401 = Unauthorized — API key is wrong or expired
    if resp.status_code == 404:
        return f"Endpoint not found: {full_url}"
        # 404 = endpoint doesn't exist — agent passed a wrong URL
    if resp.status_code != 200:
        return f"PMS API error {resp.status_code}: {resp.text[:200]}"
        # Any other non-success status code — returns the error message from the server
    
    data = resp.json().get("data", resp.json())
    # Your PMS API wraps responses in a "data" key: {"data": [...], "metrics": {...}}
    # .get("data", resp.json()) extracts just the data array
    # If no "data" key exists, falls back to the entire response
    
    _log_tool("fetch_from_api", full_url, str(data)[:200])
    # Logs the full URL called and first 200 chars of the response
    
    return json.dumps(data, indent=2)[:3000]
    # json.dumps converts the Python dict/list back to a formatted JSON string
    # indent=2 makes it human-readable with indentation
    # [:3000] limits to 3000 chars — prevents overwhelming the model's context window

# ── TOOL 5: READ FILE ─────────────────────────────────────────────────────────

@tool
def read_file(filepath: str) -> str:
    """Read the contents of a file inside the private-ai project folder.
    Use when the user asks to read, summarise, or analyse a specific file.
    filepath should be relative to the private-ai folder e.g. 'app.py' or 'outputs/report.txt'
    Cannot read files outside the private-ai folder."""
    
    base = pathlib.Path("~/private-ai").expanduser().resolve()
    # expanduser() converts "~" to your actual home directory path
    # resolve() converts to an absolute path e.g. /Users/anuj/private-ai
    # This is the security boundary — no file outside this folder can be read
    
    path = (base / filepath).resolve()
    # Builds the full path to the requested file
    # resolve() is critical here — it converts path traversal attempts to absolute paths
    # e.g. "../../Documents/secret.pdf" resolves to /Users/anuj/Documents/secret.pdf
    
    if not str(path).startswith(str(base)):
        _log_tool("read_file", filepath, "BLOCKED — outside private-ai folder")
        return "Access denied — can only read files inside the private-ai folder"
        # Security check — compares absolute paths
        # If the resolved path doesn't start with /Users/anuj/private-ai, it's outside the sandbox
        # Logs the blocked attempt — you can see in the audit trail if someone tried to escape the sandbox
        # This prevents path traversal attacks: passing "../../Documents/taxes.pdf" is blocked here
    
    if not path.exists():
        return f"File not found: {filepath}"
    
    if path.is_dir():
        return f"{filepath} is a folder, not a file. Use list_folder instead."
        # Helpful redirect — prevents confusing errors when user passes a folder path
    
    content = path.read_text(errors="ignore")[:4000]
    # Reads the file as text
    # errors="ignore" skips characters that can't be decoded (e.g. binary data in text files)
    # [:4000] limits to 4000 characters — prevents overwhelming the model's context window
    
    _log_tool("read_file", str(path), content[:100])
    # Logs the full resolved path and first 100 chars of content
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO file_log(filepath,action) VALUES(%s,%s)", [str(path), "read"])
    conn.commit()
    # Logs the file read to file_log — separate dedicated audit trail for file access
    
    return content

# ── TOOL 6: LIST FOLDER ───────────────────────────────────────────────────────

@tool
def list_folder(folder_path: str = "") -> str:
    """List all files and folders inside the private-ai project folder.
    Use when the user asks what files exist, wants to explore the project, or needs to find a filename.
    folder_path is optional — leave empty to list the root private-ai folder.
    Use subfolder names to go deeper e.g. 'outputs' or 'documents'
    Cannot list folders outside private-ai."""
    
    base = pathlib.Path("~/private-ai").expanduser().resolve()
    # Same security boundary as read_file — ~/private-ai is the root
    
    if not folder_path:
        path = base
        # Empty string = list the root project folder
    else:
        path = (base / folder_path).resolve()
        # Build path to the requested subfolder
    
    if not str(path).startswith(str(base)):
        _log_tool("list_folder", folder_path, "BLOCKED — outside private-ai folder")
        return "Access denied — can only list folders inside private-ai"
        # Same path traversal protection as read_file
    
    if not path.exists():
        return f"Folder not found: {folder_path}"
    
    if not path.is_dir():
        return f"{folder_path} is a file, not a folder. Use read_file instead."
        # Helpful redirect when user passes a file path instead of a folder path
    
    items = []
    for f in sorted(path.iterdir()):
        # sorted() alphabetises the listing — easier to read
        # path.iterdir() yields every item in the directory
        
        if f.name.startswith("."):
            continue
            # Skips hidden files — .env, .git, .DS_Store etc
            # Critical for .env — prevents the agent from seeing or listing your secrets file
        
        if f.is_dir():
            items.append(f"📁 {f.name}/")
            # Folders shown with 📁 emoji and trailing slash — visually distinct from files
        else:
            size = f.stat().st_size
            # Gets file size in bytes
            size_str = f"{size:,} bytes" if size < 1024 else f"{size//1024:,} KB"
            # Formats size: under 1024 bytes shows bytes, over shows KB
            # {size:,} adds comma separators e.g. 1,234 bytes
            items.append(f"📄 {f.name} ({size_str})")
    
    _log_tool("list_folder", str(path), f"{len(items)} items")
    return f"Contents of {path.relative_to(base.parent)}:\n" + "\n".join(items)
    # relative_to(base.parent) shows path relative to parent of private-ai
    # e.g. shows "private-ai/outputs" not the full absolute path

# ── TOOL 7: CREATE STRUCTURED REPORT ─────────────────────────────────────────

@tool
def create_structured_report(title: str, sections: str, filename: str) -> str:
    """Create a formatted analysis report with clearly labelled sections.
    Use when the user asks for a formal analysis, gap analysis, structured summary, or report with headings.
    Use create_file instead for plain unstructured content.
    filename should be just the filename — never include 'outputs/' prefix e.g. 'gap_analysis.txt'
    sections should be separated by '|||' with heading:content format
    Example: 'Executive Summary: ... ||| Key Findings: ... ||| Gaps: ...'"""
    
    filename = filename.replace("outputs/", "").replace("outputs\\", "")
    # Same outputs/ prefix stripping as create_file — prevents path doubling
    
    path = pathlib.Path("outputs") / filename
    
    content = f"# {title}\n\n"
    # Starts the report with a Markdown H1 heading
    # # = H1, ## = H2 — renders as headings in any Markdown viewer
    
    for section in sections.split("|||"):
        # Splits the sections string on the ||| delimiter
        # The model is instructed to use ||| because it's unlikely to appear in normal text
        # Using comma or pipe alone would conflict with content
        
        if ":" in section:
            heading, body = section.split(":", 1)
            # Splits each section on the first colon
            # "Executive Summary: The company..." → heading="Executive Summary", body=" The company..."
            # split(":", 1) ensures only the first colon is used — body can contain colons
            content += f"## {heading.strip()}\n{body.strip()}\n\n"
            # .strip() removes leading/trailing whitespace from heading and body
            # ## makes it an H2 subheading in Markdown
    
    path.write_text(content)
    # Writes the formatted Markdown report to the file
    
    _log_tool("create_structured_report", title, f"Created {path}")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO file_log(filepath,action) VALUES(%s,%s)", [str(path), "create"])
    conn.commit()
    
    return f"✓ Report saved: {path}"

# ── TOOL 8: GET WEATHER ───────────────────────────────────────────────────────

@tool
def get_weather(location: str) -> str:
    """Get current weather for any city or location.
    Use when the user asks about weather, temperature, forecast, or conditions anywhere.
    location should be a city name e.g. 'Nottingham' or 'London' or 'Mumbai'"""
    
    import requests
    # Imported inside function — only loads when tool is actually called
    
    resp = requests.get(
        f"https://wttr.in/{location}?format=3",
        # wttr.in is a free public weather service — no API key, no account needed
        # ?format=3 returns a single compact line e.g. "London: ⛅️ +12°C"
        # This compact format is ideal — easy for the model to read and relay
        timeout=10,
        headers={"User-Agent": "private-ai-agent"}
        # Some servers block requests without a User-Agent header
        # "private-ai-agent" identifies the request without pretending to be a browser
    )
    
    if resp.status_code != 200:
        return f"Could not fetch weather for {location}"
        # Generic error — covers network issues, invalid location names etc
    
    _log_tool("get_weather", location, resp.text)
    # Logs location queried and weather result returned
    
    return resp.text
    # Returns the single-line weather string directly
    # e.g. "Nottingham: 🌧 +9°C"

# ── TOOL 9: QUERY EXCEL ───────────────────────────────────────────────────────

@tool
def query_excel(filename: str, question: str) -> str:
    """Query an Excel or CSV file directly for precise numerical data, totals, dates, or figures.
    Use for ANY question involving amounts, spending, transactions, medical expenses, or structured data.
    Use for ANY question about Ciggis, hospitals, categories, monthly spend, or financial summaries.
    filename should be just the filename e.g. 'Mummy_Medical_Expenses_Anuj.xlsx'
    Never use query_knowledge for Excel files — always use this tool instead."""
    # Excel files are NOT ingested into ChromaDB — they're read directly
    # Reason: Excel has structured numerical data, pivot tables, complex layouts
    # ChromaDB would convert it to text chunks, losing the spatial relationships
    # Direct reading preserves cell coordinates which the model uses to understand structure
    
    import openpyxl
    # Excel reading library — imported lazily, only when this tool is called
    
    path = pathlib.Path("documents") / filename
    # Excel files live in the documents/ folder
    # Note: NOT in a subdomain folder — query_excel is domain-agnostic
    
    if not path.exists():
        return f"File not found: {filename}. Make sure the file is in the documents folder."
    
    wb = openpyxl.load_workbook(path, data_only=True)
    # Opens the Excel file
    # data_only=True returns calculated values not formulas
    # e.g. returns 42500 instead of =SUM(B2:B10)
    
    output = []
    for sheet in wb.worksheets:
        # Loops through every tab in the workbook
        output.append(f"\n=== Sheet: {sheet.title} ===")
        # Labels each sheet clearly — model uses these labels to distinguish between sheets
        # e.g. "=== Sheet: Medical Expenses ===" and "=== Sheet: Anuj Spend History ==="
        
        for row in sheet.iter_rows():
            # Loops through every row in the sheet
            row_data = []
            for cell in row:
                if cell.value is not None:
                    row_data.append(f"{cell.coordinate}={cell.value}")
                    # cell.coordinate = the Excel cell reference e.g. "A1", "B3", "F12"
                    # cell.value = the content of that cell
                    # Format: "A1=Date | B1=Hospital | C1=Amount"
                    # Preserving coordinates is the key insight:
                    # The model can see that F1=December and F3=Ciggis
                    # and understand F3's value belongs to the December column
                    # This handles pivot tables and irregular layouts that row-by-row parsing cannot
            
            if row_data:
                output.append(" | ".join(row_data))
                # Joins non-empty cells with " | " separator
                # Empty rows (all None) produce no output — cleaner result
    
    result = "\n".join(output)
    _log_tool("query_excel", f"{filename}: {question}", f"Loaded {len(output)} lines across {len(wb.worksheets)} sheets")
    # Logs which file was queried and how much data was loaded
    # question parameter is logged but not used in the function — the model interprets the data
    
    return result
    # Returns the full coordinate-based dump to the model
    # The model reads the coordinates and values to answer the specific question

# ── TOOLS LIST ────────────────────────────────────────────────────────────────

tools = [search_web, create_file, query_knowledge, query_excel, fetch_from_api, read_file, list_folder, create_structured_report, get_weather]
# This list is imported by agent.py and passed to create_react_agent()
# The agent can ONLY call tools in this list — it has no other capabilities
# Order doesn't matter — the model selects based on docstrings not position
# Adding a new tool = write the function with @tool decorator + add to this list

# ── TOOL TESTS ────────────────────────────────────────────────────────────────
# Run these individually in Terminal to verify each tool works before connecting to the agent
# python3 -c "from tools import search_web; print(search_web.invoke('Python news 2025'))"
# python3 -c "from tools import create_file; print(create_file.invoke({'filename': 'test.txt', 'content': 'hello world'}))"
# python3 -c "from tools import query_knowledge; print(query_knowledge.invoke('test query'))"
# python3 -c "from tools import query_excel; print(query_excel.invoke({'filename': 'Mummy_Medical_Expenses_Anuj.xlsx', 'question': 'total spent'}))"
# python3 -c "from tools import fetch_from_api; print(fetch_from_api.invoke('/dashboard'))"
# python3 -c "from tools import list_folder; print(list_folder.invoke(''))"
# python3 -c "from tools import read_file; print(read_file.invoke('app.py'))"
# python3 -c "from tools import get_weather; print(get_weather.invoke('London'))"
# .invoke() is required for LangChain tool objects — calling search_web('query') directly won't work
