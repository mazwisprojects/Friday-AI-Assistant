"""Semantic Memory Engine for FRIDAY — vector search over facts, chats, and tool results. Works fully offline."""
from __future__ import annotations
import json, math, re, time, uuid, hashlib
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
_STATE = _BACKEND / "long_term_memory" / "semantic_index.json"
_DIMS = 256
_MAX_ENTRIES = 5000

def _load() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"entries": []}

def _save(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")

_st_model = None
def _st():
    """Optional sentence-transformers upgrade; falls back to hashed embeddings."""
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            _st_model = False
    return _st_model or None

def _tokens(text: str):
    return re.findall(r"[a-z0-9]+", (text or "").lower())

def _embed(text: str) -> dict:
    """Hashed word+bigram embedding (L2-normalised). Real vectors, zero dependencies."""
    model = _st()
    if model is not None:
        try:
            return {"v": [round(float(x), 6) for x in model.encode((text or "")[:2000])], "model": "minilm"}
        except Exception:
            pass
    vec = [0.0] * _DIMS
    words = _tokens(text)[:400]
    for i, w in enumerate(words):
        h = int(hashlib.md5(w.encode()).hexdigest(), 16)
        sign = 1.0 if (h >> 124) & 1 else -1.0
        vec[h % _DIMS] += sign * (1.0 / (1.0 + 0.02 * i))
    for a, b in zip(words, words[1:]):
        h = int(hashlib.md5(("%s_%s" % (a, b)).encode()).hexdigest(), 16)
        sign = 1.0 if (h >> 124) & 1 else -1.0
        vec[h % _DIMS] += sign * 0.6
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return {"v": [round(v / norm, 6) for v in vec], "model": "hash256"}

def _cosine(qv: list, dv: list) -> float:
    if len(qv) != len(dv) or not qv:
        return 0.0
    return sum(a * b for a, b in zip(qv, dv))

def _text_overlap(query: str, text: str) -> float:
    """Jaccard fallback when stored/query vectors come from different models."""
    q, t = set(_tokens(query)), set(_tokens(text))
    if not q or not t:
        return 0.0
    return len(q & t) / len(q | t)

def remember(text: str, kind: str = "fact", source: str = "friday", meta: dict = None) -> dict:
    """Store text in the semantic index (auto-chunked for long inputs)."""
    state = _load()
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Nothing to remember"}
    chunks = [text[i:i + 700] for i in range(0, min(len(text), 4200), 700)] or [text]
    added = []
    for chunk in chunks:
        emb = _embed(chunk)
        entry = {"id": uuid.uuid4().hex[:10], "text": chunk, "kind": kind, "source": source,
                 "meta": meta or {}, "vector": emb["v"], "model": emb["model"], "t": time.time()}
        state["entries"].append(entry)
        added.append(entry["id"])
    if len(state["entries"]) > _MAX_ENTRIES:
        state["entries"] = state["entries"][-_MAX_ENTRIES:]
    _save(state)
    return {"ok": True, "ids": added, "count": len(added), "total": len(state["entries"])}
def search(query: str, top_k: int = 5, kind: str = None) -> dict:
    """Vector similarity search across the semantic index."""
    state = _load()
    if not (query or "").strip():
        return {"ok": False, "error": "Empty query"}
    emb = _embed(query)
    qv, qm = emb["v"], emb["model"]
    scored = []
    for e in state["entries"]:
        if kind and e.get("kind") != kind:
            continue
        s = _cosine(qv, e.get("vector", [])) if qm == e.get("model") else _text_overlap(query, e.get("text", ""))
        scored.append((s, e))
    scored.sort(key=lambda se: -se[0])
    return {"ok": True, "query": query, "model": qm, "results": [
        {"id": e["id"], "score": round(s, 4), "kind": e.get("kind"), "source": e.get("source"),
         "t": e.get("t"), "text": e["text"][:300]} for s, e in scored[:max(1, int(top_k))] ]}

def forget(entry_id: str) -> dict:
    state = _load()
    before = len(state["entries"])
    state["entries"] = [e for e in state["entries"] if e.get("id") != entry_id]
    _save(state)
    return {"ok": len(state["entries"]) < before, "removed": before - len(state["entries"])}

def stats() -> dict:
    state = _load()
    entries = state["entries"]
    by_kind, by_model = {}, {}
    for e in entries:
        by_kind[e.get("kind", "?")] = by_kind.get(e.get("kind", "?"), 0) + 1
        by_model[e.get("model", "?")] = by_model.get(e.get("model", "?"), 0) + 1
    return {"ok": True, "total": len(entries), "by_kind": by_kind, "by_model": by_model,
            "backend": "minilm" if _st() else "hash256"}

_ingest_buffer = []
_last_flush = time.time()  # module import time — avoids instant flush on the first message

def ingest_chat(sender: str, text: str, project: str = None) -> dict:
    """Buffered ingestion for the message hot path — flushes every 10 messages or 60 seconds."""
    global _ingest_buffer, _last_flush
    _ingest_buffer.append({"sender": sender, "text": (text or "")[:1500], "project": project or "global", "t": time.time()})
    if len(_ingest_buffer) >= 10 or (time.time() - _last_flush) > 60:
        return flush()
    return {"ok": True, "buffered": len(_ingest_buffer)}

def flush() -> dict:
    """Write buffered messages into the semantic index as one batch."""
    global _ingest_buffer, _last_flush
    items, _ingest_buffer, _last_flush = _ingest_buffer, [], time.time()
    if not items:
        return {"ok": True, "added": 0}
    state = _load()
    for item in items:
        emb = _embed("%s: %s" % (item["sender"], item["text"]))
        state["entries"].append({"id": uuid.uuid4().hex[:10], "text": "%s: %s" % (item["sender"], item["text"]),
                                 "kind": "chat", "source": item["project"], "meta": {},
                                 "vector": emb["v"], "model": emb["model"], "t": item["t"]})
    if len(state["entries"]) > _MAX_ENTRIES:
        state["entries"] = state["entries"][-_MAX_ENTRIES:]
    _save(state)
    return {"ok": True, "added": len(items), "total": len(state["entries"])}

def semantic_tool(args: dict) -> dict:
    a = args or {}
    action = a.get("action", "")
    if action == "remember":
        return remember(a.get("text", ""), a.get("kind", "fact"), a.get("source", "friday"), a.get("meta"))
    if action == "search":
        return search(a.get("query", ""), int(a.get("top_k", 5)), a.get("kind"))
    if action == "forget":
        return forget(a.get("id", ""))
    if action == "stats":
        return stats()
    return {"ok": False, "error": "Unknown semantic action"}