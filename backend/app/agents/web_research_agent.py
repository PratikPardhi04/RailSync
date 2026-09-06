"""Tavily Web Research Agent.

Searches the web ONLY when external/current information is required (railway
rules, maintenance regulations, operational notices, route or timetable info).
Output is structured WebSearchEvidence; web results are evidence-only and never
feed deterministic constraints or schedules.

Fallback rules (per architecture):
  * no TAVILY_API_KEY      -> status "failed", workflow continues on RAG/DB
  * Tavily API error       -> status "failed", workflow continues on RAG/DB
  * no useful results      -> status "completed" with empty relevant sources
  * DEMO_MODE              -> deterministic sample sources (labelled sample=True)
  * search budget          -> bounded by TAVILY_MAX_SEARCHES per run
"""
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

from app.schemas.workflow import WebSearchEvidence
from app.services.tavily_client import _domain_of, is_authoritative, tavily_search

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true" or not os.getenv("GROQ_API_KEY", "")
MAX_SEARCHES = int(os.getenv("TAVILY_MAX_SEARCHES", "2"))

# Maintenance types where external rules/regulations/notices add value.
_EXTERNAL_INTEREST = (
    "TRACK_REPAIR", "TRACK_REPLACEMENT", "TRACK_MAINTENANCE", "SIGNAL_REPAIR",
    "OVERHEAD_WIRE", "BRIDGE_INSPECTION", "TUNNEL_INSPECTION", "LEVEL_CROSSING",
    "OHE", "CIVIL", "ELECTRICAL",
)
_EXTERNAL_KEYWORDS = ("rule", "regulation", "notice", "noticed", "order", "schedule",
                      "timetable", "route", "diversion", "availability", "notice")  # noqa


def _norm(maint: str) -> str:
    return re.sub(r"[^A-Z]", "", (maint or "").upper())


def _needs_search(request: Dict[str, Any], rag_evidence: Optional[Dict[str, Any]]) -> bool:
    maint = _norm(request.get("maintenance_type"))
    rag_docs = int((rag_evidence or {}).get("total_retrieved", 0))
    if rag_docs == 0:
        return True
    if any(_norm(t) in maint for t in _EXTERNAL_INTEREST):
        return True
    blob = " ".join(str(request.get(k) or "") for k in
                    ("description", "notes", "section", "location")).lower()
    return any(kw in blob for kw in _EXTERNAL_KEYWORDS)


def _build_queries(request: Dict[str, Any]) -> List[str]:
    maint = request.get("maintenance_type", "")
    section = request.get("section", "")
    queries = [f"{maint} railway maintenance regulations Indian Railways {section}".strip()]
    blob = " ".join(str(request.get(k) or "") for k in ("description", "notes")).lower()
    if any(k in blob for k in ("timetable", "schedule")):
        queries.append(f"Indian Railways updated timetable {section} train schedule")
    elif any(k in blob for k in ("route", "diversion")):
        queries.append(f"Indian Railways route diversion block {section}")
    else:
        queries.append(f"Indian Railways operational notice block maintenance {section}")
    return queries


