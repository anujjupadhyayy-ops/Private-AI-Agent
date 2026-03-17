import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
cursor = conn.cursor()

# Identical schema to your SQLite setup_db.py
# This is the payoff of designing standard SQL from the start
cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id         SERIAL PRIMARY KEY,
        session_id TEXT,
        role       TEXT,
        content    TEXT,
        timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS tool_calls (
        id          SERIAL PRIMARY KEY,
        tool_name   TEXT,
        input_text  TEXT,
        output_text TEXT,
        session_id  TEXT,
        timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS web_log (
        id        SERIAL PRIMARY KEY,
        url       TEXT,
        query     TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS file_log (
        id        SERIAL PRIMARY KEY,
        filepath  TEXT,
        action    TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id         SERIAL PRIMARY KEY,
        username   TEXT UNIQUE NOT NULL,
        password   TEXT NOT NULL,
        role       TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

conn.commit()
cursor.close()
conn.close()
print("✓ PostgreSQL schema created — all tables ready")
