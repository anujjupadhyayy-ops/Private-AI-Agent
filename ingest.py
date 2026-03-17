import chromadb, sys, pathlib, requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

embedding_fn = OllamaEmbeddingFunction(
    model_name="nomic-embed-text",
    url="http://localhost:11434/api/embeddings"
)

client = chromadb.PersistentClient(path="./vectorstore")
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

def extract_text(path: pathlib.Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return " ".join([p.extract_text() or "" for p in pdf.pages])
    elif ext in [".xlsx", ".xls"]:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        rows = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                rows.append(" | ".join([str(c) for c in row if c is not None]))
        return "\n".join(rows)
    elif ext == ".docx":
        from docx import Document
        doc = Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext in [".html", ".htm"]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(path.read_text(), "html.parser")
        return soup.get_text(separator=" ")
    elif ext in [".txt", ".md", ".py", ".js", ".csv", ".json"]:
        return path.read_text(errors="ignore")
    else:
        return f"Unsupported file type: {ext}"

def ingest_url(url: str):
    """Fetch a web page and ingest its text content — goes into work_docs by default."""
    from bs4 import BeautifulSoup
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(separator=" ")
    name = url.split("/")[2]
    chunks = splitter.split_text(text)
    # URLs go into work_docs by default — change to personal_docs or finance_docs if needed
    url_collection = client.get_or_create_collection(
        name="work_docs",
        embedding_function=embedding_fn
    )
    url_collection.add(
        documents=chunks,
        ids=[f"url_{name}_{i}" for i in range(len(chunks))],
        metadatas=[{"source": url, "chunk": i, "domain": "work_docs"}
                   for i in range(len(chunks))]
    )
    print(f"✓ Ingested {len(chunks)} chunks from {url} → work_docs")

def ingest_file(filepath: str):
    path = pathlib.Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}"); return

    # Auto-detect domain from parent folder name
    parent = path.parent.name.lower()
    domain_map = {
        "personal": "personal_docs",
        "finance":  "finance_docs",
        "work":     "work_docs",
        "financial_reports": "finance_docs"
    }
    collection_name = domain_map.get(parent, "work_docs")

    domain_collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn
    )

    text = extract_text(path)
    if not text or text.startswith("Unsupported"):
        print(f"✗ Could not extract text from {path.name}: {text}")
        return

    chunks = splitter.split_text(text)
    if not chunks:
        print(f"✗ No chunks created from {path.name} — file may be empty")
        return

    domain_collection.add(
        documents=chunks,
        ids=[f"{path.stem}_{i}" for i in range(len(chunks))],
        metadatas=[{"source": path.name, "chunk": i, "domain": collection_name}
                   for i in range(len(chunks))]
    )
    print(f"✓ Ingested {len(chunks)} chunks from {path.name} → {collection_name}")

def delete_source(source_name: str, domain: str = "work_docs"):
    """Remove all chunks for a file from a specific domain collection."""
    domain_collection = client.get_or_create_collection(
        name=domain,
        embedding_function=embedding_fn
    )
    existing = domain_collection.get(where={"source": source_name})
    if existing["ids"]:
        domain_collection.delete(ids=existing["ids"])
        print(f"✓ Deleted {len(existing['ids'])} old chunks for {source_name} from {domain}")
    else:
        print(f"No existing chunks found for {source_name} in {domain}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ingest.py documents/personal/file.pdf")
        print("       python3 ingest.py https://example.com")
        print("       python3 ingest.py --delete filename.pdf finance_docs")
    elif sys.argv[1] == "--delete":
        if len(sys.argv) < 4:
            print("Usage: python3 ingest.py --delete filename.pdf domain_name")
        else:
            delete_source(sys.argv[2], sys.argv[3])
    elif sys.argv[1].startswith("http"):
        ingest_url(sys.argv[1])
    else:
        ingest_file(sys.argv[1])