def _demo_sources(request: Dict[str, Any]) -> WebSearchEvidence:
    """Deterministic demo-mode evidence (clearly labelled, not real web data)."""
    section = request.get("section", "")
    maint = request.get("maintenance_type", "")
    seed = (len(section or "") * 31 + len(maint or "") * 7) % 10
    sources = [
        {
            "query": f"{maint} railway maintenance regulations Indian Railways {section}",
            "source_url": "https://indianrailways.gov.in/railwayboard/uploads/directorate/traffic_comm/downloads/Gn_Operational_Manual.pdf",
            "title": "General & Subsidiary Rules / Operational Manual - Indian Railways",
            "snippet": ("Relevant general rules governing block working and maintenance "
                        "of line. Indicative demo source - verify against live Tavily feed."),
            "relevance": round(0.9 - seed / 100, 3),
            "score": 0.9,
            "domain": "indianrailways.gov.in",
            "authoritative": True,
            "published_date": None,
            "sample": True,
        },
        {
            "query": f"Indian Railways operational notice block maintenance {section}",
            "source_url": "https://pib.gov.in/newsite/relcontent.aspx?relid=railways",
            "title": "Press Information Bureau - Ministry of Railways",
            "snippet": ("Official railway announcements and operational advisories. "
                        "Indicative demo source - verify against live Tavily feed."),
            "relevance": round(0.8 - seed / 100, 3),
            "score": 0.8,
            "domain": "pib.gov.in",
            "authoritative": True,
            "published_date": None,
            "sample": True,
        },
    ]
    return WebSearchEvidence(
        query="; ".join(_build_queries(request)),
        total_searches=2,
        total_results=len(sources),
        relevant_results=len(sources),
        sources=[s for s in sources if s["relevance"] >= 0.4],
        status="completed",
        search_count=2,
        search_depth="basic",
        summary="Demo-mode web evidence (sample=True). No live Tavily request was made.",
        sample=True,
    )


def run(
    request: Dict[str, Any],
    rag_evidence: Optional[Dict[str, Any]] = None,
    previous: Optional[WebSearchEvidence] = None,
) -> WebSearchEvidence:
    start = time.time()

    # bounded: never re-search when the workflow already produced evidence
    if previous is not None and getattr(previous, "status", "") in ("completed", "failed"):
        return previous

    if not _needs_search(request, rag_evidence):
        return WebSearchEvidence(
            status="idle",
            summary="No external information required; internal RAG/historical evidence is sufficient.",
            search_count=0,
        )

    if not os.getenv("TAVILY_API_KEY", ""):
        if DEMO_MODE:
            return _demo_sources(request)
        return WebSearchEvidence(
            status="failed",
            error="TAVILY_API_KEY not configured; using internal RAG/database workflow.",
            search_count=0,
        )

    queries = _build_queries(request)[:MAX_SEARCHES]
    all_sources: List[Dict[str, Any]] = []
    search_count = 0
    last_error: Optional[str] = None

    for query in queries:
        if search_count >= MAX_SEARCHES:
            break
        search_count += 1
        results, err = tavily_search(query)
        if err:
            last_error = err
            continue
        if results:
            all_sources.extend(results)

    # dedupe across queries (accept both client-mapped source_url and raw Tavily url)
    seen, sources = set(), []
    for s in all_sources:
        if "source_url" not in s:
            u = s.get("url") or ""
            s = {**s, "source_url": u, "domain": s.get("domain") or _domain_of(u),
                 "authoritative": bool(s.get("authoritative", is_authoritative(u))),
                 "relevance": min(max(float(s.get("score") or 0.0), 0.0), 1.0),
                 "snippet": s.get("snippet") or s.get("content") or ""}
        u = s.get("source_url") or ""
        if u in seen or not u:
            continue
        seen.add(u)
        sources.append(s)

    if not sources and last_error:
        return WebSearchEvidence(
            query="; ".join(queries), status="failed", error=last_error,
            search_count=search_count, summary="Tavily search failed; continuing with internal RAG/database evidence.",
        )

    relevant = [s for s in sources if float(s.get("relevance") or 0.0) >= 0.4]
    return WebSearchEvidence(
        query="; ".join(queries),
        total_searches=search_count,
        total_results=len(sources),
        relevant_results=len(relevant),
        sources=sources,
        status="completed",
        search_count=search_count,
        search_depth="basic",
        summary=(
            f"Web research completed: {len(sources)} unique source(s), "
            f"{len(relevant)} relevant, "
            f"{sum(1 for s in sources if s.get('authoritative'))} from authoritative railway domains. "
            "Evidence only - does not modify plan constraints."
        ),
        error=last_error if (sources and last_error) else None,
        execution_time=round(time.time() - start, 3),
    )