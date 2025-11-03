# GiveLit

GiveLit is a Typer-powered CLI that keeps laboratory teams up to date with the latest, most relevant papers from the journals they care about. It queries Crossref for the chosen journals, scores candidates using the supplied keywords, and renders either a sleek terminal table or a minimalist HTML report with clickable cards.

## Requirements

- [pixi](https://pixi.sh) 0.48 or newer (dependency manager)

All runtime dependencies are specified in `pixi.toml`. No `pip` steps required.

## Quick start

```bash
# Solve the environment once
pixi install

# Show usage information
pixi run givelit --help

# Scan the default journals with a 30-day window and CLI output
pixi run givelit
```

## Custom searches

- Add more keywords by repeating `--keyword/-k`.
- Choose journals by repeating `--journal/-j` with either the predefined keys (`nature-microbiology`, `science`, `cell-systems`) or any container title recognised by Crossref (e.g. `"The ISME Journal"`).
- Control freshness with `--days/-d` (0 disables the date filter).
- Trim the list with `--limit/-n`.
- Generate a minimalist HTML report with `--format web --output path/to/report.html`.

Example:

```bash
pixi run givelit \
  --keyword metagenomics \
  --keyword longitudinal \
  --journal nature-microbiology \
  --journal science \
  --limit 8 \
  --days 120 \
  --format web \
  --output outputs/metagenomics.html
```

## How relevance works

GiveLit blends three signals:

1. Keyword density, with extra weight when terms appear in the title.
2. Crossref's native similarity score.
3. A recency boost within the requested window.

Results are sorted by this composite score before truncation to the requested limit.

## Project layout

- `src/givelit/cli.py` — Typer command definition and orchestration.
- `src/givelit/fetcher.py` — Crossref queries and response normalisation.
- `src/givelit/relevance.py` — Relevance scoring heuristics.
- `src/givelit/reporting.py` — Rich terminal table and HTML rendering.
- `pixi.toml` — Environment + task configuration.

## Notes

- The CLI uses a rich progress bar while contacting Crossref; network access is required.
- HTML reports are self-contained and easy to share.
- The project stays Python-only for maximum portability. Contributions are welcome!
