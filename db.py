import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

def get_conn():
    """Get a PostgreSQL connection.
    Uses POSTGRES_URL_DOCKER inside Docker, POSTGRES_URL locally."""
    url = os.getenv("POSTGRES_URL_DOCKER") or os.getenv("POSTGRES_URL")
    return psycopg2.connect(url)