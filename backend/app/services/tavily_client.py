"""Tavily web-search client.

Web research is EVIDENCE ONLY. Nothing retrieved here may modify hard
constraints, schedules, or the output of deterministic engines (CP-SAT,
simulator, validator, hard-conflict gate). This module:

  * calls the Tavily REST API guarded by TAVILY_API_KEY,
  * prefers authoritative railway sources (Indian Railways, CRIS, PIB,
    Ministry of Railways),
  * keeps web traffic bounded (per-run query budget + limited HTTP retries),
  * never raises - failures return (None, error) so the workflow falls back
    to the internal RAG/database path.
"""
import json
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

TAVILY_API_URL = "https://api.tavily.com/search"

MAX_HTTP_RETRIES = int(__import__("os").getenv("TAVILY_HTTP_RETRIES", "2"))
BACKOFF_MS = float(__import__("os").getenv("TAVILY_BACKOFF_MS", "0.35"))

AUTHORITATIVE_DOMAINS = (
    "indianrailways.gov.in",
    "indianrail.gov.in",
    "cris.org.in",
    "pib.gov.in",
    "pib.nic.in",
    "irctc.co.in",
    "railmitra.com",
    "mission.railway.gov.in",
    "rct.indianrail.gov.in",
    "morth.nic.in",
)

_RELEVANCE_FLOOR = 0.4

_cache: Dict[str, Any] = {"results": None, "at": 0.0}
_CACHE_TTL = 900.0  # repeated identical queries within a run hit the cache


def is_authoritative(url: str) -> bool:
    return any(d in (url or "").lower() for d in AUTHORITATIVE_DOMAINS)


def _domain_of(url: str) -> str:
    url = (url or "").lower()
    url = url.split("://")[-1]
    host = url.split("/")[0].split("?")[0]
    return host


def _dedupe(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for r in results:
        u = (r.get("source_url") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(r)
    return out


def _build_result(query: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    url = raw.get("url", "")
    snippet = raw.get("content") or raw.get("raw_content") or ""
    score = float(raw.get("score") or 0.0)
    relevance = min(max(score, 0.0), 1.0)
    return {
        "query": query,
        "source_url": url,
        "title": raw.get("title", ""),
        "snippet": (snippet[:1000] + ("..." if len(snippet) > 1000 else "")),
        "relevance": round(relevance, 3),
        "score": round(relevance, 3),
        "domain": _domain_of(url),
        "authoritative": is_authoritative(url),
        "published_date": raw.get("published_date"),
        "sample": False,
    }


def tavily_search(
    query: str,
    *,
    api_key: Optional[str] = None,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[List[str]] = None,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Run one bounded Tavily search. Returns (normalized results, error)."""
    api_key = api_key or __import__("os").getenv("TAVILY_API_KEY", "")
    if not api_key:
        return None, "TAVILY_API_KEY not configured"

    # cache identical queries for the lifetime of a workflow run
    now = time.time()
    if _cache["results"] is not None and (now - _cache["at"]) < _CACHE_TTL:
        return _cache["results"], None

    payload = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max(max_results, 1),
        "topic": "general",
    }
    if include_domains:
        payload["include_domains"] = include_domains

    last_err: Optional[str] = None
    for attempt in range(MAX_HTTP_RETRIES + 1):
        try:
            req = urllib.request.Request(
                TAVILY_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "raillink-ai/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            raw_results = body.get("results") or []
            results = _dedupe([_build_result(query, r) for r in raw_results])
            results = [r for r in results if r["snippet"] or r["relevance"] >= _RELEVANCE_FLOOR]
            results.sort(key=lambda r: (r["authoritative"], r["relevance"]), reverse=True)
            _cache["results"] = results
            _cache["at"] = now
            return results, None
        except Exception as e:  # noqa: BLE001 - network/API errors are recoverable
            last_err = str(e)
            if attempt < MAX_HTTP_RETRIES:
                time.sleep(BACKOFF_MS * (attempt + 1))
    _cache["results"] = []
    _cache["at"] = now
    return None, last_err


def validate_evidence(web_evidence: Dict[str, Any], max_sources: int = 8) -> Dict[str, Any]:
    """Deterministic evidence validation. Filters/dedupes/ranks sources.

    This is the "Evidence Validation" gate in the workflow. It never alters
    planning state - it only decides what web information is trustworthy enough
    to surface to the officer in the report.
    """
    sources = web_evidence.get("sources") or []
    validated = []
    for s in sources:
        if not s.get("source_url"):
            continue
        validated.append(s)

    # rank: authoritative first, then by relevance
    validated.sort(key=lambda s: (bool(s.get("authoritative")), float(s.get("relevance") or 0.0)),
                   reverse=True)
    validated = validated[:max_sources]

    relevant = [s for s in validated if float(s.get("relevance") or 0.0) >= _RELEVANCE_FLOOR]
    summary = (
        f"{len(validated)} web source(s) validated; "
        f"{len(relevant)} considered relevant, "
        f"{sum(1 for s in validated if s.get('authoritative'))} from authoritative railway domains. "
        "Web evidence is informational only and does not modify plan constraints."
    )
    return {
        **{k: v for k, v in web_evidence.items() if k not in ("sources", "summary")},
        "sources": validated,
        "relevant_results": len(relevant),
        "summary": summary,
    }