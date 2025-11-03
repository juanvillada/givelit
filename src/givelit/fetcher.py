"""
Download recent works for configured journals via the Crossref API.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Iterable, List

import httpx
from bs4 import BeautifulSoup

from .models import JournalConfig, Paper


CROSSREF_API = "https://api.crossref.org/works"
USER_AGENT = "GiveLit/0.1 (+https://github.com/jcvillada/givelit)"


def _clean_abstract(raw: str | None) -> str | None:
    if not raw:
        return None
    soup = BeautifulSoup(raw, "lxml")
    text = soup.get_text(" ", strip=True)
    return text or None


def _parse_author(author: dict) -> str:
    given = author.get("given")
    family = author.get("family")
    if given and family:
        return f"{given} {family}"
    return author.get("name") or family or given or "Unknown"


def _parse_date(date_payload: dict | None) -> datetime | None:
    if not date_payload:
        return None
    parts = date_payload.get("date-parts")
    if not parts:
        return None
    numbers = parts[0]
    if not numbers:
        return None
    year = numbers[0]
    month = numbers[1] if len(numbers) > 1 else 1
    day = numbers[2] if len(numbers) > 2 else 1
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


class CrossrefFetcher:
    """
    Retrieve articles from Crossref for a set of journals concurrently.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    @property
    def timeout(self) -> float:
        return self._timeout

    async def collect(
        self,
        journals: Iterable[JournalConfig],
        keywords: List[str],
        days_back: int,
        max_results: int,
    ) -> List[Paper]:
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            tasks = [
                self.fetch_for_journal(client, journal, keywords, days_back, max_results)
                for journal in journals
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        papers: List[Paper] = []
        for chunk in results:
            papers.extend(chunk)
        return papers

    async def fetch_for_journal(
        self,
        client: httpx.AsyncClient,
        journal: JournalConfig,
        keywords: List[str],
        days_back: int,
        max_results: int,
    ) -> List[Paper]:
        query = " ".join(keywords).strip()
        if not query:
            raise ValueError("At least one keyword is required.")

        filters = [f"container-title:{journal.container_title}"]
        if days_back > 0:
            cutoff = (datetime.now(tz=UTC) - timedelta(days=days_back)).date()
            filters.append(f"from-pub-date:{cutoff.isoformat()}")

        rows = max(20, min(max_results * 3, 150))
        params = {
            "query": query,
            "select": "title,author,issued,URL,abstract,score,container-title",
            "sort": "score",
            "order": "desc",
            "rows": str(rows),
            "filter": ",".join(filters),
        }

        response = await client.get(CROSSREF_API, params=params)
        response.raise_for_status()

        payload = response.json()
        items = payload.get("message", {}).get("items", [])

        papers: List[Paper] = []
        for item in items:
            title_candidates = item.get("title") or ["Untitled"]
            title = title_candidates[0]

            authors_payload = item.get("author") or []
            authors = [_parse_author(author) for author in authors_payload]

            published = _parse_date(item.get("published") or item.get("issued"))
            abstract = _clean_abstract(item.get("abstract"))

            paper = Paper(
                journal=journal.name,
                title=title,
                url=item.get("URL") or "",
                published=published,
                authors=authors,
                summary=abstract,
                source_score=item.get("score"),
            )
            papers.append(paper)

        return papers[:max_results * 2]
