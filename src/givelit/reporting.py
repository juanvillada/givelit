"""
Rendering utilities for CLI and HTML reports.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable, Sequence, Dict

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


def _coverage_level(paper: Paper, total_keywords: int) -> str:
    if total_keywords <= 0:
        return "unmatched"
    matched = paper.match_count
    if matched >= total_keywords:
        return "full"
    if matched >= max(total_keywords - 1, 1):
        return "near"
    if matched >= 1:
        return "partial"
    return "single"


def _group_by_coverage(papers: Sequence[Paper], total_keywords: int) -> Dict[str, list[Paper]]:
    groups: Dict[str, list[Paper]] = {"full": [], "near": [], "partial": [], "single": []}
    for paper in papers:
        level = _coverage_level(paper, total_keywords)
        if level not in groups:
            groups[level] = []
        groups[level].append(paper)
    return {level: groups[level] for level in ["full", "near", "partial", "single"] if groups[level]}


def _match_descriptor(items: Sequence[Paper], total_keywords: int) -> str:
    if total_keywords <= 0:
        return "no keywords configured"
    counts = sorted({max(0, min(total_keywords, paper.match_count)) for paper in items})
    plural = "" if total_keywords == 1 else "s"
    if not counts:
        return f"0 of {total_keywords} keyword{plural} matched"
    if len(counts) == 1:
        count = counts[0]
        if count >= total_keywords:
            return f"all {total_keywords} keyword{plural} matched"
        if count == 0:
            return f"0 of {total_keywords} keyword{plural} matched"
        return f"{count} of {total_keywords} keyword{plural} matched"
    return f"{counts[0]}–{counts[-1]} of {total_keywords} keyword{plural} matched"


def render_cli_report(
    console: Console,
    papers: Sequence[Paper],
    keywords: Iterable[str],
    journals: Iterable[str],
    options: dict[str, str] | None = None,
    missing_journals: Sequence[str] | None = None,
) -> None:
    """
    Print a compact table with hyperlinks to the console.
    """

    header = Text("GiveLit — recent literature radar", style="bold green")
    console.print(header)

    options = options or {}
    keywords_list = list(keywords)
    journals_list = list(journals)
    bullet = "✦"

    console.print(Text(f"{bullet} Keywords: {', '.join(f'\"{kw}\"' for kw in keywords_list)}", style="cyan"))
    console.print(Text(f"{bullet} Days window: {options.get('days', 'n/a')}", style="cyan"))
    console.print(Text(f"{bullet} Limit: {options.get('limit', 'n/a')}", style="cyan"))
    console.print(Text(f"{bullet} Sort: {options.get('sort', 'score')}", style="cyan"))
    coverage_mode = options.get('coverage', 'all')
    console.print(Text(f"{bullet} Coverage: {coverage_mode.title()}", style="cyan"))

    hits = {paper.journal for paper in papers}
    journal_buffer = [f"[{name}]" if name in hits else name for name in journals_list]
    journal_count = options.get('journal_count', str(len(journals_list)))
    console.print(Text(f"{bullet} Journals searched ({journal_count})", style="magenta"))
    if journal_buffer:
        per_line = 4
        chunks = [" | ".join(journal_buffer[i:i + per_line]) for i in range(0, len(journal_buffer), per_line)]
        for chunk in chunks:
            console.print(Text(f"    {chunk}", style="magenta"))
    console.print()

    total_keywords = len(keywords_list)
    groups = _group_by_coverage(papers, total_keywords)

    coverage_base_titles = {
        "full": "Full coverage",
        "near": "Near full coverage",
        "partial": "Partial coverage",
        "single": "Single keyword coverage",
    }

    if not papers:
        console.print(Text("No papers matched the filters.", style="yellow"))
        return

    if groups:
        console.print(Text("Coverage summary", style="bold cyan"))
        for level in ["full", "near", "partial", "single"]:
            items = groups.get(level)
            if not items:
                continue
            ascii_rows = _ascii_plot(_summarise_by_journal(items))
            if not ascii_rows:
                continue
            descriptor = _match_descriptor(items, total_keywords)
            coverage_title = f"{coverage_base_titles.get(level, level.title())} ({descriptor})"
            console.print(Text(coverage_title, style="bold magenta"))
            for line in ascii_rows:
                console.print(Text(line, style="green"))
            console.print()

    for level, items in groups.items():
        descriptor = _match_descriptor(items, total_keywords)
        title = f"{coverage_base_titles.get(level, level.title())} ({descriptor})"
        table = Table(
            show_lines=False,
            box=box.SIMPLE_HEAD,
            header_style="bold cyan",
            padding=(0, 1),
            title=title,
        )
        table.add_column("Journal", style="magenta", no_wrap=True)
        table.add_column("Title", style="white", overflow="fold")
        table.add_column("Date", style="green", no_wrap=True)
        table.add_column("GiveLit score", justify="right", style="bold cyan")
        table.add_column("Days ago", justify="right", style="cyan")
        table.add_column("Authors", style="dim", overflow="fold")

        for paper in items:
            row_title = Text(paper.title.strip() or "Untitled")
            if paper.url:
                row_title.stylize(f"link {paper.url}")
            authors = ", ".join(paper.authors[:4])
            if len(paper.authors) > 4:
                authors += ", et al."

            score_str = f"{paper.relevance:.2f}"
            age_str = "—"
            if paper.age_days is not None:
                age_str = str(paper.age_days)

            table.add_row(
                paper.journal,
                row_title,
                paper.formatted_date(),
                score_str,
                age_str,
                authors or "—",
            )

        console.print(table)
        console.print()



def write_html_report(
    papers: Sequence[Paper],
    keywords: Iterable[str],
    journals: Iterable[str],
    output_path: Path,
    options: dict[str, str] | None = None,
    missing_journals: Sequence[str] | None = None,
) -> Path:
    """
    Generate a minimalist HTML report with clickable cards.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    options = options or {}
    keywords_list = list(keywords)
    journals_list = list(journals)
    keywords_display = ", ".join(f'"{kw}"' for kw in keywords_list)

    hits = {paper.journal for paper in papers}
    meta_entries = [
        f"✦ Keywords: {keywords_display}",
        f"✦ Days window: {options.get('days', 'n/a')}",
        f"✦ Limit: {options.get('limit', 'n/a')}",
        f"✦ Sort: {options.get('sort', 'score')}",
        f"✦ Coverage: {options.get('coverage', 'all').title()}",
    ]
    meta_html = [f"<li>{escape(item)}</li>" for item in meta_entries]
    meta_html.append(f"<li>✦ Generated: {escape(generated)}</li>")
    journal_fragments: list[str] = []
    for index, name in enumerate(journals_list):
        if index:
            journal_fragments.append("<span class=\"journal-sep\">|</span>")
        classes = ["journal-pill"]
        if name in hits:
            classes.append("hit")
        journal_fragments.append(
            f"<span class=\"{' '.join(classes)}\">{escape(name)}</span>"
        )
    journal_body = "".join(journal_fragments)
    journal_label = escape(f"✦ Journals searched ({options.get('journal_count', str(len(journals_list)))})")
    meta_html.append(
        "<li class=\"journal-block\">"
        f"<span class=\"journal-block-label\">{journal_label}</span>"
        f"<div class=\"journal-pill-wrap\">{journal_body}</div>"
        "</li>"
    )
    meta_list = "".join(meta_html)

    coverage_groups = _group_by_coverage(papers, len(keywords_list))
    summary_sections: list[str] = []
    summary_base_titles = {
        "full": "Journal summary — full coverage",
        "near": "Journal summary — near coverage",
        "partial": "Journal summary — partial coverage",
        "single": "Journal summary — single keyword",
    }
    for level, items in coverage_groups.items():
        rows = _ascii_plot(_summarise_by_journal(items))
        if not rows:
            continue
        summary_body = escape("\n".join(rows))
        descriptor = _match_descriptor(items, len(keywords_list))
        title = f"{summary_base_titles.get(level, level.title())} ({descriptor})"
        summary_sections.append(
            "<section class=\"summary\">"
            f"<h2>{escape(title)}</h2>"
            f"<pre class=\"summary-plot\">{summary_body}</pre>"
            "</section>"
        )
    summary_section = "".join(summary_sections)

    cards: list[str] = []
    if coverage_groups:
        cards.append("<section class=\"coverage-groups\">")
    coverage_base_titles = {
        "full": "Full coverage",
        "near": "Near full coverage",
        "partial": "Partial coverage",
        "single": "Single keyword coverage",
    }
    for level, items in coverage_groups.items():
        descriptor = _match_descriptor(items, len(keywords_list))
        cards.append(f"<h2 class=\"coverage-heading\">{coverage_base_titles.get(level, level.title())} ({escape(descriptor)})</h2>")
        for paper in items:
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
    if coverage_groups:
        cards.append("</section>")

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
        .meta-list {{
            list-style: none;
            padding: 0;
            margin: 0 0 1rem 0;
            column-count: 2;
            column-gap: 1.4rem;
        }}
        @media (max-width: 720px) {{
            .meta-list {{
                column-count: 1;
            }}
        }}
        .meta-list li {{
            margin: 0.25rem 0;
            color: var(--muted);
            break-inside: avoid;
        }}
        .journal-block {{
            column-span: all;
            margin-top: 0.75rem;
        }}
        .journal-block-label {{
            display: block;
            margin-bottom: 0.4rem;
            color: var(--muted);
        }}
        .journal-pill-wrap {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.25rem;
            align-items: center;
        }}
        .journal-sep {{
            display: inline-flex;
            align-items: center;
            padding: 0 0.2rem;
            color: var(--muted);
            opacity: 0.55;
            font-size: 0.95rem;
        }}
        .journal-pill {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.2rem 0.65rem;
            border-radius: 0.45rem;
            border: 1px solid var(--border);
            color: var(--muted);
            background: rgba(0, 255, 144, 0.04);
            letter-spacing: 0.05em;
        }}
        .journal-pill.hit {{
            border-color: var(--accent);
            color: var(--accent);
            background: rgba(0, 255, 144, 0.12);
            box-shadow: 0 0 0 1px rgba(0, 255, 144, 0.08);
        }}
        .meta-list li.journal-item {{
            color: var(--text);
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
        .coverage-groups {{
            margin-top: 1.5rem;
        }}
        .coverage-heading {{
            margin: 1.6rem 0 0.6rem 0;
            font-size: 1.3rem;
            color: var(--accent);
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
        <ul class="meta-list">
            {meta_list}
        </ul>
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
