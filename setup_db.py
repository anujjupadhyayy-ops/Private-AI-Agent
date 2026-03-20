import sqlite3, bcrypt
# sqlite3 — Python's built-in SQLite library, no installation needed
# This file creates the LOCAL development database (memory.db on your Mac)
# For production/Docker, setup_postgres.py does the same thing in PostgreSQL
# bcrypt — imported here but not actively used in this file
# It was added during user management work — can be safely removed if unused

conn = sqlite3.connect("memory.db")
# Creates a connection to the SQLite database file called memory.db
# If memory.db doesn't exist yet, SQLite creates it automatically
# If it already exists, this just opens it — no data is lost
# The file lives in ~/private-ai/memory.db — a single file containing your entire database

conn.executescript("""
# executescript() runs multiple SQL statements in one call
# It wraps everything in a transaction automatically

  CREATE TABLE IF NOT EXISTS messages (
  # IF NOT EXISTS — safe to run multiple times, won't error if table already exists
  # This table stores every conversation message — both user and AI turns
  
    id         INTEGER PRIMARY KEY,
    # Unique number for each row, auto-increments (1, 2, 3...)
    # PRIMARY KEY means this column uniquely identifies each row
    
    session_id TEXT,
    # Links each message to a specific user session
    # Format: "user_1", "user_2" etc — set by app.py when user logs in
    # All messages for one user share the same session_id
    # This is how the app separates one user's history from another's
    
    role       TEXT,
    # Either "user" (what you typed) or "assistant" (what the AI responded)
    # Used to render the correct chat bubble style in the UI
    
    content    TEXT,
    # The actual message text — can be any length
    
    timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
    # Automatically records when each message was saved
    # DEFAULT CURRENT_TIMESTAMP means SQLite fills this in automatically
    # Used to ORDER BY timestamp in queries — ensures chronological order
  );

  CREATE TABLE IF NOT EXISTS tool_calls (
  # Audit trail for every tool the agent invoked
  # This is the black box recorder — you can see exactly what the agent did
  
    id          INTEGER PRIMARY KEY,
    tool_name   TEXT,
    # Which tool was called e.g. "search_web", "query_knowledge", "create_file"
    
    input_text  TEXT,
    # What was passed into the tool — the query or parameters
    # e.g. for search_web: the search query string
    # e.g. for query_knowledge: the domain and question
    
    output_text TEXT,
    # What the tool returned — truncated to 1000 characters in _log_tool()
    # Full outputs can be very long — truncation keeps the database manageable
    
    session_id  TEXT,
    # Links tool calls to the user session they came from
    # Lets you audit what a specific user's agent did
    
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS web_log (
  # Separate table specifically for web searches
  # Every DuckDuckGo query is logged HERE before it executes
  # Logging before execution means even failed searches are recorded
  # This is your privacy audit — proof of what left your machine
  
    id        INTEGER PRIMARY KEY,
    url       TEXT,
    # The URL that was fetched (if applicable)
    
    query     TEXT,
    # The search query string that was sent to DuckDuckGo
    # This is what actually left your machine — you can audit it here
    
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS file_log (
  # Tracks every file the agent created, read, or modified
  # Complete audit of file system activity
  
    id        INTEGER PRIMARY KEY,
    filepath  TEXT,
    # The full path to the file that was touched
    # e.g. "outputs/gap_analysis.txt" or "/Users/anuj/private-ai/app.py"
    
    action    TEXT,
    # What was done — "create", "read", or "append"
    
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS users (
  # Stores login credentials and roles for all application users
  # Powers the authentication system in app.py
  
    id         INTEGER PRIMARY KEY,
    
    username   TEXT UNIQUE NOT NULL,
    # UNIQUE — prevents two users having the same username
    # NOT NULL — username cannot be left empty
    # These constraints are enforced at the database level, not just in Python code
    
    password   TEXT NOT NULL,
    # Stores the HASHED password — never the plain text
    # bcrypt hash looks like: $2b$12$... (always starts with $2b$)
    # Even if someone reads this database, they cannot recover the real password
    
    role       TEXT DEFAULT 'user',
    # Either "user" or "admin"
    # DEFAULT 'user' means new users are regular users unless explicitly set to admin
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    # Automatically records when the user account was created
  );
""")

conn.commit()
# Makes all the CREATE TABLE statements permanent
# Without commit(), the schema changes would be lost when the connection closes

print("✓ Database schema ready — all tables created")
# Confirmation that the script ran successfully
# If you see this message, the database is ready to use