import argparse
import sys
from pathlib import Path

from app import config, store
from app.embed import get_embedder

from .chunk import chunk_text
from .sources import fetch_europepmc, load_local


def build(rebuild: bool, epmc_limit: int, skip_web: bool) -> None:
    emb = get_embedder()
    conn = store.connect()
    if rebuild:
        store.reset(conn)
    store.check_embed_model(conn, emb.model_name, emb.dim, init=True)
    docs = [load_local(config.ROOT / "corpus" / "user")]
    if not skip_web:
        docs.append(fetch_europepmc(epmc_limit))
    seen = {r[0] for r in conn.execute("SELECT DISTINCT title FROM chunks")}
    total = 0
    for src in docs:
        for source, title, url, text in src:
            if title in seen:
                continue
            pieces = chunk_text(text)
            if not pieces:
                continue
            vecs = emb.embed_documents(pieces)
            store.add_chunks(conn, [(source, title, url, p) for p in pieces], vecs)
            total += len(pieces)
            print(f"{source}: {title} -> {len(pieces)} chunks", flush=True)
    print(f"added {total} chunks; index now {conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="ingest")
    ap.add_argument("cmd", choices=["build", "rebuild"])
    ap.add_argument("--epmc-limit", type=int, default=40)
    ap.add_argument("--skip-web", action="store_true")
    a = ap.parse_args()
    build(a.cmd == "rebuild", a.epmc_limit, a.skip_web)
