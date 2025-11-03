"""
Definitions and helpers for supported journals.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence

from .models import JournalConfig


DEFAULT_JOURNALS: Sequence[JournalConfig] = (
    JournalConfig(key="cell", name="Cell", container_title="Cell"),
    JournalConfig(key="cell-genomics", name="Cell Genomics", container_title="Cell Genomics"),
    JournalConfig(key="cell-host-microbe", name="Cell Host & Microbe", container_title="Cell Host & Microbe"),
    JournalConfig(key="cell-metabolism", name="Cell Metabolism", container_title="Cell Metabolism"),
    JournalConfig(key="cell-reports", name="Cell Reports", container_title="Cell Reports"),
    JournalConfig(key="cell-systems", name="Cell Systems", container_title="Cell Systems"),
    JournalConfig(key="communications-biology", name="Communications Biology", container_title="Communications Biology"),
    JournalConfig(key="current-biology", name="Current Biology", container_title="Current Biology"),
    JournalConfig(key="isme-communications", name="ISME Communications", container_title="ISME Communications"),
    JournalConfig(key="mbio", name="mBio", container_title="mBio"),
    JournalConfig(key="molecular-biology-and-evolution", name="Molecular Biology and Evolution", container_title="Molecular Biology and Evolution"),
    JournalConfig(key="msystems", name="mSystems", container_title="mSystems"),
    JournalConfig(key="nature", name="Nature", container_title="Nature"),
    JournalConfig(key="nature-biotechnology", name="Nature Biotechnology", container_title="Nature Biotechnology"),
    JournalConfig(key="nature-communications", name="Nature Communications", container_title="Nature Communications"),
    JournalConfig(key="nature-ecology-evolution", name="Nature Ecology & Evolution", container_title="Nature Ecology & Evolution"),
    JournalConfig(key="nature-machine-intelligence", name="Nature Machine Intelligence", container_title="Nature Machine Intelligence"),
    JournalConfig(key="nature-methods", name="Nature Methods", container_title="Nature Methods"),
    JournalConfig(key="nature-microbiology", name="Nature Microbiology", container_title="Nature Microbiology"),
    JournalConfig(key="nature-reviews-microbiology", name="Nature Reviews Microbiology", container_title="Nature Reviews Microbiology"),
    JournalConfig(key="science", name="Science", container_title="Science"),
    JournalConfig(key="science-advances", name="Science Advances", container_title="Science Advances"),
    JournalConfig(key="the-isme-journal", name="The ISME Journal", container_title="The ISME Journal"),
    JournalConfig(key="trends-in-biotechnology", name="Trends in Biotechnology", container_title="Trends in Biotechnology"),
    JournalConfig(key="trends-in-ecology-evolution", name="Trends in Ecology & Evolution", container_title="Trends in Ecology & Evolution"),
    JournalConfig(key="trends-in-microbiology", name="Trends in Microbiology", container_title="Trends in Microbiology"),
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

    tokens = _tokenise(user_values)
    resolved: dict[str, JournalConfig] = {}

    if any(token.lower() == "all" for token in tokens):
        for journal in DEFAULT_JOURNALS:
            resolved[journal.container_title] = journal

    for token in tokens:
        lowered = token.lower()
        if lowered == "all":
            continue
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
