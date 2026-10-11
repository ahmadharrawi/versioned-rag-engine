import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from db import get_connection
from models import ModelRegistry

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Simple text chunker based on character offsets."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks if chunks else [text]

def ingest_document_version(
    doc_id: str,
    title: str,
    content: str,
    effective_from: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Ingests a new version of a document.
    
    Version Control Logic:
    1. If no effective_from is supplied, defaults to current UTC timestamp.
    2. Any existing active version (where effective_to IS NULL) is superseded:
       its effective_to is set to the new version's effective_from.
    3. Old versions and chunks are preserved (never deleted), enabling time-travel queries.
    4. Version number is incremented automatically.
    5. Content is chunked, embedded via all-mpnet-base-v2, and stored in pgvector.
    """
    if effective_from is None:
        effective_from = datetime.now(timezone.utc)
    elif effective_from.tzinfo is None:
        effective_from = effective_from.replace(tzinfo=timezone.utc)

    metadata = metadata or {}
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # 1. Fetch current highest version number and active version
                cur.execute(
                    """
                    SELECT version_id, version_number, effective_from 
                    FROM doc_versions 
                    WHERE doc_id = %s AND effective_to IS NULL
                    FOR UPDATE;
                    """,
                    (doc_id,)
                )
                active_record = cur.fetchone()

                # Get the max version number for this doc_id
                cur.execute(
                    "SELECT COALESCE(MAX(version_number), 0) AS max_v FROM doc_versions WHERE doc_id = %s;",
                    (doc_id,)
                )
                max_v_row = cur.fetchone()
                next_version_num = (max_v_row['max_v'] or 0) + 1

                # 2. Supersede the previously active version if it exists
                if active_record:
                    active_version_id = active_record['version_id']
                    # Version-control logic: The previous version ceases to be effective 
                    # at the exact moment the new version becomes effective.
                    cur.execute(
                        """
                        UPDATE doc_versions
                        SET effective_to = %s
                        WHERE version_id = %s;
                        """,
                        (effective_from, active_version_id)
                    )

                # 3. Insert the new document version
                new_version_id = uuid.uuid4()
                cur.execute(
                    """
                    INSERT INTO doc_versions (
                        version_id, doc_id, version_number, title, 
                        effective_from, effective_to, metadata
                    ) VALUES (%s, %s, %s, %s, %s, NULL, %s);
                    """,
                    (str(new_version_id), doc_id, next_version_num, title, effective_from, psycopg2.extras.Json(metadata))
                )

                # 4. Generate chunks & embeddings
                chunks = chunk_text(content)
                if not chunks:
                    chunks = [content]

                embedding_model = ModelRegistry.get_embedding_model()
                embeddings = embedding_model.encode(chunks, normalize_embeddings=True).tolist()

                # 5. Insert chunks into the database
                chunk_records = [
                    (
                        str(uuid.uuid4()),
                        str(new_version_id),
                        doc_id,
                        idx,
                        chunk_txt,
                        emb
                    )
                    for idx, (chunk_txt, emb) in enumerate(zip(chunks, embeddings))
                ]

                cur.executemany(
                    """
                    INSERT INTO chunks (chunk_id, version_id, doc_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    chunk_records
                )

        return {
            "status": "success",
            "version_id": str(new_version_id),
            "doc_id": doc_id,
            "version_number": next_version_num,
            "effective_from": effective_from.isoformat(),
            "chunks_count": len(chunks)
        }
    finally:
        conn.close()

if __name__ == "__main__":
    import psycopg2.extras
    # Example test run
    print("Testing Ingestion...")
    v1 = ingest_document_version(
        doc_id="policy_remote_work",
        title="Remote Work Policy",
        content="Employees are allowed to work remotely up to 2 days per week with manager approval.",
        effective_from=datetime(2023, 1, 1, tzinfo=timezone.utc)
    )
    print("V1 ingested:", v1)

    v2 = ingest_document_version(
        doc_id="policy_remote_work",
        title="Remote Work Policy v2",
        content="Remote work has been expanded. Employees may now work remotely full-time without manager approval.",
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    print("V2 ingested:", v2)
