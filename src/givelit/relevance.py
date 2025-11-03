"""
Relevance scoring for retrieved papers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from .models import Paper


def compute_relevance(paper: Paper, keywords: Iterable[str], recency_window: int) -> float:
    """
    Combine keyword matches, recency, and Crossref's inherent score.
    """

    text = f"{paper.title} {paper.summary or ''}".lower()
    title = paper.title.lower()
    score = 0.0

    for keyword in keywords:
        target = keyword.lower().strip()
        if not target:
            continue
        title_hits = title.count(target)
        if title_hits:
            score += 6.0 * title_hits
        body_hits = text.count(target)
        if body_hits:
            score += 2.5 * body_hits

    if paper.source_score:
        score += float(paper.source_score) / 10.0

    if paper.published:
        age_days = (datetime.now(tz=UTC) - paper.published).days
        if age_days >= 0:
            window = max(recency_window, 1)
            freshness = max(0.0, (window - age_days) / window)
            score += freshness * 5.0

    paper.relevance = round(score, 2)
    return paper.relevance

