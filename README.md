# ⚽ Premier League Stats

> A unified data repository combining live **Fantasy Premier League (FPL)** statistics for the 2025-26 season with a **historical Premier League archive** spanning from 2008-09 to the present.

[![Data Source](https://img.shields.io/badge/source-Official%20FPL%20API-37003C)](https://fantasy.premierleague.com/api/)
[![Automation](https://img.shields.io/badge/automation-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/)
[![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Format](https://img.shields.io/badge/format-CSV%20%7C%20JSON-150458?logo=pandas&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Dataset Reference](#dataset-reference)
  - [Historical PL Stats](#1-historical-pl-stats-pl_stats)
  - [Gameweek FPL Data](#2-gameweek-fpl-data)
  - [Individual Player Stats](#3-individual-player-stats)
  - [FPL Metadata](#4-fpl-metadata)
- [Update Cadence](#update-cadence)
- [Getting Started](#getting-started)
- [Use Cases](#use-cases)
- [Data Caveats](#data-caveats)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

This repository serves two complementary purposes:

| Component | Description | Coverage |
| :--- | :--- | :--- |
| **Active FPL Scraper** | A self-updating database of player and team statistics for the current FPL season, sourced from the official FPL API via custom Python scrapers. | 2025-26 |
| **Historical PL Archive** | A club-by-club archive of Premier League event statistics for 40+ current and historic clubs. | 2008-09 → present |

All data is exported as clean, analysis-ready **CSV** (with raw **JSON** retained for metadata), making it trivial to ingest into Pandas, R, Tableau, or Power BI.

---

## Repository Structure

```
Premier-League-Stats/
├── pl_stats/                          # Historical PL data, by club
│   └── {Team_Name}/
│       └── {Season}_events_stats.csv
├── fpl_stats/
│   ├── gameweeks/2025-26/             # Per-gameweek snapshots
│   │   ├── gw_{X}_players.csv
│   │   └── gw_{X}_teams.csv
│   ├── players/                       # Per-player season tracking
│   │   └── {Player_Name}_{ID}/
│   │       └── 2025-26_gw_stats.csv
│   └── metadata/2025-26/              # ID mappings & raw API dumps
│       ├── fixtures.csv
│       ├── fixtures.json
│       ├── players_id_list.csv
│       ├── teams_id_list.csv
│       └── raw_bootstrap_metadata.json
├── .github/workflows/
│   └── fpl_updater.yml                # Scheduled scrape automation
├── players_scrapper.py
├── teams_scrapper.py
└── requirements.txt
```

---

## Dataset Reference

### 1. Historical PL Stats (`pl_stats/`)

Nearly two decades of match and event data for 40+ clubs — including historic top-flight stints from sides such as Blackpool, Bolton Wanderers, and Portsmouth.

| Field | Value |
| :--- | :--- |
| **Path** | `pl_stats/{Team_Name}/{Season}_events_stats.csv` |
| **Granularity** | Team-specific event data, per season |
| **Range** | 2008-09 onwards (each club's PL participation only) |

### 2. Gameweek FPL Data

Round-by-round performance snapshots for the current season.

| File | Contents |
| :--- | :--- |
| `fpl_stats/gameweeks/2025-26/gw_{X}_players.csv` | Points, minutes, goals, assists, and underlying metrics for all players in Gameweek X |
| `fpl_stats/gameweeks/2025-26/gw_{X}_teams.csv` | Team-level performance metrics for Gameweek X |

### 3. Individual Player Stats

Track a single player across the season without filtering global gameweek files.

| Field | Value |
| :--- | :--- |
| **Path** | `fpl_stats/players/{Player_Name}_{ID}/2025-26_gw_stats.csv` |
| **Contents** | Cumulative and round-by-round statistics for one player |

### 4. FPL Metadata

Structural data mapping FPL API IDs to real football entities.

| File | Purpose |
| :--- | :--- |
| `fixtures.csv` / `fixtures.json` | Full PL schedule and Fixture Difficulty Ratings |
| `players_id_list.csv` | Master player-name → FPL ID dictionary |
| `teams_id_list.csv` | Master club-name → FPL ID dictionary |
| `raw_bootstrap_metadata.json` | Unprocessed `bootstrap-static` API dump |

---

## Update Cadence

| Dataset | Method | Frequency |
| :--- | :--- | :--- |
| **FPL Data** | Automated (`fpl_updater.yml`) | Regularly via GitHub Actions |
| **Historical PL Stats** | Manual push | End of each PL round |

---

## Getting Started

```bash
# 1. Clone
git clone https://github.com/imadeddine-belkat/Premier-League-Stats.git
cd Premier-League-Stats

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the scrapers
python players_scrapper.py
python teams_scrapper.py
```

**Quick load in Pandas:**

```python
import pandas as pd

gw1 = pd.read_csv("https://raw.githubusercontent.com/imadeddine-belkat/Premier-League-Stats/main/fpl_stats/gameweeks/2025-26/gw_1_players.csv")
top = gw1.sort_values("total_points", ascending=False).head(10)
print(top[["web_name", "team", "total_points", "minutes"]])
```

---

## Use Cases

- **FPL Managers** — Backtest transfer strategies and train Expected Points (xPts) models.
- **Football Analysts** — Study long-term PL trends, club tactical evolution, and historical event data back to 2008.
- **Data Visualization** — Drop CSVs straight into Pandas, R, Tableau, or Power BI for interactive dashboards.

---

## Data Caveats

- Historical `pl_stats` only includes seasons in which a given club actually competed in the Premier League.
- FPL underlying metrics (xG, xA, ICT) reflect official FPL API values and may be revised post-match by the provider.
- When training ML models, beware **lookahead bias** in any expected-points or form field that the API may update after a gameweek deadline — shift such features by one gameweek or exclude them.

---

## Contributing

Contributions, corrections, and historical-data backfills are welcome. Please open an issue describing the change before submitting a PR.

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

> **Disclaimer:** This is an unofficial dataset and is not affiliated with or endorsed by the Premier League or Fantasy Premier League. All data is sourced from publicly available APIs for educational and analytical use.
