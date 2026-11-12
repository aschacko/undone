import numpy as np
from functools import lru_cache
from .common import load_rows, evaluate
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def load_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME, device="cpu")

def train():
    rows = load_rows("train")
    model = load_model()
    embeddings = model.encode([r["text"] for r in rows], normalize_embeddings=True, show_progress_bar=False)
    labels = sorted(set(r["theme"] for r in rows))
    centers = []
    for label in labels:
        vectors = embeddings[[i for i, r in enumerate(rows) if r["theme"] == label]]
        center = vectors.mean(axis=0)
        centers.append(center / max(np.linalg.norm(center), 1e-12))
    return model, labels, np.array(centers)

def predict(state, texts):
    if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
        raise ValueError("Invalid feedback")
    model, labels, centers = state
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    similarities = embeddings @ centers.T
    indexes = similarities.argmax(axis=1)
    predictions = [labels[int(i)] for i in indexes]
    scores = [float(similarities[j, i]) for j, i in enumerate(indexes)]
    return predictions, scores

if __name__ == "__main__":
    state = train()
    evaluate("minilm", lambda texts: predict(state, texts))
