"""
Rendering utilities for CLI and HTML reports.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import Paper


def render_cli_report(
    console: Console,
    papers: Sequence[Paper],
    keywords: Iterable[str],
    journals: Iterable[str],
) -> None:
    """
    Print a compact table with hyperlinks to the console.
    """

    header = Text("GiveLit — recent literature radar", style="bold green")
    console.print(header)
    console.print(
        Text(
            f"Keywords: {', '.join(keywords)} | Journals: {', '.join(journals)}",
            style="dim",
        )
    )

    if not papers:
        console.print(Text("No papers matched the filters.", style="yellow"))
        return

    table = Table(
        show_lines=False,
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
        padding=(0, 1),
        title="Top Matches",
    )
    table.add_column("Journal", style="magenta", no_wrap=True)
    table.add_column("Title", style="white", overflow="fold")
    table.add_column("Date", style="green", no_wrap=True)
    table.add_column("Relevance", justify="right", style="bold cyan")
    table.add_column("Authors", style="dim", overflow="fold")

    for paper in papers:
        title = Text(paper.title.strip() or "Untitled")
        if paper.url:
            title.stylize(f"link {paper.url}")
        authors = ", ".join(paper.authors[:4])
        if len(paper.authors) > 4:
            authors += ", et al."

        table.add_row(
            paper.journal,
            title,
            paper.formatted_date(),
            f"{paper.relevance:.2f}",
            authors or "—",
        )

    console.print(table)


def write_html_report(
    papers: Sequence[Paper],
    keywords: Iterable[str],
    journals: Iterable[str],
    output_path: Path,
) -> Path:
    """
    Generate a minimalist HTML report with clickable cards.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    keywords_str = ", ".join(keywords)
    journals_str = ", ".join(journals)

    cards = []
    for paper in papers:
        authors = ", ".join(paper.authors[:6]) or "Unknown authors"
        if len(paper.authors) > 6:
            authors += ", et al."

        summary = paper.summary or "No abstract available."
        safe_summary = summary.replace("<", "&lt;").replace(">", "&gt;")

        card = f"""
        <article class="card">
            <header>
                <h2><a href="{paper.url}" target="_blank" rel="noopener">{paper.title}</a></h2>
                <div class="meta">
                    <span class="journal">{paper.journal}</span>
                    <span class="date">{paper.formatted_date()}</span>
                    <span class="score">Score: {paper.relevance:.2f}</span>
                </div>
            </header>
            <p class="authors">{authors}</p>
            <p class="summary">{safe_summary}</p>
        </article>
        """
        cards.append(card.strip())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>GiveLit Report</title>
    <style>
        :root {{
            color-scheme: light dark;
            --bg: #f5f5f5;
            --card: rgba(255, 255, 255, 0.85);
            --text: #222;
            --accent: #5c6ac4;
        }}
        body {{
            font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
            margin: 0 auto;
            padding: 2.5rem 1.5rem;
            max-width: 960px;
            background: var(--bg);
            color: var(--text);
        }}
        header.page-header {{
            margin-bottom: 2rem;
        }}
        header.page-header h1 {{
            margin: 0;
            font-size: 2.2rem;
        }}
        .meta {{
            display: flex;
            gap: 0.6rem;
            font-size: 0.85rem;
            color: #555;
            flex-wrap: wrap;
        }}
        .card {{
            background: var(--card);
            backdrop-filter: blur(10px);
            padding: 1.4rem;
            border-radius: 1.2rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 10px 24px rgba(0,0,0,0.08);
        }}
        .card h2 {{
            margin: 0 0 0.4rem 0;
            font-size: 1.35rem;
        }}
        .card a {{
            color: var(--accent);
            text-decoration: none;
        }}
        .card a:hover {{
            text-decoration: underline;
        }}
        .authors {{
            font-size: 0.9rem;
            color: #444;
        }}
        .summary {{
            font-size: 0.95rem;
            line-height: 1.45;
            margin-top: 0.8rem;
        }}
        footer {{
            margin-top: 2.5rem;
            font-size: 0.8rem;
            color: #777;
        }}
    </style>
</head>
<body>
    <header class="page-header">
        <h1>GiveLit Radar</h1>
        <p>Keywords: {keywords_str}</p>
        <p>Journals: {journals_str}</p>
        <p>Generated: {generated}</p>
    </header>
    <main>
        {' '.join(cards) if cards else '<p>No papers matched the filters.</p>'}
    </main>
    <footer>
        Crafted with GiveLit — stay on top of the literature.
    </footer>
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")
    return output_path

