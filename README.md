# GiveLit

GiveLit is a Typer-powered CLI that keeps laboratory teams up to date with the latest, most relevant papers from the journals they care about. It queries the Europe PMC literature service for the chosen journals, scores candidates using the supplied keywords, and renders either a sleek terminal table or a minimalist HTML report with clickable cards.

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
- Choose journals by repeating `--journal/-j` with either the predefined keys (see table below) or any journal title recognised by Europe PMC (e.g. `"The ISME Journal"`).
- Use `--journal all` to include every built-in journal in a single run.
- Control freshness with `--days/-d` (0 disables the date filter).
- Choose the ordering strategy with `--sort` (`score`, `recency`, or `journal`).
- Trim the list with `--limit/-n`.
- Generate a minimalist HTML report with `--format web --output path/to/report.html`.

Example:

```bash
pixi run givelit \
  --keyword metagenomics \
  --journal nature-microbiology \
  --journal cell-systems \
  --journal science \
  --limit 90 \
  --days 360 \
  --format web \
  --output outputs/metagenomics.html
```

All built-in journals in one go:

```bash
pixi run givelit \
  --keyword metagenomics \
  --keyword binning \
  --journal all \
  --limit 30 \
  --days 10 \
  --sort score \
  --format web \
  --output outputs/metagenomics.html
```

## Built-in journal keywords

| Journal                            | CLI key                             | Container title                |
|------------------------------------|-------------------------------------|--------------------------------|
| Cell                               | `cell`                              | Cell                           |
| Cell Genomics                      | `cell-genomics`                     | Cell Genomics                  |
| Cell Host & Microbe                | `cell-host-microbe`                 | Cell Host & Microbe            |
| Cell Metabolism                    | `cell-metabolism`                   | Cell Metabolism                |
| Cell Reports                       | `cell-reports`                      | Cell Reports                   |
| Cell Systems                       | `cell-systems`                      | Cell Systems                   |
| Communications Biology             | `communications-biology`            | Communications Biology         |
| Current Biology                    | `current-biology`                   | Current Biology                |
| ISME Communications                | `isme-communications`               | ISME Communications            |
| mBio                               | `mbio`                              | mBio                           |
| Molecular Biology and Evolution    | `molecular-biology-and-evolution`   | Molecular Biology and Evolution |
| mSystems                           | `msystems`                          | mSystems                       |
| Nature                             | `nature`                            | Nature                         |
| Nature Biotechnology               | `nature-biotechnology`              | Nature Biotechnology           |
| Nature Communications              | `nature-communications`             | Nature Communications          |
| Nature Ecology & Evolution         | `nature-ecology-evolution`          | Nature Ecology & Evolution     |
| Nature Machine Intelligence        | `nature-machine-intelligence`       | Nature Machine Intelligence    |
| Nature Methods                     | `nature-methods`                    | Nature Methods                 |
| Nature Microbiology                | `nature-microbiology`               | Nature Microbiology            |
| Nature Reviews Microbiology        | `nature-reviews-microbiology`       | Nature Reviews Microbiology    |
| Science                            | `science`                           | Science                        |
| Science Advances                   | `science-advances`                  | Science Advances               |
| The ISME Journal                   | `the-isme-journal`                  | The ISME Journal               |
| Trends in Biotechnology            | `trends-in-biotechnology`           | Trends in Biotechnology        |
| Trends in Ecology & Evolution      | `trends-in-ecology-evolution`       | Trends in Ecology & Evolution  |
| Trends in Microbiology             | `trends-in-microbiology`            | Trends in Microbiology         |

## How relevance works

GiveLit blends three signals for each returned article:

1. Keyword density, with extra weight when terms appear in the title or abstract.
2. Europe PMC's relevance score for the underlying query.
3. A recency boost that depends on how many days ago the work was published.

The precise scoring function is:

```
S = 6 * T + 2.5 * B + 4 * M + (R / 10) + 6 * F + 4 / (1 + D)
```

Where:

- `T` = number of keyword hits in the title.
- `B` = number of keyword hits in the title + abstract (case-insensitive).
- `M` = number of distinct query keywords that appear at least once.
- `R` = Europe PMC relevance score from the API response (0 when unavailable).
- `D` = days since publication (0 for same-day releases; if unknown, the recency terms are omitted).
- `F` = max(0, 1 - min(D, W) / W) with `W = max(requested_days, 30)` — a freshness factor bounded between 0 and 1.

The final score is rounded to two decimals. Scores and the associated `D` ("days ago") are displayed in both the CLI and HTML reports.

By default, GiveLit sorts by decreasing score and, within ties, by increasing `D`. Use `--sort recency` to prioritise fresher items or `--sort journal` to group by journal name.

Articles are grouped per journal and interleaved to guarantee that every requested journal is represented before the overall limit is reached. Remaining slots (if any) are backfilled by the highest-scoring papers regardless of journal.

## Data source

- GiveLit uses the [Europe PMC REST API](https://europepmc.org/RestfulWebService) to perform `keyword AND JOURNAL:"name"` searches with an optional publication date window.
- Returned metadata (title, authors, abstract, DOI, relevance score) is normalised and stored locally in memory only.
- Europe PMC requires no API keys, but we ship a descriptive `User-Agent` so that traffic is easy to attribute.

## Project layout

- `src/givelit/cli.py` — Typer command definition and orchestration.
- `src/givelit/fetcher.py` — Europe PMC queries and response normalisation.
- `src/givelit/relevance.py` — Relevance scoring heuristics.
- `src/givelit/reporting.py` — Rich terminal table and HTML rendering.
- `pixi.toml` — Environment + task configuration.

## Notes

- The CLI uses a rich progress bar while contacting Europe PMC; network access is required.
- HTML reports are self-contained and easy to share.
- The project stays Python-only for maximum portability. Contributions are welcome!

## Contact

For questions or feedback, reach out to Juan C. Villada at juanv@linux.com
