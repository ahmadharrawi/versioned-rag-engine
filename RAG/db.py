import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Get DB URL or use default pgvector credentials
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:mysecretpassword@localhost:5432/postgres"
)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Ensures vector extension and tables exist before handling requests."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Enable pgvector
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            
            # Create doc_versions table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS doc_versions (
                    id SERIAL PRIMARY KEY,
                    document_id VARCHAR(255) NOT NULL,
                    version INT NOT NULL,
                    effective_from TIMESTAMP WITH TIME ZONE NOT NULL,
                    effective_to TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(50) DEFAULT 'current'
                );
            """)
            
            # Create chunks table (768-dim embeddings for all-mpnet-base-v2)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id SERIAL PRIMARY KEY,
                    doc_version_id INT REFERENCES doc_versions(id) ON DELETE CASCADE,
                    text TEXT NOT NULL,
                    embedding vector(768)
                );
            """)
            conn.commit()
            print("Database initialized successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Error initializing database: {e}")
        raise e
    finally:
        conn.close()