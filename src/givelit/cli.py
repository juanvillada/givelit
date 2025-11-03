"""
Command line interface powered by Typer.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import List, Sequence

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

from .fetcher import CROSSREF_API, USER_AGENT, CrossrefFetcher
from .journals import resolve_journals
from .models import JournalConfig, Paper
from .relevance import compute_relevance
from .reporting import render_cli_report, write_html_report

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


class ReportFormat(str, Enum):
    CLI = "cli"
    WEB = "web"


def _normalise_keywords(keywords: Sequence[str]) -> List[str]:
    cleaned = [kw.strip() for kw in keywords if kw.strip()]
    if not cleaned:
        raise typer.BadParameter("Please provide at least one keyword.")
    return cleaned


async def _fetch_with_progress(
    fetcher: CrossrefFetcher,
    journals: Sequence[JournalConfig],
    keywords: List[str],
    days: int,
    max_results: int,
) -> List[Paper]:
    async with httpx.AsyncClient(
        timeout=fetcher.timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        base_url=CROSSREF_API.rsplit("/", 1)[0],
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

        async def run_for_journal(
            journal: JournalConfig,
        ) -> tuple[JournalConfig, List[Paper]]:
            papers = await fetcher.fetch_for_journal(
                client, journal, keywords, days, max_results
            )
            return journal, papers

        tasks = [asyncio.create_task(run_for_journal(journal)) for journal in journals]

        combined: List[Paper] = []
        with progress:
            task_id = progress.add_task("Requesting Crossref…", total=len(tasks))
            for coro in asyncio.as_completed(tasks):
                journal, papers = await coro
                combined.extend(papers)
                progress.update(
                    task_id,
                    advance=1,
                    description=f"{journal.name} ✓",
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
    output: Path = typer.Option(
        Path("givelit-report.html"),
        "--output",
        "-o",
        help="Path for the generated HTML when using --format web.",
        show_default=False,
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

    fetcher = CrossrefFetcher(timeout=15.0)

    try:
        papers = asyncio.run(
            _fetch_with_progress(fetcher, journal_configs, keyword_list, days, max_results)
        )
    except httpx.HTTPError as error:
        console.print(f"[red]Crossref request failed:[/red] {error}")
        raise typer.Exit(1) from error

    window = days if days > 0 else 30
    for paper in papers:
        compute_relevance(paper, keyword_list, window)

    now = datetime.now(tz=UTC)
    filtered: List[Paper] = []
    for paper in papers:
        if not paper.url:
            continue
        if days > 0 and paper.published:
            age_days = (now - paper.published).days
            if age_days > days:
                continue
        filtered.append(paper)

    papers = filtered

    papers.sort(
        key=lambda p: (
            p.relevance,
            p.published or p.source_score or 0.0,
        ),
        reverse=True,
    )

    top_papers = papers[:max_results]

    journal_names = [journal.name for journal in journal_configs]

    if report_format is ReportFormat.CLI:
        render_cli_report(console, top_papers, keyword_list, journal_names)
    else:
        destination = write_html_report(top_papers, keyword_list, journal_names, output)
        console.print(f"[green]Report saved to[/green] {destination}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
