"""
Definitions and helpers for supported journals.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from .models import JournalConfig


DEFAULT_JOURNALS: Sequence[JournalConfig] = (
    JournalConfig(
        key="nature-microbiology",
        name="Nature Microbiology",
        container_title="Nature Microbiology",
    ),
    JournalConfig(
        key="science",
        name="Science",
        container_title="Science",
    ),
    JournalConfig(
        key="cell-systems",
        name="Cell Systems",
        container_title="Cell Systems",
    ),
)


def normalise_key(label: str) -> str:
    """
    Convert arbitrary journal names to kebab-case keys.
    """

    key = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return key or "journal"


def _tokenise(values: Iterable[str]) -> List[str]:
    tokens: List[str] = []
    for value in values:
        for part in re.split(r"[;,]", value):
            cleaned = part.strip()
            if cleaned:
                tokens.append(cleaned)
    return tokens


def resolve_journals(user_values: Iterable[str] | None) -> List[JournalConfig]:
    """
    Resolve user-supplied journal labels into search configurations.
    Unknown entries are treated as new journal definitions.
    """

    if not user_values:
        return list(DEFAULT_JOURNALS)

    canonical_lookup = {}
    for journal in DEFAULT_JOURNALS:
        canonical_lookup[journal.key.lower()] = journal
        canonical_lookup[journal.name.lower()] = journal
        canonical_lookup[journal.container_title.lower()] = journal

    resolved: dict[str, JournalConfig] = {}
    for token in _tokenise(user_values):
        lowered = token.lower()
        if lowered in canonical_lookup:
            journal = canonical_lookup[lowered]
        else:
            journal = JournalConfig(
                key=normalise_key(token),
                name=token,
                container_title=token,
            )
        resolved[journal.container_title] = journal
    return list(resolved.values())

