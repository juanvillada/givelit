"""
Journal search backed by the Europe PMC REST API.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable, List

import httpx
from bs4 import BeautifulSoup

from .models import JournalConfig, Paper


BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
USER_AGENT = "GiveLit/0.2 (+https://github.com/jcvillada/givelit)"


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    soup = BeautifulSoup(value, "lxml")
    cleaned = soup.get_text(" ", strip=True)
    return cleaned or None


def _parse_authors(author_string: str | None) -> List[str]:
    if not author_string:
        return []
    authors = [part.strip() for part in author_string.split(";") if part.strip()]
    return authors


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.strptime(raw, "%Y-%m").replace(day=1, tzinfo=UTC)
        except ValueError:
            try:
                return datetime.strptime(raw, "%Y").replace(month=1, day=1, tzinfo=UTC)
            except ValueError:
                return None


def _build_query(journal: JournalConfig, keywords: Iterable[str], days_back: int) -> str:
    quoted_terms = []
    for keyword in keywords:
        term = keyword.strip()
        if not term:
            continue
        if " " in term:
            quoted_terms.append(f'"{term}"')
        else:
            quoted_terms.append(term)

    if not quoted_terms:
        raise ValueError("At least one keyword is required.")

    keyword_query = " AND ".join(quoted_terms)
    journal_clause = f'JOURNAL:"{journal.container_title}"'
    segments = [keyword_query, journal_clause]

    if days_back > 0:
        end_date = datetime.now(tz=UTC).date()
        start_date = end_date - timedelta(days=days_back)
        segments.append(f'FIRST_PDATE:[{start_date} TO {end_date}]')

    return " ".join(segments)


@dataclass
class EuropePMCFetchResult:
    journal: JournalConfig
    papers: List[Paper]


class EuropePMCFetcher:
    """
    Retrieve journal articles from Europe PMC concurrently.
    """

    def __init__(self, timeout: float = 15.0, mailto: str | None = None) -> None:
        self._timeout = timeout
        self._mailto = mailto or "givelit@example.com"

    @property
    def timeout(self) -> float:
        return self._timeout

    async def collect(
        self,
        journals: Iterable[JournalConfig],
        keywords: List[str],
        days_back: int,
        max_results: int,
    ) -> List[EuropePMCFetchResult]:
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            tasks = [
                self.fetch_for_journal(client, journal, keywords, days_back, max_results)
                for journal in journals
            ]
            results = await asyncio.gather(*tasks)
        return results

    async def fetch_for_journal(
        self,
        client: httpx.AsyncClient,
        journal: JournalConfig,
        keywords: List[str],
        days_back: int,
        max_results: int,
    ) -> EuropePMCFetchResult:
        query = _build_query(journal, keywords, days_back)
        page_size = max(25, min(max_results * 3, 200))

        params = {
            "query": query,
            "pageSize": str(page_size),
            "format": "json",
            "resultType": "core",
        }

        response = await client.get(BASE_URL, params=params)
        response.raise_for_status()
        payload = response.json()

        results = payload.get("resultList", {}).get("result", [])

        papers: List[Paper] = []
        for item in results:
            title = _strip_html(item.get("title")) or "Untitled"
            abstract = _strip_html(item.get("abstractText"))
            authors = _parse_authors(item.get("authorString"))
            publication_date = _parse_date(item.get("firstPublicationDate"))

            url: str = ""
            doi = item.get("doi")
            if doi:
                url = f"https://doi.org/{doi}"
            elif item.get("pmcid"):
                url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{item['pmcid']}"
            elif item.get("id"):
                # Fallback to Europe PMC article page
                source = item.get("source", "MED")
                url = f"https://www.ebi.ac.uk/europepmc/article/{source}/{item['id']}"

            score = float(item.get("score", 0.0)) if item.get("score") else None

            paper = Paper(
                journal=journal.name,
                title=title,
                url=url,
                published=publication_date,
                authors=authors,
                summary=abstract,
                source_score=score,
            )
            papers.append(paper)

        return EuropePMCFetchResult(journal=journal, papers=papers[: max_results * 2])
