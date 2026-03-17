import sqlite3, os
import psycopg2
from dotenv import load_dotenv
load_dotenv()

# Source — your existing SQLite database
sqlite_conn = sqlite3.connect("memory.db")

# Destination — your PostgreSQL database
pg_conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
pg_cursor = pg_conn.cursor()

def migrate_table(table: str, columns: list):
    """Copy all rows from SQLite table to PostgreSQL table."""
    rows = sqlite_conn.execute(
        f"SELECT {', '.join(columns)} FROM {table}"
    ).fetchall()

    if not rows:
        print(f"  {table}: no rows to migrate")
        return

    placeholders = ", ".join(["%s"] * len(columns))
    col_names = ", ".join(columns)

    for row in rows:
        pg_cursor.execute(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
            row
        )

    pg_conn.commit()
    print(f"  ✓ {table}: {len(rows)} rows migrated")

print("Migrating SQLite → PostgreSQL...")
migrate_table("messages",   ["session_id", "role", "content"])
migrate_table("tool_calls", ["tool_name", "input_text", "output_text", "session_id"])
migrate_table("web_log",    ["url", "query"])
migrate_table("file_log",   ["filepath", "action"])
migrate_table("users",      ["username", "password", "role"])

sqlite_conn.close()
pg_cursor.close()
pg_conn.close()
print("\n✓ Migration complete — all data moved to PostgreSQL")
