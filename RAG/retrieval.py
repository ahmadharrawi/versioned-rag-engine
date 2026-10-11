from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from db import get_connection
from models import ModelRegistry

def retrieve_version_aware_chunks(
    query: str,
    as_of: Optional[datetime] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Retrieves the top_k relevant chunks valid as of a specified timestamp.
    
    Version Control & SQL Filter Logic:
    1. If as_of is None, default to current UTC time (latest snapshot).
    2. A document version is valid at as_of IF AND ONLY IF:
         effective_from <= as_of AND (effective_to IS NULL OR effective_to > as_of)
    3. The SQL query strictly applies this temporal condition inside the JOIN/WHERE clause
       BEFORE computing cosine distance (<=>) and ordering by it.
    4. Distance <=> in pgvector calculates cosine distance (1 - cosine_similarity).
    """
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    # Generate query embedding
    embedding_model = ModelRegistry.get_embedding_model()
    query_vector = embedding_model.encode(query, normalize_embeddings=True).tolist()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # SQL filtering strictly isolates valid versions prior to vector ranking
            sql = """
                SELECT 
                    c.chunk_id,
                    c.doc_id,
                    c.content,
                    c.chunk_index,
                    dv.version_number,
                    dv.title,
                    dv.effective_from,
                    dv.effective_to,
                    (c.embedding <=> %s::vector) AS distance
                FROM chunks c
                INNER JOIN doc_versions dv ON c.version_id = dv.version_id
                WHERE dv.effective_from <= %s 
                  AND (dv.effective_to IS NULL OR dv.effective_to > %s)
                ORDER BY distance ASC
                LIMIT %s;
            """
            cur.execute(sql, (query_vector, as_of, as_of, top_k))
            results = cur.fetchall()

            formatted_results = []
            for row in results:
                formatted_results.append({
                    "chunk_id": str(row["chunk_id"]),
                    "doc_id": row["doc_id"],
                    "title": row["title"],
                    "version_number": row["version_number"],
                    "effective_from": row["effective_from"].isoformat() if row["effective_from"] else None,
                    "effective_to": row["effective_to"].isoformat() if row["effective_to"] else None,
                    "content": row["content"],
                    "score": round(1.0 - float(row["distance"]), 4), # Cosine similarity
                    "distance": round(float(row["distance"]), 4)
                })

            return formatted_results
    finally:
        conn.close()
