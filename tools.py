from db import get_conn
from dotenv import load_dotenv
import os
load_dotenv()
from langchain.tools import tool
import pathlib
from ddgs import DDGS
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

def _log_tool(name, inp, out):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tool_calls(tool_name,input_text,output_text) VALUES(%s,%s,%s)",
        [name, str(inp), str(out)[:1000]]
    )
    conn.commit()

@tool
def search_web(query: str) -> str:
    """Search the internet for current information only.
    Never include personal names, financial figures, or private data in queries.
    Use ONLY when: the user asks about recent events, or documents
    don't contain the answer, or current data is needed."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO web_log(query) VALUES(%s)", [query])
    conn.commit()
    results = DDGS().text(query, max_results=3)
    out = "\n".join([r['body'] for r in results])
    _log_tool("search_web", query, out)
    return out

@tool
def create_file(filename: str, content: str) -> str:
    """Save content to a file in the outputs folder.
    Use when the user asks to save, write, create, or draft a plain document.
    filename should be just the filename — never include 'outputs/' prefix e.g. 'report.txt' not 'outputs/report.txt'
    For structured reports with sections use create_structured_report instead."""
    # Strip outputs/ prefix if agent includes it — prevents outputs/outputs/ doubling
    filename = filename.replace("outputs/", "").replace("outputs\\", "")
    path = pathlib.Path("outputs") / filename
    path.write_text(content)
    _log_tool("create_file", filename, f"Created {path}")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO file_log(filepath,action) VALUES(%s,%s)", [str(path), "create"])
    conn.commit()
    return f"✓ Saved: {path}"

@tool
def query_knowledge(question: str, domain: str = "work") -> str:
    """Search private documents for relevant information.
    domain options: 'personal', 'finance', 'work'
    personal — CV, travel documents, personal files
    finance — expenses, invoices, financial reports
    work — contracts, architecture docs, API docs, session notes
    Always specify the correct domain. Default is 'work' if unsure."""
    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
    collection_map = {
        "personal": "personal_docs",
        "finance":  "finance_docs",
        "work":     "work_docs"
    }
    collection_name = collection_map.get(domain, "work_docs")
    embedding_fn = OllamaEmbeddingFunction(
        model_name="nomic-embed-text",
        url="http://localhost:11434/api/embeddings"
    )
    client = chromadb.PersistentClient(path="./vectorstore")
    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_fn
        )
        results = collection.query(query_texts=[question], n_results=4)
        chunks = results['documents'][0]
        out = "\n\n".join(chunks) if chunks else "No relevant documents found."
    except Exception:
        out = f"No documents ingested yet for domain: {domain}"
    _log_tool("query_knowledge", f"{domain}: {question}", out)
    return out

@tool
def fetch_from_api(url: str) -> str:
    """Fetch data from the PMS (Property Management System) API.
    Use when the user asks about contracts, budgets, forecasts, dashboard data, or third party providers.

    Available endpoints:
    - /dashboard — overall dashboard summary
    - /third-party-providers — list all contracts, supports ?supplier=name or ?customer=name filters
    - /third-party-providers/{id} — single contract by ID
    - /budgets — all budgets
    - /budgets/{id} — single budget by ID
    - /forecasts — forecast data
    - /forecasts/executive-report — executive summary, supports ?fy=FY25/26 filter

    url should be just the endpoint path e.g. '/dashboard' or '/budgets' or '/third-party-providers?supplier=Acme'"""
    import requests, json
    base_url = os.getenv("PMS_BASE_URL")
    api_key = os.getenv("PMS_API_KEY")
    if not api_key:
        return "PMS API key not configured. Check your .env file."
    if not base_url:
        return "PMS base URL not configured. Check your .env file."
    full_url = f"{base_url}{url}" if not url.startswith("http") else url
    resp = requests.get(
        full_url,
        headers={"X-API-Key": api_key},
        timeout=10
    )
    if resp.status_code == 401:
        return "Authentication failed — check your PMS API key in .env"
    if resp.status_code == 404:
        return f"Endpoint not found: {full_url}"
    if resp.status_code != 200:
        return f"PMS API error {resp.status_code}: {resp.text[:200]}"
    data = resp.json().get("data", resp.json())
    _log_tool("fetch_from_api", full_url, str(data)[:200])
    return json.dumps(data, indent=2)[:3000]

@tool
def read_file(filepath: str) -> str:
    """Read the contents of a file inside the private-ai project folder.
    Use when the user asks to read, summarise, or analyse a specific file.
    filepath should be relative to the private-ai folder e.g. 'app.py' or 'outputs/report.txt'
    Cannot read files outside the private-ai folder."""
    base = pathlib.Path("~/private-ai").expanduser().resolve()
    path = (base / filepath).resolve()
    if not str(path).startswith(str(base)):
        _log_tool("read_file", filepath, "BLOCKED — outside private-ai folder")
        return "Access denied — can only read files inside the private-ai folder"
    if not path.exists():
        return f"File not found: {filepath}"
    if path.is_dir():
        return f"{filepath} is a folder, not a file. Use list_folder instead."
    content = path.read_text(errors="ignore")[:4000]
    _log_tool("read_file", str(path), content[:100])
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO file_log(filepath,action) VALUES(%s,%s)", [str(path), "read"])
    conn.commit()
    return content

@tool
def list_folder(folder_path: str = "") -> str:
    """List all files and folders inside the private-ai project folder.
    Use when the user asks what files exist, wants to explore the project, or needs to find a filename.
    folder_path is optional — leave empty to list the root private-ai folder.
    Use subfolder names to go deeper e.g. 'outputs' or 'documents'
    Cannot list folders outside private-ai."""
    base = pathlib.Path("~/private-ai").expanduser().resolve()
    if not folder_path:
        path = base
    else:
        path = (base / folder_path).resolve()
    if not str(path).startswith(str(base)):
        _log_tool("list_folder", folder_path, "BLOCKED — outside private-ai folder")
        return "Access denied — can only list folders inside private-ai"
    if not path.exists():
        return f"Folder not found: {folder_path}"
    if not path.is_dir():
        return f"{folder_path} is a file, not a folder. Use read_file instead."
    items = []
    for f in sorted(path.iterdir()):
        if f.name.startswith("."):
            continue
        if f.is_dir():
            items.append(f"📁 {f.name}/")
        else:
            size = f.stat().st_size
            size_str = f"{size:,} bytes" if size < 1024 else f"{size//1024:,} KB"
            items.append(f"📄 {f.name} ({size_str})")
    _log_tool("list_folder", str(path), f"{len(items)} items")
    return f"Contents of {path.relative_to(base.parent)}:\n" + "\n".join(items)

@tool
def create_structured_report(title: str, sections: str, filename: str) -> str:
    """Create a formatted analysis report with clearly labelled sections.
    Use when the user asks for a formal analysis, gap analysis, structured summary, or report with headings.
    Use create_file instead for plain unstructured content.
    filename should be just the filename — never include 'outputs/' prefix e.g. 'gap_analysis.txt'
    sections should be separated by '|||' with heading:content format
    Example: 'Executive Summary: ... ||| Key Findings: ... ||| Gaps: ...'"""
    # Strip outputs/ prefix if agent includes it — prevents outputs/outputs/ doubling
    filename = filename.replace("outputs/", "").replace("outputs\\", "")
    path = pathlib.Path("outputs") / filename
    content = f"# {title}\n\n"
    for section in sections.split("|||"):
        if ":" in section:
            heading, body = section.split(":", 1)
            content += f"## {heading.strip()}\n{body.strip()}\n\n"
    path.write_text(content)
    _log_tool("create_structured_report", title, f"Created {path}")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO file_log(filepath,action) VALUES(%s,%s)", [str(path), "create"])
    conn.commit()
    return f"✓ Report saved: {path}"

#Weather Tool
@tool
def get_weather(location: str) -> str:
    """Get current weather for any city or location.
    Use when the user asks about weather, temperature, forecast, or conditions anywhere.
    location should be a city name e.g. 'Nottingham' or 'London' or 'Mumbai'"""
    import requests
    # wttr.in is a free weather API — no key needed, returns clean text
    resp = requests.get(
        f"https://wttr.in/{location}?format=3",
        timeout=10,
        headers={"User-Agent": "private-ai-agent"}
    )
    if resp.status_code != 200:
        return f"Could not fetch weather for {location}"
    _log_tool("get_weather", location, resp.text)
    return resp.text

@tool
def query_excel(filename: str, question: str) -> str:
    """Query an Excel or CSV file directly for precise numerical data, totals, dates, or figures.
    Use for ANY question involving amounts, spending, transactions, medical expenses, or structured data.
    Use for ANY question about Ciggis, hospitals, categories, monthly spend, or financial summaries.
    filename should be just the filename e.g. 'Mummy_Medical_Expenses_Anuj.xlsx'
    Never use query_knowledge for Excel files — always use this tool instead."""
    import openpyxl
    path = pathlib.Path("documents") / filename
    if not path.exists():
        return f"File not found: {filename}. Make sure the file is in the documents folder."
    wb = openpyxl.load_workbook(path, data_only=True)
    output = []
    for sheet in wb.worksheets:
        output.append(f"\n=== Sheet: {sheet.title} ===")
        for row in sheet.iter_rows():
            row_data = []
            for cell in row:
                if cell.value is not None:
                    row_data.append(f"{cell.coordinate}={cell.value}")
            if row_data:
                output.append(" | ".join(row_data))
    result = "\n".join(output)
    _log_tool("query_excel", f"{filename}: {question}", f"Loaded {len(output)} lines across {len(wb.worksheets)} sheets")
    return result

tools = [search_web, create_file, query_knowledge, query_excel, fetch_from_api, read_file, list_folder, create_structured_report, get_weather]

# ── TEST EACH TOOL INDEPENDENTLY ──
# python3 -c "from tools import search_web; print(search_web.invoke('Python news 2025'))"
# python3 -c "from tools import create_file; print(create_file.invoke({'filename': 'test.txt', 'content': 'hello world'}))"
# python3 -c "from tools import query_knowledge; print(query_knowledge.invoke('test query'))"
# python3 -c "from tools import query_excel; print(query_excel.invoke({'filename': 'Mummy_Medical_Expenses_Anuj.xlsx', 'question': 'total spent'}))"
# python3 -c "from tools import fetch_from_api; print(fetch_from_api.invoke('/dashboard'))"
# python3 -c "from tools import list_folder; print(list_folder.invoke(''))"
# python3 -c "from tools import read_file; print(read_file.invoke('app.py'))"
# python3 -c "from tools import get_weather; print(get_weather.invoke('London'))"