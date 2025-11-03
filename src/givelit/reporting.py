"""
Rendering utilities for CLI and HTML reports.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import Paper


def _summarise_by_journal(papers: Sequence[Paper]) -> list[tuple[str, int, float]]:
    summary: dict[str, list[float]] = {}
    for paper in papers:
        bucket = summary.setdefault(paper.journal, [])
        bucket.append(paper.relevance)
    rows: list[tuple[str, int, float]] = []
    for journal, scores in summary.items():
        count = len(scores)
        avg = sum(scores) / count if count else 0.0
        rows.append((journal, count, avg))
    rows.sort(key=lambda item: (-item[1], -item[2], item[0].lower()))
    return rows


def _ascii_plot(rows: Sequence[tuple[str, int, float]], width: int = 18) -> list[str]:
    if not rows:
        return []
    max_count = max(count for _, count, _ in rows) or 1
    lines: list[str] = []
    for journal, count, avg in rows:
        length = int(round((count / max_count) * width)) if count else 0
        bar = "█" * max(length, 1 if count else 0)
        lines.append(
            f"{journal:<22} | {bar:<{width}} {count} paper{'s' if count != 1 else ''}, avg {avg:.2f}"
        )
    return lines


def render_cli_report(
    console: Console,
    papers: Sequence[Paper],
    keywords: Iterable[str],
    journals: Iterable[str],
    missing_journals: Sequence[str] | None = None,
) -> None:
    """
    Print a compact table with hyperlinks to the console.
    """

    header = Text("GiveLit — recent literature radar", style="bold green")
    console.print(header)
    console.print(
        Text(
            f"Keywords: {', '.join(f'\"{kw}\"' for kw in keywords)} | Journals: {', '.join(journals)}",
            style="dim",
        )
    )

    summary_rows = _ascii_plot(_summarise_by_journal(papers))
    if summary_rows:
        console.print(Text("Journal summary", style="bold cyan"))
        for line in summary_rows:
            console.print(Text(line, style="green"))
        console.print()

    if not papers:
        console.print(Text("No papers matched the filters.", style="yellow"))
        if missing_journals:
            console.print(
                Text(
                    f"No matches returned for: {', '.join(missing_journals)}",
                    style="dim",
                )
            )
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
    table.add_column("GiveLit score", justify="right", style="bold cyan")
    table.add_column("Days ago", justify="right", style="cyan")
    table.add_column("Authors", style="dim", overflow="fold")

    for paper in papers:
        title = Text(paper.title.strip() or "Untitled")
        if paper.url:
            title.stylize(f"link {paper.url}")
        authors = ", ".join(paper.authors[:4])
        if len(paper.authors) > 4:
            authors += ", et al."

        score_str = f"{paper.relevance:.2f}"
        age_str = "—"
        if paper.age_days is not None:
            age_str = str(paper.age_days)

        table.add_row(
            paper.journal,
            title,
            paper.formatted_date(),
            score_str,
            age_str,
            authors or "—",
        )

    console.print(table)
    if missing_journals:
        console.print(
            Text(
                f"No matches returned for: {', '.join(missing_journals)}",
                style="dim",
            )
        )


def write_html_report(
    papers: Sequence[Paper],
    keywords: Iterable[str],
    journals: Iterable[str],
    output_path: Path,
    missing_journals: Sequence[str] | None = None,
) -> Path:
    """
    Generate a minimalist HTML report with clickable cards.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    keywords_str = escape(", ".join(f'"{kw}"' for kw in keywords))
    journals_str = escape(", ".join(journals))

    summary_section = ""
    summary_rows = _ascii_plot(_summarise_by_journal(papers))
    if summary_rows:
        summary_body = escape("\n".join(summary_rows))
        summary_section = (
            "<section class=\"summary\">"
            "<h2>Journal summary</h2>"
            f"<pre class=\"summary-plot\">{summary_body}</pre>"
            "</section>"
        )

    cards = []
    for paper in papers:
        authors = ", ".join(paper.authors[:6]) or "Unknown authors"
        if len(paper.authors) > 6:
            authors += ", et al."

        summary = paper.summary or "No abstract available."
        safe_summary = escape(summary)
        title_text = escape(paper.title)
        url = escape(paper.url, quote=True)
        journal_label = escape(paper.journal)
        authors_text = escape(authors)
        date_text = escape(paper.formatted_date())
        if paper.age_days is not None:
            age_text = escape(f"Days ago: {paper.age_days}")
        else:
            age_text = escape("Days ago: unknown")

        card = f"""
        <article class="card">
            <header>
                <h2><a href="{url}" target="_blank" rel="noopener">{title_text}</a></h2>
                <div class="meta">
                    <span class="journal">Journal: {journal_label}</span>
                    <span class="separator">|</span>
                    <span class="date">{date_text}</span>
                    <span class="separator">|</span>
                    <span class="age">{age_text}</span>
                    <span class="separator">|</span>
                    <span class="score"><span class="badge">GiveLit score</span><span class="value">{paper.relevance:.2f}</span></span>
                </div>
            </header>
            <p class="authors">{authors_text}</p>
            <p class="summary">{safe_summary}</p>
        </article>
        """
        cards.append(card.strip())

    missing_block = ""
    if missing_journals:
        missing_list = escape(", ".join(missing_journals))
        missing_block = f'<p class="missing">No recent matches for: {missing_list}</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>GiveLit Report</title>
    <style>
        :root {{
            --bg: #040404;
            --text: #7fffb3;
            --accent: #00ff90;
            --muted: #3ddc84;
            --journal: #b8ffd6;
            --border: rgba(0, 255, 144, 0.35);
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            margin: 0 auto;
            padding: 2.5rem 1.5rem;
            max-width: 880px;
            background: var(--bg);
            color: var(--text);
            font-family: "IBM Plex Mono", "SFMono-Regular", Menlo, Consolas, "Liberation Mono", monospace;
            letter-spacing: 0.03em;
        }}
        .summary {{
            margin-bottom: 1.8rem;
        }}
        .summary h2 {{
            margin: 0 0 0.6rem 0;
            font-size: 1.1rem;
            color: var(--accent);
        }}
        .summary-plot {{
            margin: 0;
            padding: 1rem;
            border: 1px solid var(--border);
            border-radius: 0.6rem;
            background: rgba(0, 255, 144, 0.04);
            color: var(--text);
            white-space: pre;
            font-size: 0.9rem;
            line-height: 1.5;
        }}
        header.page-header {{
            margin-bottom: 2rem;
        }}
        header.page-header h1 {{
            margin: 0 0 0.75rem 0;
            font-size: 2rem;
            color: var(--accent);
        }}
        header.page-header p {{
            margin: 0.25rem 0;
        }}
        .card {{
            padding: 1.2rem;
            border: 1px solid var(--border);
            border-radius: 0.75rem;
            margin-bottom: 1.1rem;
            background: transparent;
        }}
        .card:last-child {{
            margin-bottom: 0;
        }}
        .card h2 {{
            margin: 0 0 0.6rem 0;
            font-size: 1.25rem;
            color: var(--accent);
        }}
        .card a {{
            color: var(--accent);
            text-decoration: none;
        }}
        .card a:hover {{
            text-decoration: underline;
        }}
        .meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            font-size: 0.85rem;
            color: var(--muted);
        }}
        .meta span {{
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }}
        .journal {{
            color: var(--journal);
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}
        .separator {{
            color: var(--muted);
            opacity: 0.6;
        }}
        .score {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.35rem 0.6rem;
            border: 1px solid var(--accent);
            border-radius: 0.4rem;
            background: rgba(0, 255, 144, 0.08);
        }}
        .score .badge {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }}
        .score .value {{
            font-weight: 600;
            color: var(--accent);
        }}
        .age {{
            color: var(--journal);
        }}
        .authors {{
            font-size: 0.9rem;
            margin: 0.9rem 0 0.6rem 0;
            color: var(--text);
        }}
        .summary {{
            font-size: 0.95rem;
            line-height: 1.6;
            color: var(--muted);
        }}
        .missing {{
            margin-top: 0.75rem;
            font-size: 0.9rem;
            color: var(--muted);
        }}
        footer {{
            margin-top: 2rem;
            font-size: 0.85rem;
            color: var(--muted);
        }}
    </style>
</head>
<body>
    <header class="page-header">
        <h1>GiveLit Radar</h1>
        <p>Keywords: {keywords_str}</p>
        <p>Journals: {journals_str}</p>
        <p>Generated: {generated}</p>
        {missing_block}
    </header>
    <main>
        {summary_section if summary_section else ''}
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
