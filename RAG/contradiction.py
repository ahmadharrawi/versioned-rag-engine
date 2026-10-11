import torch
import torch.nn.functional as F
from typing import List, Dict, Any, Tuple
from models import ModelRegistry

def detect_contradictions(
    chunks: List[Dict[str, Any]],
    contradiction_threshold: float = 0.65
) -> List[Dict[str, Any]]:
    """
    Evaluates pairs of retrieved chunks using CrossEncoder (nli-deberta-v3-base).
    
    cross-encoder/nli-deberta-v3-base outputs 3 logits corresponding to:
    [contradiction, entailment, neutral]
    
    Returns a list of contradiction warnings detected among the provided chunks.
    """
    if len(chunks) < 2:
        return []

    model = ModelRegistry.get_nli_model()
    pairs = []
    chunk_meta_pairs = []

    # Build unique chunk combinations
    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            # Form premise and hypothesis
            pairs.append([chunks[i]["content"], chunks[j]["content"]])
            chunk_meta_pairs.append((chunks[i], chunks[j]))

    if not pairs:
        return []

    # Compute logits
    # The default label mapping for nli-deberta-v3-base: 0: contradiction, 1: entailment, 2: neutral
    # We verify mapping via model.config.id2label if available or default softmax over [0]
    logits = model.predict(pairs, convert_to_tensor=True)
    probabilities = F.softmax(logits, dim=-1)

    id2label = getattr(model.model.config, "id2label", {0: "contradiction", 1: "entailment", 2: "neutral"})
    contradiction_idx = 0
    for idx, label in id2label.items():
        if "contradict" in label.lower():
            contradiction_idx = int(idx)
            break

    contradictions = []
    for pair_idx, (c1, c2) in enumerate(chunk_meta_pairs):
        contra_score = float(probabilities[pair_idx][contradiction_idx])
        if contra_score >= contradiction_threshold:
            contradictions.append({
                "chunk_1": {
                    "doc_id": c1["doc_id"],
                    "version_number": c1["version_number"],
                    "title": c1["title"],
                    "snippet": c1["content"][:150] + "..." if len(c1["content"]) > 150 else c1["content"]
                },
                "chunk_2": {
                    "doc_id": c2["doc_id"],
                    "version_number": c2["version_number"],
                    "title": c2["title"],
                    "snippet": c2["content"][:150] + "..." if len(c2["content"]) > 150 else c2["content"]
                },
                "contradiction_score": round(contra_score, 4),
                "warning": (
                    f"Potential contradiction ({round(contra_score * 100, 1)}%) "
                    f"between [{c1['title']} v{c1['version_number']}] and [{c2['title']} v{c2['version_number']}]."
                )
            })

    return contradictions
