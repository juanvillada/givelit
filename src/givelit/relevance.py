"""
Relevance scoring for retrieved papers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, Optional

from .models import Paper


def compute_relevance(
    paper: Paper,
    keywords: Iterable[str],
    recency_window: int,
    reference: Optional[datetime] = None,
) -> float:
    """
    Combine keyword matches, recency, and Europe PMC's inherent score.
    """

    now = reference or datetime.now(tz=UTC)
    text = f"{paper.title} {paper.summary or ''}".lower()
    title = paper.title.lower()
    score = 0.0

    matched_keywords = 0
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
        if title_hits or body_hits:
            matched_keywords += 1

    if paper.source_score:
        score += float(paper.source_score) / 10.0

    if matched_keywords:
        score += 4.0 * matched_keywords

    age_days: Optional[int] = None
    if paper.published:
        delta = now - paper.published
        if delta.days >= 0:
            age_days = delta.days
    paper.age_days = age_days

    if age_days is not None:
        window = max(recency_window, 30)
        freshness = max(0.0, (window - min(age_days, window)) / window)
        decay = 1.0 / (1.0 + age_days)
        score += freshness * 6.0 + decay * 4.0

    paper.match_count = matched_keywords
    paper.relevance = round(score, 2)
    return paper.relevance
