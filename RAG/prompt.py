from datetime import datetime, timezone
from typing import List, Dict, Any

def format_version_aware_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    as_of: datetime,
    contradictions: List[Dict[str, Any]]
) -> str:
    """
    Constructs an explicit, version-aware prompt for the LLM.
    Explicitly provides version numbers, effective dates, and contradiction warnings.
    """
    as_of_str = as_of.strftime("%Y-%m-%d %H:%M:%S UTC")

    context_blocks = []
    for idx, c in enumerate(chunks, start=1):
        block = (
            f"--- Context Document {idx} ---\n"
            f"Title: {c['title']}\n"
            f"Document ID: {c['doc_id']}\n"
            f"Version: {c['version_number']}\n"
            f"Effective From: {c['effective_from']}\n"
            f"Effective To: {c['effective_to'] or 'Present (Active)'}\n"
            f"Content:\n{c['content']}\n"
        )
        context_blocks.append(block)

    context_str = "\n".join(context_blocks) if context_blocks else "No relevant documents found for the requested as-of date."

    warnings_block = ""
    if contradictions:
        warnings_lines = ["\n[CRITICAL NOTICE: CONTRADICTIONS DETECTED IN RETRIEVED CONTEXT]"]
        for c in contradictions:
            warnings_lines.append(f"- {c['warning']}")
        warnings_block = "\n".join(warnings_lines) + "\n"

    prompt = f"""You are an enterprise AI assistant answering queries using temporal versioned knowledge.

TEMPORAL CONTEXT:
The user is evaluating this question strictly as of: {as_of_str}.
All provided context was verified to be effective at this specific point in time.
{warnings_block}
RETRIEVED CONTEXT:
{context_str}

USER QUERY:
{query}

INSTRUCTIONS:
1. Answer the query relying exclusively on the provided context effective as of {as_of_str}.
2. Explicitly cite the document title, version number, and effective date for any factual claims made.
3. If contradiction warnings are present, acknowledge the ambiguity or explain the differences.
4. If information is not available for this effective date, explicitly state that it is not covered.

ANSWER:
"""
    return prompt
