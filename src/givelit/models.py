"""
Core data structures used throughout GiveLit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class JournalConfig:
    """
    Represents a search target that can be translated into a Europe PMC query.
    """

    key: str
    name: str
    container_title: str


@dataclass
class Paper:
    """
    Normalised representation of an article returned by Europe PMC.
    """

    journal: str
    title: str
    url: str
    published: Optional[datetime]
    authors: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    relevance: float = 0.0
    source_score: Optional[float] = None
    age_days: Optional[int] = None
    match_count: int = 0

    def formatted_date(self) -> str:
        if not self.published:
            return "Unknown"
        return self.published.strftime("%Y-%m-%d")
