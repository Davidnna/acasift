"""One-run external scholarly comparison; no external full-text persistence."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from flask import current_app

from app.services.scholarly_providers import run_live_scholarly_discovery
from app.services.similarity_service import compare_text_pair


def _clip_passage(value, maximum=350):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= maximum:
        return value
    return value[:maximum].rsplit(" ", 1)[0].rstrip() + "…"


def compare_with_live_scholarly_sources(submitted_text, ngram_size=5, document_title=None):
    """Discover, temporarily retrieve and compare every permitted source in this run."""
    max_sources = current_app.config.get("MAX_EXTERNAL_SOURCES", 24)
    max_downloads = current_app.config.get("MAX_EXTERNAL_DOWNLOADS", 8)
    run = run_live_scholarly_discovery(
        submitted_text,
        document_title=document_title,
        max_sources=max_sources,
        max_downloads=max_downloads,
    )

    evidence = []
    semantic_statuses = []
    for candidate, retrieved in run["retrieved_sources"]:
        source_text = retrieved["text"]
        analysis = compare_text_pair(
            submitted_text,
            source_text,
            ngram_size=ngram_size,
        )
        semantic_statuses.append(analysis["semantic_status"])

        has_overlap = (
            analysis["matched_ngram_count"] > 0
            or analysis["fuzzy_coverage"] > 0
            or (analysis["semantic_coverage"] or 0) > 0
        )
        if not has_overlap:
            continue

        passages = []
        for passage in analysis["passages"][:20]:
            start = int(passage["reference_start"])
            end = int(passage["reference_end"])
            source_excerpt = passage.get("reference_text") or source_text[start:end]
            passages.append({
                "submitted_start": int(passage["submitted_start"]),
                "submitted_end": int(passage["submitted_end"]),
                "matched_text": _clip_passage(passage.get("matched_text")),
                "source_excerpt": _clip_passage(source_excerpt),
                "match_method": passage.get("match_method", "exact_ngram"),
                "match_score": float(passage.get("match_score", 100.0)),
            })

        authors = candidate.get("authors") or []
        evidence.append({
            "provider": candidate.get("provider") or "scholarly_source",
            "providers": candidate.get("providers") or [],
            "provider_id": candidate.get("provider_id"),
            "title": candidate.get("title") or "Untitled scholarly source",
            "authors": authors[:20],
            "year": candidate.get("year"),
            "journal": candidate.get("journal"),
            "doi": candidate.get("doi"),
            "source_url": candidate.get("source_url"),
            "full_text_url": retrieved.get("final_url"),
            "license_name": retrieved.get("license_name"),
            "license_url": retrieved.get("license_url"),
            "cosine_similarity": analysis["cosine_similarity"],
            "exact_ngram_coverage": analysis["matched_ngram_coverage"],
            "matched_ngram_count": analysis["matched_ngram_count"],
            "total_query_ngrams": analysis["total_query_ngrams"],
            "fuzzy_similarity": analysis["fuzzy_similarity"],
            "fuzzy_coverage": analysis["fuzzy_coverage"],
            "semantic_similarity": analysis["semantic_similarity"],
            "semantic_coverage": analysis["semantic_coverage"],
            "semantic_status": analysis["semantic_status"],
            "composite_similarity": analysis["composite_similarity"],
            "passages": passages,
        })

    evidence.sort(
        key=lambda item: (
            item["composite_similarity"],
            item["exact_ngram_coverage"],
            item["fuzzy_coverage"],
        ),
        reverse=True,
    )

    return {
        "status": run["status"],
        "queries": run["queries"],
        "providers": run["providers"],
        "sources_discovered": run["sources_discovered"],
        "sources_downloaded": run["sources_downloaded"],
        "sources_compared": len(run["retrieved_sources"]),
        "sources_with_matches": len(evidence),
        "retrieval_failures": run["retrieval_failures"],
        "semantic_status": (
            "enabled" if "completed" in semantic_statuses
            else ("unavailable" if "unavailable" in semantic_statuses else "not_configured")
        ),
        "evidence": evidence[:40],
        "full_text_retained": False,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
