import re
import sqlite3

import sqlite_vec

from . import config
from .embed import Embedder

RRF_K = 60


def _fts_query(text: str) -> str:
    terms = re.findall(r"[A-Za-z0-9]{3,}", text)
    return " OR ".join(f'"{t}"' for t in terms[:12])


def search(conn: sqlite3.Connection, embedder: Embedder, query: str, k: int = config.TOP_K) -> list[dict]:
    """Hybrid search: vector KNN + FTS5 BM25 merged with reciprocal rank fusion."""
    pool = k * 4
    qvec = sqlite_vec.serialize_float32(embedder.embed_query(query))
    vec_ids = [
        r["rowid"]
        for r in conn.execute(
            "SELECT rowid, distance FROM vec WHERE embedding MATCH ? AND k = ? ORDER BY distance", (qvec, pool)
        )
        if r["distance"] <= config.MAX_DISTANCE
    ]
    if not vec_ids:  # nothing semantically close: off-topic, so return no sources
        return []
    fts_ids: list[int] = []
    fq = _fts_query(query)
    if fq:
        fts_ids = [
            r["rowid"]
            for r in conn.execute(
                "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
                (fq, pool),
            )
        ]
    scores: dict[int, float] = {}
    for ids in (vec_ids, fts_ids):
        for rank, rid in enumerate(ids):
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (RRF_K + rank)
    top = sorted(scores, key=scores.get, reverse=True)[:k]
    out = []
    for rid in top:
        row = conn.execute("SELECT source, title, url, text FROM chunks WHERE id=?", (rid,)).fetchone()
        out.append(dict(row))
    return out
