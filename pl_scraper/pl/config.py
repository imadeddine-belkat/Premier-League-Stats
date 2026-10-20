"""Endpoints, paths, constants, and shared helpers for the PL scrapers."""
import re
from datetime import date, datetime
from pathlib import Path

ROOT = "https://sdp-prem-prod.premier-league-prod.pulselive.com"

# Endpoints. _limit unified to 100 (stats scraper used 60; 100 is a safe
# superset — PL squads never exceed it and the teams list is ~20).
EP_TEAMS = ROOT + "/api/v1/competitions/8/seasons/{season}/teams?_limit=100"
EP_SQUAD = ROOT + "/api/v2/competitions/8/seasons/{season}/teams/{team_id}/squad"
EP_PLAYER_STATS = ROOT + "/api/v2/competitions/8/seasons/{season}/players/{player_id}/stats"
EP_MATCHES = ROOT + "/api/v2/matches?competition=8&season={season}&team={team_id}&_limit=60"
EP_MATCH_STATS = ROOT + "/api/v3/matches/{match_id}/stats"
EP_PLAYER_MATCH_STATS = (ROOT + "/api/v2/competitions/8/seasons/{season}/players/{player_id}/stats?match={match_id}")
EP_MATCH_LINEUPS = ROOT + "/api/v3/matches/{match_id}/lineups"

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_ROOT = _REPO_ROOT / "pl_stats"
CACHE_DIR = Path("cache")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Origin": "https://www.premierleague.com",
    "Referer": "https://www.premierleague.com/",
}

SLEEP_BETWEEN_CALLS = 0.3
REQUEST_TIMEOUT = (10, 60)
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 2.0

# Match periods that mean "not played yet" -> no stats to fetch.
UNPLAYED_PERIODS = {"PreMatch", "Postponed", "Abandoned"}

# Default season range shared by all three entry points.
DEFAULT_SEASONS = list(range(2027, 2008, -1))  # 2027 .. 2009


def season_dir_name(season_start_year: int) -> str:
    """2025 -> '2025-26'."""
    return f"{season_start_year}-{str(season_start_year + 1)[-2:]}"


def safe_name(name: str | None) -> str:
    """Filesystem-safe team/player name. Single canonical version — the three
    scrapers previously had two slightly different impls (player names dropped
    the & -> and rule). Unified here; folder names stay consistent across all
    outputs, which matters because they share the pl_stats/{Team} tree."""
    name = name or "unknown"
    return (
        name.replace(" ", "_")
        .replace("'", "")
        .replace("/", "_")
        .replace("&", "and")
    )


def calc_age(birth_str: str | None) -> int | None:
    if not birth_str or birth_str == "Unknown":
        return None
    try:
        b = datetime.strptime(birth_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = date.today()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))

def team_dir(team_id: int | str, team_name: str) -> Path:
    team_id = str(team_id)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # Any folder ending in _{team_id} belongs to this team.
    pattern = re.compile(rf"_{re.escape(team_id)}$")

    matches = [
        p
        for p in OUTPUT_ROOT.iterdir()
        if p.is_dir() and pattern.search(p.name)
    ]

    if matches:
        # Always reuse the same physical team folder.
        return sorted(matches)[0]

    # First time this team is seen.
    return OUTPUT_ROOT / safe_name(f"{team_name}_{team_id}")