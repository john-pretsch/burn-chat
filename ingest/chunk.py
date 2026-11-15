import re


def chunk_text(text: str, max_words: int = 380, overlap: int = 60) -> list[str]:
    """Paragraph-aware chunker, roughly 500 tokens per chunk with word overlap."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], []
    for p in paras:
        words = p.split()
        if len(cur) + len(words) > max_words and cur:
            chunks.append(" ".join(cur))
            cur = cur[-overlap:]
        cur.extend(words)
        while len(cur) > max_words * 1.5:  # one huge paragraph
            chunks.append(" ".join(cur[:max_words]))
            cur = cur[max_words - overlap:]
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if len(c.split()) >= 20]
