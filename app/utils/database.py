import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import Config  

def get_db_connection():
    """
    Establishes connection to the Postgres DB using credentials from Config.
    """
    try:
        conn = psycopg2.connect(
            database=Config.POSTGRES_DB,
            user=Config.POSTGRES_USER,
            password=Config.POSTGRES_PASSWORD,
            host=Config.POSTGRES_HOST,
            port=Config.POSTGRES_PORT
        )
        return conn
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        raise e