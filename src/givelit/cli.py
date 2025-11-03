"""
Command line interface powered by Typer.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import List, Sequence, Optional

import httpx
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from .fetcher import EuropePMCFetchResult, EuropePMCFetcher, USER_AGENT
from .journals import resolve_journals
from .models import JournalConfig, Paper
from .relevance import compute_relevance
from .reporting import render_cli_report, write_html_report

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


class ReportFormat(str, Enum):
    CLI = "cli"
    WEB = "web"


class SortStrategy(str, Enum):
    SCORE = "score"
    RECENCY = "recency"
    JOURNAL = "journal"


def _normalise_keywords(keywords: Sequence[str]) -> List[str]:
    cleaned = [kw.strip() for kw in keywords if kw.strip()]
    if not cleaned:
        raise typer.BadParameter("Please provide at least one keyword.")
    return cleaned


def _sort_papers(papers: List[Paper], strategy: SortStrategy) -> List[Paper]:
    def age_value(paper: Paper) -> int:
        return paper.age_days if paper.age_days is not None else 10**6

    if strategy is SortStrategy.SCORE:
        key = lambda p: (-p.relevance, age_value(p), p.title.lower())
    elif strategy is SortStrategy.RECENCY:
        key = lambda p: (age_value(p), -p.relevance, p.title.lower())
    else:  # SortStrategy.JOURNAL
        key = lambda p: (p.journal.lower(), -p.relevance, age_value(p))

    return sorted(papers, key=key)


async def _fetch_with_progress(
    fetcher: EuropePMCFetcher,
    journals: Sequence[JournalConfig],
    keywords: List[str],
    days: int,
    max_results: int,
) -> List[EuropePMCFetchResult]:
    async with httpx.AsyncClient(
        timeout=fetcher.timeout,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        progress = Progress(
            SpinnerColumn(style="green"),
            TextColumn("{task.description}", justify="left"),
            BarColumn(bar_width=24, style="cyan"),
            TextColumn("{task.completed}/{task.total}", style="cyan"),
            TimeElapsedColumn(),
            transient=True,
            console=console,
        )

        async def run_for_journal(journal: JournalConfig) -> EuropePMCFetchResult:
            return await fetcher.fetch_for_journal(
                client, journal, keywords, days, max_results
            )

        tasks = [asyncio.create_task(run_for_journal(journal)) for journal in journals]

        combined: List[EuropePMCFetchResult] = []
        with progress:
            task_id = progress.add_task("Querying Europe PMC…", total=len(tasks))
            for coro in asyncio.as_completed(tasks):
                result = await coro
                combined.append(result)
                progress.update(
                    task_id,
                    advance=1,
                    description=f"{result.journal.name} ✓",
                )
        return combined


@app.command()
def radar(
    keywords: List[str] = typer.Option(
        ["metagenomics"],
        "--keyword",
        "-k",
        help="Keywords used to rank relevance (repeat for multiple terms).",
    ),
    journals: List[str] = typer.Option(
        None,
        "--journal",
        "-j",
        help="Journal key or name to query (repeat for more than one).",
        show_default=False,
    ),
    max_results: int = typer.Option(
        12,
        "--limit",
        "-n",
        min=1,
        max=100,
        help="Maximum number of papers to include in the final report.",
    ),
    days: int = typer.Option(
        30,
        "--days",
        "-d",
        min=0,
        help="Only include papers published within the last N days.",
    ),
    report_format: ReportFormat = typer.Option(
        ReportFormat.CLI,
        "--format",
        "-f",
        case_sensitive=False,
        help="Choose between CLI output or a minimalist HTML report.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path for the generated HTML when using --format web.",
        show_default=False,
    ),
    sort_strategy: SortStrategy = typer.Option(
        SortStrategy.SCORE,
        "--sort",
        case_sensitive=False,
        help="Order results by score, recency, or journal name.",
    ),
) -> None:
    """
    Surface the most relevant recent papers for the chosen journals.
    """

    keyword_list = _normalise_keywords(keywords)
    journal_configs = resolve_journals(journals)

    console.print(
        f"[bold]Scanning[/bold] {len(journal_configs)} journal(s) for "
        f"[italic]{', '.join(keyword_list)}[/italic]…"
    )

    fetcher = EuropePMCFetcher(timeout=15.0)

    try:
        journal_chunks = asyncio.run(
            _fetch_with_progress(fetcher, journal_configs, keyword_list, days, max_results)
        )
    except httpx.HTTPError as error:
        console.print(f"[red]Europe PMC request failed:[/red] {error}")
        raise typer.Exit(1) from error

    papers: List[Paper] = []
    empty_journals: List[str] = []
    for result in journal_chunks:
        if result.papers:
            papers.extend(result.papers)
        else:
            empty_journals.append(result.journal.name)

    now = datetime.now(tz=UTC)
    recency_window = days if days > 0 else 0
    for paper in papers:
        compute_relevance(paper, keyword_list, recency_window, reference=now)

    filtered: List[Paper] = []
    for paper in papers:
        if not paper.url:
            continue
        if days > 0 and paper.age_days is not None and paper.age_days > days:
            continue
        filtered.append(paper)

    papers = filtered

    ordered = _sort_papers(papers, sort_strategy)
    top_papers = ordered[:max_results]

    journal_names = [journal.name for journal in journal_configs]

    option_context = {
        "limit": str(max_results),
        "days": "all time" if days == 0 else f"last {days} day{'s' if days != 1 else ''}",
        "sort": sort_strategy.value.title(),
        "format": report_format.value.upper(),
        "journal_count": str(len(journal_names)),
    }

    if report_format is ReportFormat.CLI:
        render_cli_report(
            console,
            top_papers,
            keyword_list,
            journal_names,
            option_context,
            missing_journals=empty_journals,
        )
    else:
        if output is None:
            keyword_slug = "__".join(kw.replace(" ", "-") for kw in keyword_list)
            timestamp = now.strftime("%Y%m%d-%H%M%S")
            output = Path(f"giveLit-output__{keyword_slug}__{timestamp}.html")
        else:
            if output.exists() and output.is_dir():
                keyword_slug = "__".join(kw.replace(" ", "-") for kw in keyword_list)
                timestamp = now.strftime("%Y%m%d-%H%M%S")
                output = output / f"giveLit-output__{keyword_slug}__{timestamp}.html"
            elif output.suffix == "":
                output = output.with_suffix(".html")
        destination = write_html_report(
            top_papers,
            keyword_list,
            journal_names,
            output,
            option_context,
            missing_journals=empty_journals,
        )
        console.print(f"[green]Report saved to[/green] {destination}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
