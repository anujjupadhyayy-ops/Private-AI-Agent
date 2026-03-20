import psycopg2, os
# psycopg2 — the Python adapter for PostgreSQL
# Without this library Python cannot talk to a PostgreSQL database
# os — standard library for reading environment variables

from dotenv import load_dotenv
# Reads your .env file and loads its contents as environment variables
# Without this, os.getenv() would only see system-level variables, not your .env file

load_dotenv()
# Actually executes the .env file loading
# Must be called before any os.getenv() calls in this file
# All files that import from db.py benefit automatically because this runs at import time

def get_conn():
    """Get a PostgreSQL connection.
    Uses POSTGRES_URL_DOCKER inside Docker, POSTGRES_URL locally."""
    
    url = os.getenv("POSTGRES_URL_DOCKER") or os.getenv("POSTGRES_URL")
    # Tries POSTGRES_URL_DOCKER first
    # Inside Docker: docker-compose.yml injects POSTGRES_URL_DOCKER=postgresql://...@postgres:5432/...
    # "postgres" is the Docker service name — resolves inside Docker but not outside
    # Outside Docker: POSTGRES_URL_DOCKER is not set, so os.getenv returns None
    # None is falsy, so Python evaluates the right side of "or"
    # POSTGRES_URL points at localhost:5432 — your Mac's native PostgreSQL
    # This single line makes the same code work in both environments
    
    return psycopg2.connect(url)
    # Opens and returns a live connection to PostgreSQL
    # Every caller is responsible for closing this connection after use
    # conn.close() — prevents connection pool exhaustion over time