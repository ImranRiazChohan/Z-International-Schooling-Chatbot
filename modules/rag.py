import json
import numpy as np
import faiss
from pathlib import Path
from sentence_transformers import SentenceTransformer
from config import EMBED_MODEL_NAME

INDEX_DIR = Path("./rag_index")
DOCSTORE_PATH = INDEX_DIR / "docstore.json"
FAISS_PATH = INDEX_DIR / "faiss.index"

_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL_NAME)
    return _embedder

def retrieve(query: str, k: int = 5):
    if not FAISS_PATH.exists() or not DOCSTORE_PATH.exists():
        return []
    index = faiss.read_index(str(FAISS_PATH))
    chunks = json.loads(DOCSTORE_PATH.read_text(encoding="utf-8"))["chunks"]
    q_emb = np.array(get_embedder().encode([query], normalize_embeddings=True)).astype('float32')
    scores, idxs = index.search(q_emb, k)
    return [{"score": s, "text": chunks[i]["text"]} for i, s in zip(idxs[0], scores[0]) if i != -1 and i < len(chunks)]

def compose_context(results):
    return "\n\n".join([r["text"] for r in results])