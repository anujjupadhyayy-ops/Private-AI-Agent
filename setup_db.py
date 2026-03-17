import sqlite3, bcrypt

conn = sqlite3.connect("memory.db")

conn.executescript("""
  CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY,
    session_id TEXT,
    role       TEXT,
    content    TEXT,
    timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS tool_calls (
    id          INTEGER PRIMARY KEY,
    tool_name   TEXT,
    input_text  TEXT,
    output_text TEXT,
    session_id  TEXT,
    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS web_log (
    id        INTEGER PRIMARY KEY,
    url       TEXT,
    query     TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS file_log (
    id        INTEGER PRIMARY KEY,
    filepath  TEXT,
    action    TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY,
    username   TEXT UNIQUE NOT NULL,
    password   TEXT NOT NULL,
    role       TEXT DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
""")

conn.commit()
print("✓ Database schema ready — all tables created")
