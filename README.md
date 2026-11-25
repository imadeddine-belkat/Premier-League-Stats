# ⚽ Premier League Stats

> A unified data repository combining **Fantasy Premier League (FPL)** gameweek statistics with a **historical Premier League archive** of match-event, player, and squad data spanning **2008-09 to the present**. Everything is exported as analysis-ready **CSV**, refreshed automatically every day.

[![Data Source](https://img.shields.io/badge/source-Official%20FPL%20%2B%20PL%20APIs-37003C)](https://fantasy.premierleague.com/api/)
[![Automation](https://img.shields.io/badge/automation-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/imadeddine-belkat/Premier-League-Stats/blob/main/.github/workflows/fpl_updater.yml)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Format](https://img.shields.io/badge/format-CSV%20%7C%20JSON-150458?logo=pandas&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/imadeddine-belkat/Premier-League-Stats/blob/main/LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [The Two Datasets](#the-two-datasets)
  - [1. FPL Gameweek Data (`fpl_scraper/fpl_stats/`)](#1-fpl-gameweek-data-fpl_scraperfpl_stats)
  - [2. Historical PL Archive (`pl_stats/`)](#2-historical-pl-archive-pl_stats)
- [The Crosswalk: Joining FPL ↔ PL](#the-crosswalk-joining-fpl--pl)
- [The Scraper Pipeline](#the-scraper-pipeline)
- [Automation](#automation)
- [Getting Started](#getting-started)
- [Quick Examples](#quick-examples)
- [Data Caveats](#data-caveats)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

This repository serves two complementary datasets that can be joined on a shared player ID:

| Dataset | What it is | Source | Coverage |
| --- | --- | --- | --- |
| **FPL Gameweek Data** | Per-player and per-team gameweek stats (points, minutes, xG/xA, ICT, prices, transfers) plus the full fixture list. | Official FPL API (`bootstrap-static`, `fixtures`, `element-summary`) | 2025-26, with merged season files back to 2016-17 |
| **Historical PL Archive** | Per-club match-event stats, per-match player stats, season-aggregate player stats, and squad rosters for 40+ clubs. | Premier League / PulseLive feeds | 2008-09 → present (each club's top-flight seasons only) |

Both halves key on the same **Opta/PulseLive player ID**, so FPL gameweek scoring can be joined directly to detailed PL event data.

---

## Repository Structure

```
Premier-League-Stats/
├── fpl_scraper/                       # FPL pipeline (code + output)
│   ├── fpl/                           # Reusable package
│   │   ├── config.py                  # Paths, constants, season resolution
│   │   ├── http.py                    # Retrying requests.Session (one source of truth)
│   │   ├── client.py                  # FPL endpoint wrapper + disk cache
│   │   └── io.py                      # Filename cleaning + dataframe shaping
│   ├── scrape_teams.py                # Per-team fixtures
│   ├── scrape_players.py              # Per-player + per-team gameweek stats
│   ├── scrape_fixtures.py             # Combined + per-team fixtures
│   ├── build_index_fpl.py             # player_code / team_code → metadata indexes
│   ├── merge_players.py               # Flatten per-team CSVs into one file per season
│   └── fpl_stats/                     # ── OUTPUT ──
│       ├── players/{Name}_{code}/{Season}_gw_stats.csv
│       ├── teams/{Team}_{code}/
│       │   ├── players/{Season}_all_players_gw.csv
│       │   └── fixtures/{Season}_fixtures.csv
│       ├── fixtures/{Season}_all_fixtures.csv
│       ├── _merged/players/{Season}_all_players_gw.csv   # all teams, one file/season
│       └── _index/
│           ├── _players_index.json    # player_code → {element, name} per season
│           └── _teams_index.json      # team_code → {id, name, short_name} per season
│
├── pl_stats/                          # Historical archive, by club
│   └── {Team}_{code}/
│       ├── events_stats/{Season}_events_stats.csv          # team match-event stats
│       ├── players_match_stats/{Season}_players_match_stats.csv  # per-player per-match
│       ├── players_stats/{Season}_players_stats.csv        # per-player season totals
│       └── squad/{Season}_squad.csv                        # roster + bio data
│   ├── _merged/events/{Season}_events_stats.csv            # all clubs, one file/season
│   ├── _index/{Season}_players.json                        # playerId → name
│   └── _badges/{code}.svg                                  # club crests
│
├── .github/workflows/fpl_updater.yml  # Daily scheduled refresh
└── requirements.txt
```

---

## The Two Datasets

### 1. FPL Gameweek Data (`fpl_scraper/fpl_stats/`)

Round-by-round FPL performance, scraped from the official API.

| File | Granularity | Contents |
| --- | --- | --- |
| `players/{Name}_{code}/{Season}_gw_stats.csv` | One player, all gameweeks | Points, minutes, goals, assists, xG, xA, ICT, BPS, defensive contributions, price, transfers in/out, selection |
| `teams/{Team}_{code}/players/{Season}_all_players_gw.csv` | One club's players, all gameweeks | Same columns, scoped to a single club |
| `teams/{Team}_{code}/fixtures/{Season}_fixtures.csv` | One club | That club's fixtures with difficulty ratings |
| `fixtures/{Season}_all_fixtures.csv` | League | Every fixture: kickoff, scores, home/away difficulty |
| `_merged/players/{Season}_all_players_gw.csv` | League | Every player's gameweek rows flattened into one table — the file you usually want for analysis |

**Key columns:** identity/join keys (`element`, `player_code`, `fixture_code`, `team_code`) lead each player row, followed by the scoring and underlying-stat columns.

### 2. Historical PL Archive (`pl_stats/`)

Nearly two decades of detailed event data for 40+ clubs, including historic top-flight sides such as Blackpool, Bolton, and Portsmouth.

| File | Granularity | Contents |
| --- | --- | --- |
| `events_stats/{Season}_events_stats.csv` | Team, per match | ~180 event metrics per game (passing zones, duels, xG, set pieces, defensive actions), keyed by `matchId` + `gameweek` |
| `players_match_stats/{Season}_players_match_stats.csv` | Player, per match | Per-90 contributions, ratings, carries, duels, keyed by `matchId` + `playerId` |
| `players_stats/{Season}_players_stats.csv` | Player, per season | Season-aggregate totals across ~140 metrics |
| `squad/{Season}_squad.csv` | Player | Roster with bio data: position, foot, nationality, DOB, height, weight, loan status |

`pl_stats/_merged/events/` provides the same event data combined across all clubs, one file per season.

---

## The Crosswalk: Joining FPL ↔ PL

The two datasets are linked by a single shared key — the **Opta/PulseLive player ID**:

- In FPL data it is `player_code` (and the index `_players_index.json` maps `player_code → {element, name}`).
- In PL data it is `playerId` / `pl_code` (and `_index/{Season}_players.json` maps `playerId → name`).

These are the **same numbers**, so you can join an FPL gameweek row to its detailed PL match stats directly:

```python
fpl.merge(pl_match, left_on=["player_code"], right_on=["playerId"])
```

Fixtures join on `fixture_code` (FPL) ↔ `matchId` (PL), both derived from the same canonical fixture code. Teams join on `team_code` (FPL) ↔ the club-folder code in `pl_stats/`.

---

## The Scraper Pipeline

The FPL side is a small package (`fpl_scraper/fpl/`) plus five entrypoint scripts. The package centralizes the parts that are easy to get wrong:

- **`http.py`** — one retrying `requests.Session` (urllib3 `Retry`: 5 attempts, exponential backoff, retries on 429/5xx). All callers share it, so retry logic lives in exactly one place.
- **`client.py`** — thin wrapper over the FPL endpoints. The expensive, high-volume `element-summary/{id}/` call (one request per player) is **disk-cached** under `fpl_cache/{season}/player_{id}.json`, with a polite delay between live fetches.
- **`config.py`** — paths, constants, and season resolution. The cache is scoped by the local clock, but the authoritative season label comes from the API itself (GW1 deadline), so filenames stay correct around the season rollover.
- **`io.py`** — filename sanitizing and dataframe shaping (drops fixture-derived columns, orders join keys first).

Run order (also encoded in the workflow):

| Step | Script | Output |
| --- | --- | --- |
| 1 | `scrape_teams.py` | Per-team fixtures |
| 2 | `scrape_players.py` | Per-player + per-team gameweek CSVs |
| 3 | `scrape_fixtures.py` | Combined + per-team fixtures |
| 4 | `build_index_fpl.py` | Player and team metadata indexes |
| 5 | `merge_players.py` | One flattened `_all_players_gw.csv` per season |

---

## Automation

- **FPL data:** `.github/workflows/fpl_updater.yml` runs daily at **05:17 UTC** and on manual dispatch.
- **PL data (`pl_stats/`):** `pl_scraper/auto_update.py` runs daily from Windows Task Scheduler on the maintainer's PC. It refetches the current season, then commits and pushes `pl_stats/`.

Both commit only when something changed.

---

## Getting Started

```bash
# 1. Clone
git clone https://github.com/imadeddine-belkat/Premier-League-Stats.git
cd Premier-League-Stats

# 2. Install dependencies
pip install -r requirements.txt          # requests, pandas

# 3. Run the FPL pipeline
cd fpl_scraper
python scrape_teams.py
python scrape_players.py
python scrape_fixtures.py
python build_index_fpl.py
python merge_players.py
```

You don't have to run anything to *use* the data — every CSV is already committed and can be read straight from a raw GitHub URL.

---

## Quick Examples

**Top FPL scorers, current season, loaded from the merged file:**

```python
import pandas as pd

url = ("https://raw.githubusercontent.com/imadeddine-belkat/Premier-League-Stats/"
       "main/fpl_scraper/fpl_stats/_merged/players/2025-26_all_players_gw.csv")
df = pd.read_csv(url)

totals = (df.groupby(["player_code", "second_name"])["total_points"]
            .sum().sort_values(ascending=False).head(10))
print(totals)
```

**Join FPL gameweek points to detailed PL match stats:**

```python
fpl = pd.read_csv(".../fpl_scraper/fpl_stats/_merged/players/2024-25_all_players_gw.csv")
pl  = pd.read_csv(".../pl_stats/Arsenal_3/players_match_stats/2024-25_players_match_stats.csv")

joined = fpl.merge(
    pl,
    left_on=["player_code", "fixture_code"],
    right_on=["playerId", "matchId"],
    how="inner",
)
```

---

## Data Caveats

- Historical `pl_stats` for a club only includes seasons in which that club actually played in the Premier League.
- FPL underlying metrics (xG, xA, ICT) reflect official API values and can be revised post-match by the provider.
- **Beware lookahead bias** when modelling expected points: any form/price/selection field the API updates *after* a gameweek deadline must be lagged by one gameweek or excluded from training features.
- Player names are UTF-8 and may contain accents; the canonical join key is the numeric ID (`player_code` / `playerId`), not the name.

---

## Contributing

Contributions, corrections, and historical backfills are welcome. Please open an issue describing the change before submitting a PR.

## License

Distributed under the MIT License. See [`LICENSE`](https://github.com/imadeddine-belkat/Premier-League-Stats/blob/main/LICENSE) for details.

> **Disclaimer:** This is an unofficial dataset, not affiliated with or endorsed by the Premier League or Fantasy Premier League. All data is sourced from publicly available APIs for educational and analytical use.
