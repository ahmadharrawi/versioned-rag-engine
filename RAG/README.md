# Version-Aware RAG Pipeline

A production-ready Version-Aware Retrieval-Augmented Generation (RAG) system built with:
- **FastAPI** & Python 3.10+
- **PostgreSQL 16 + pgvector** (via Docker)
- **SentenceTransformers** (`sentence-transformers/all-mpnet-base-v2` for 768-dim embeddings)
- **CrossEncoder** (`cross-encoder/nli-deberta-v3-base` for Natural Language Inference & Contradiction Detection)

---

## Architecture Overview

```
                      +---------------------------------------+
                      |               FastAPI                 |
                      |            POST /ask, /ingest         |
                      +-------------------+-------------------+
                                          |
        +---------------------------------+--------------------------------+
        |                                 |                                |
  [ Ingestion ]                     [ Retrieval ]                [ Contradiction Check ]
  - Auto-increments v#              - SQL Filter:                - CrossEncoder
  - Supersedes old version            effective_from <= as_of      (nli-deberta-v3-base)
    effective_to = new.from           AND (effective_to IS NULL  - Computes pairwise
  - Never deletes history                 OR effective_to > as_of) contradiction score
  - all-mpnet-base-v2 vectors       - pgvector Cosine Distance
```

---

## 1. Quickstart

### Step 1: Start PostgreSQL with pgvector
```bash
docker-compose up -d
```
This automatically executes `init.sql`, creates the tables `doc_versions` and `chunks`, and installs the vector HNSW index.

### Step 2: Install Python Dependencies
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
```

### Step 3: Start FastAPI Application
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger documentation is available at: [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 2. API Endpoints

### `POST /ingest`
Ingest a document. When a new version of an existing `doc_id` is ingested, previous active versions have their `effective_to` set to the new version's `effective_from`.

**Example Request:**
```json
{
  "doc_id": "remote_work_policy",
  "title": "Remote Work Policy v1",
  "content": "Employees may work remotely 2 days per week with manager approval.",
  "effective_from": "2023-01-01T00:00:00Z"
}
```

Superseding version:
```json
{
  "doc_id": "remote_work_policy",
  "title": "Remote Work Policy v2",
  "content": "All employees can work remotely 5 days per week without manager approval.",
  "effective_from": "2024-01-01T00:00:00Z"
}
```

---

### `POST /ask`
Queries knowledge as of a specific point in time.

**Historical Query (2023):**
```json
{
  "query": "How many days can I work remotely?",
  "as_of": "2023-06-01T12:00:00Z",
  "top_k": 3
}
```
*Retrieves V1 (2 days per week).*

**Modern Query (Current / 2024+):**
```json
{
  "query": "How many days can I work remotely?",
  "as_of": "2024-06-01T12:00:00Z",
  "top_k": 3
}
```
*Retrieves V2 (5 days per week).*
