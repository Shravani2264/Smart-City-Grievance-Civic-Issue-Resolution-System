"""Retrieval-Augmented Generation layer backed by ChromaDB.

Every complaint ever filed is embedded (MiniLM, 384-d, runs locally/offline) and stored in a persistent
ChromaDB collection. Two things use it:

1. Duplicate Detection (agent 5) — semantic similarity between a new complaint and recent open ones,
   far stronger than keyword Jaccard ("kachra pile" ≈ "trash heap uncollected", "nala choked" ≈
   "drain blocked"), including across Hinglish.
2. Complaint Understanding (agent 1) — retrieves a few similar past complaints with their confirmed
   issue types, injected into the LLM prompt as grounding examples (classic RAG few-shot).

Fully optional and graceful: if `chromadb` is not installed, `available()` is False and every function
is a safe no-op, so the system runs exactly as before. Install with `pip install chromadb` to enable.
"""
import logging
import os

log = logging.getLogger("civic.rag")

_client = None
_collection = None
_ef = None
_disabled = None

_DIR = os.environ.get("CIVIC_CHROMA_DIR", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
_COLLECTION = "civic_complaints"


def _init():
    global _client, _collection, _ef, _disabled
    if _collection is not None or _disabled:
        return _collection
    if os.environ.get("CIVIC_RAG", "auto").lower() == "off":
        _disabled = "CIVIC_RAG=off"
        return None
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        _ef = embedding_functions.DefaultEmbeddingFunction()  # MiniLM-L6-v2 ONNX, local
        _client = chromadb.PersistentClient(path=os.path.abspath(_DIR))
        _collection = _client.get_or_create_collection(_COLLECTION, embedding_function=_ef,
                                                        metadata={"hnsw:space": "cosine"})
    except Exception as e:
        _disabled = f"chromadb unavailable: {e}"
        log.info("RAG disabled (%s) — falling back to keyword matching", _disabled)
    return _collection


def available() -> bool:
    return _init() is not None


def status() -> dict:
    col = _init()
    return {"enabled": col is not None, "backend": "chromadb", "embedder": "all-MiniLM-L6-v2 (onnx, local)",
            "indexed": (col.count() if col is not None else 0), "reason": _disabled}


def reset():
    """Drop and recreate the collection (called by seed)."""
    global _collection
    if not available():
        return
    try:
        _client.delete_collection(_COLLECTION)
    except Exception:
        pass
    _collection = _client.get_or_create_collection(_COLLECTION, embedding_function=_ef,
                                                    metadata={"hnsw:space": "cosine"})


def _meta(c: dict) -> dict:
    return {k: (c.get(k) if c.get(k) is not None else "") for k in
            ("issue_type", "category", "ward", "status", "cluster_id")} | {"created_at": c.get("created_at") or 0}


def index(complaint: dict):
    """Add or update one complaint's embedding. Best-effort; never raises."""
    col = _init()
    if col is None or not complaint.get("text"):
        return
    try:
        col.upsert(ids=[complaint["id"]], documents=[complaint["text"]], metadatas=[_meta(complaint)])
    except Exception as e:
        log.debug("rag index failed for %s: %s", complaint.get("id"), e)


def index_bulk(complaints: list[dict]):
    col = _init()
    if col is None:
        return
    rows = [(c["id"], c["text"], _meta(c)) for c in complaints if c.get("text")]
    if not rows:
        return
    try:
        ids, docs, metas = zip(*rows)
        col.upsert(ids=list(ids), documents=list(docs), metadatas=list(metas))
    except Exception as e:
        log.debug("rag bulk index failed: %s", e)


def similar(text: str, n: int = 10, where: dict | None = None) -> dict[str, float]:
    """Return {complaint_id: similarity 0..1} for the n most semantically similar complaints.

    Similarity = 1 - cosine_distance. Empty dict if RAG is unavailable or on any error.
    """
    col = _init()
    if col is None or not text:
        return {}
    try:
        if col.count() == 0:  # nothing indexed yet (e.g. mid-seed) — skip the embed cost
            return {}
        res = col.query(query_texts=[text], n_results=n, where=where or None,
                        include=["distances"])
        ids = res.get("ids", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return {i: max(0.0, 1.0 - float(d)) for i, d in zip(ids, dists)}
    except Exception as e:
        log.debug("rag query failed: %s", e)
        return {}


def retrieve_examples(text: str, n: int = 3) -> list[dict]:
    """RAG grounding: return a few similar past complaints with their confirmed issue types.

    Used by Complaint Understanding to few-shot the classifier. Each item: {text, issue_type, similarity}.
    """
    col = _init()
    if col is None or not text:
        return []
    try:
        if col.count() == 0:
            return []
        res = col.query(query_texts=[text], n_results=n, include=["documents", "metadatas", "distances"])
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        out = []
        for doc, meta, dist in zip(docs, metas, dists):
            it = (meta or {}).get("issue_type") or ""
            if it and it != "other":
                out.append({"text": doc, "issue_type": it, "similarity": round(max(0.0, 1.0 - float(dist)), 2)})
        return out
    except Exception as e:
        log.debug("rag retrieve failed: %s", e)
        return []
