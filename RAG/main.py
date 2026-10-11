from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager
import db
from sentence_transformers import SentenceTransformer, CrossEncoder

# Load models
embedder = SentenceTransformer('all-mpnet-base-v2')
nli = CrossEncoder('cross-encoder/nli-deberta-v3-base')

# Lifespan manager auto-runs init_db on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables automatically
    db.init_db()
    yield

app = FastAPI(title="Version-Aware RAG API", lifespan=lifespan)

# Pydantic Schemas with Sample Data so Swagger UI works automatically
class DocumentIngestRequest(BaseModel):
    document_id: str = Field(default="emp_handbook", example="emp_handbook")
    version: int = Field(default=1, example=1)
    effective_from: datetime = Field(default_factory=datetime.now, example="2023-01-01T00:00:00Z")
    text: str = Field(
        default="Employees receive 20 days of paid vacation per year. Remote work is allowed on Fridays.",
        example="Employees receive 20 days of paid vacation per year. Remote work is allowed on Fridays."
    )

class AskRequest(BaseModel):
    query: str = Field(example="How many vacation days do I get?")
    as_of: Optional[datetime] = Field(default_factory=datetime.now, example="2023-05-01T00:00:00Z")
    top_k: int = Field(default=5, example=5)


@app.post("/ingest", summary="Ingest document version")
def ingest_document(payload: DocumentIngestRequest):
    conn = None
    try:
        conn = db.get_db_connection()
        with conn.cursor() as cur:
            # 1. Supersede any currently active version of this document
            cur.execute("""
                UPDATE doc_versions 
                SET effective_to = %s, status = 'superseded' 
                WHERE document_id = %s AND effective_to IS NULL
            """, (payload.effective_from, payload.document_id))
            
            # 2. Insert new version record
            cur.execute("""
                INSERT INTO doc_versions (document_id, version, effective_from, status) 
                VALUES (%s, %s, %s, 'current') RETURNING id
            """, (payload.document_id, payload.version, payload.effective_from))
            
            version_id = cur.fetchone()[0]
            
            # 3. Embed text and insert chunk using str() to bypass psycopg2 type errors
            embedding = embedder.encode(payload.text).tolist()
            cur.execute("""
                INSERT INTO chunks (doc_version_id, text, embedding) 
                VALUES (%s, %s, %s)
            """, (version_id, payload.text, str(embedding)))
            
            conn.commit()
            return {
                "status": "success", 
                "message": f"Ingested {payload.document_id} v{payload.version} successfully."
            }
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database ingestion error: {str(e)}")
    finally:
        if conn:
            conn.close()


@app.post("/ask", summary="Ask a question as of a specific date")
def ask_question(payload: AskRequest):
    as_of_date = payload.as_of or datetime.now()
    
    # Calculate embedding and convert to string for Postgres
    query_embedding = embedder.encode(payload.query).tolist()
    
    conn = None
    try:
        conn = db.get_db_connection()
        with conn.cursor() as cur:
            # Version-Aware Effective Date SQL Query
            cur.execute("""
                SELECT c.text, d.document_id, d.version, d.effective_from 
                FROM chunks c
                JOIN doc_versions d ON d.id = c.doc_version_id
                WHERE d.effective_from <= %s
                  AND (d.effective_to IS NULL OR d.effective_to > %s)
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s;
            """, (as_of_date, as_of_date, str(query_embedding), payload.top_k))
            
            results = cur.fetchall()
            
            retrieved_chunks = [
                {
                    "text": row[0],
                    "document_id": row[1],
                    "version": row[2],
                    "effective_from": str(row[3])
                }
                for row in results
            ]
            
            # Contradiction Detection check
            is_contradiction = False
            if len(retrieved_chunks) >= 2:
                scores = nli.predict([(retrieved_chunks[0]["text"], retrieved_chunks[1]["text"])])
                is_contradiction = bool(scores.argmax(axis=1)[0] == 0)

            return {
                "query": payload.query,
                "as_of": str(as_of_date),
                "retrieved_chunks": retrieved_chunks,
                "contradiction_detected": is_contradiction
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")
    finally:
        if conn:
            conn.close()