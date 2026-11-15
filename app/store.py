import datetime
import sqlite3

import sqlite_vec

from . import config


class EmbedModelMismatch(RuntimeError):
    pass


def connect(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY, source TEXT, title TEXT, url TEXT, text TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text, title, content='chunks', content_rowid='id');
        CREATE TABLE IF NOT EXISTS spend (day TEXT PRIMARY KEY, usd REAL NOT NULL DEFAULT 0);
        """
    )
    return conn


def check_embed_model(conn: sqlite3.Connection, model_name: str, dim: int, *, init: bool = False) -> None:
    """Refuse to use an index built with a different embedding model."""
    row = conn.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
    if row is None:
        if init:
            conn.execute("INSERT INTO meta VALUES ('embed_model', ?), ('embed_dim', ?)", (model_name, str(dim)))
            conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS vec USING vec0(embedding float[{dim}])")
            conn.commit()
        return
    if row["value"] != model_name:
        raise EmbedModelMismatch(
            f"Index was built with {row['value']!r} but EMBED_MODEL is {model_name!r}. "
            "Run `python -m ingest rebuild` to re-embed the corpus."
        )


def add_chunks(conn, rows, vectors) -> None:
    for (source, title, url, text), vec in zip(rows, vectors):
        cur = conn.execute(
            "INSERT INTO chunks (source, title, url, text) VALUES (?,?,?,?)", (source, title, url, text)
        )
        rid = cur.lastrowid
        conn.execute("INSERT INTO chunks_fts (rowid, text, title) VALUES (?,?,?)", (rid, text, title))
        conn.execute("INSERT INTO vec (rowid, embedding) VALUES (?, ?)", (rid, sqlite_vec.serialize_float32(vec)))
    conn.commit()


def reset(conn) -> None:
    conn.executescript(
        "DELETE FROM chunks; INSERT INTO chunks_fts(chunks_fts) VALUES('delete-all'); DROP TABLE IF EXISTS vec;"
        "DELETE FROM meta WHERE key IN ('embed_model','embed_dim');"
    )
    conn.commit()


def spend_today(conn) -> float:
    row = conn.execute("SELECT usd FROM spend WHERE day=?", (_today(),)).fetchone()
    return row["usd"] if row else 0.0


def add_spend(conn, usd: float) -> None:
    conn.execute(
        "INSERT INTO spend (day, usd) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET usd = usd + excluded.usd",
        (_today(), usd),
    )
    conn.commit()


def _today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
