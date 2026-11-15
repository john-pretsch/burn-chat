import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

UA = {"User-Agent": "burn-rag/0.1 (educational nutrition corpus)"}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def load_local(root: Path):
    """Yield (source, title, url, text) for .md/.txt/.pdf files under corpus/user."""
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in {".md", ".txt"}:
            yield "user", p.stem, "", p.read_text(errors="ignore")
        elif p.suffix.lower() == ".pdf":
            text = "\n\n".join((pg.extract_text() or "") for pg in PdfReader(p).pages)
            yield "user", p.stem, "", text


TOPICS = [
    "energy metabolism", "thermic effect of food", "basal metabolic rate", "resting energy expenditure",
    "dietary protein", "insulin sensitivity", "micronutrient deficiency", "glycemic index",
    "dietary fiber", "intermittent fasting", "ketogenic diet", "gut microbiome nutrition",
]
FILTER = ' AND OPEN_ACCESS:y AND LICENSE:"cc by" AND SRC:MED AND PUB_TYPE:"review"'


def _get_json(c, url, params, tries=3):
    for i in range(tries):
        try:
            r = c.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError):
            time.sleep(2 * (i + 1))
    return None


def fetch_europepmc(limit: int = 40):
    """Open-access (CC BY) review articles from Europe PMC, via its documented REST API."""
    with httpx.Client(headers=UA, timeout=45, follow_redirects=True) as c:
        per = max(1, -(-limit // len(TOPICS)))
        hits, seen = [], set()
        for topic in TOPICS:
            data = _get_json(c, f"{EPMC}/search", {
                "query": f'"{topic}"' + FILTER, "format": "json", "pageSize": per, "resultType": "core"})
            for h in (data or {}).get("resultList", {}).get("result", []):
                if h.get("pmcid") and h["pmcid"] not in seen:
                    seen.add(h["pmcid"])
                    hits.append(h)
        hits = hits[:limit]
        for h in hits:
            pmcid = h.get("pmcid")
            if not pmcid:
                continue
            time.sleep(0.4)
            title = f"{h['title'].rstrip('.')} ({h.get('journalTitle', '')} {h.get('pubYear', '')})".strip()
            url = f"https://europepmc.org/article/MED/{h['pmid']}"
            body = None
            try:
                r = c.get(f"{EPMC}/{pmcid}/fullTextXML")
                r.raise_for_status()
                body = BeautifulSoup(r.text, "xml").find("body")
            except httpx.HTTPError:
                pass
            if body is None:  # full text unavailable (endpoint errors happen): fall back to the abstract
                abstract = BeautifulSoup(h.get("abstractText", ""), "lxml").get_text(" ", strip=True)
                if abstract:
                    yield "Europe PMC (abstract)", title, url, abstract
                continue
            parts = []
            for sec in body.find_all("sec"):
                head = sec.find("title", recursive=False)
                paras = [p.get_text(" ", strip=True) for p in sec.find_all("p", recursive=False)]
                if paras:
                    parts.append(((head.get_text(" ", strip=True) + "\n") if head else "") + "\n\n".join(paras))
            text = "\n\n".join(parts) or "\n\n".join(p.get_text(" ", strip=True) for p in body.find_all("p"))
            yield "Europe PMC (CC BY)", title, url, text
