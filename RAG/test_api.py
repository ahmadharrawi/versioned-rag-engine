import requests

print("--- 1. INGESTING DOCUMENT ---")
ingest_response = requests.post(
    "http://127.0.0.1:8000/ingest", 
    json={
        "document_id": "emp_handbook",
        "version": 1,
        "effective_from": "2023-01-01T00:00:00Z",
        "text": "Employees receive 20 days of paid vacation per year. Remote work is allowed on Fridays."
    }
)
print(ingest_response.json())


print("\n--- 2. ASKING QUESTION ---")
ask_response = requests.post(
    "http://127.0.0.1:8000/ask", 
    json={
        "query": "How many vacation days do I get?",
        "as_of": "2023-05-01T00:00:00Z",
        "top_k": 5
    }
)
print(ask_response.json())