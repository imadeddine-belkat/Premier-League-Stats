"""Download Premier League team badge SVGs.

IMPORTANT (verified against the live CDN, June 2026):
The badge namespace is NOT per-season. Only the current slug `premierleague25`
serves files; older slugs (premierleague24, ...23, etc.) all return 502. A team's
badge is keyed solely by its numeric team id and is identical no matter which
season you discovered that team in.

So the strategy is:
  1. Walk every season via client.get_teams() to collect the full set of team ids
     that have ever appeared (promotion/relegation means each season differs).
  2. Fetch each unique badge ONCE from the single live slug.

Output: badges are season-agnostic, so they go in one flat dir:
    {OUTPUT_ROOT}/_badges/{team_id}.svg

The id -> club name map is NOT written here anymore; that lives in
`build_index.py`, which owns everything under {OUTPUT_ROOT}/_index/.
"""
from __future__ import annotations

import sys
import time

import requests

from pl import client, config

# Fixed live slug -- confirmed the only one that resolves. If the PL bumps this
# (e.g. to premierleague26 next season), change this single constant.
BADGE_SLUG = "premierleague25"
BADGE_URL = "https://resources.premierleague.com/{slug}/badges-alt/{team_id}.svg"

BADGE_DIR = config.OUTPUT_ROOT / "_badges"


def collect_team_ids(seasons: list[int]) -> set[str]:
    """Set of every team id seen across the given seasons. Reuses the cached_get
    layer in client, so re-runs are cheap and hit disk, not the API."""
    ids: set[str] = set()
    for season in seasons:
        teams = client.get_teams(season)
        for t in teams:
            tid = t.get("id")
            if tid is not None:
                ids.add(str(tid))
        print(f"{season}: {len(teams)} teams (running unique total {len(ids)})")
    return ids


def download_badge(team_id: str) -> bool:
    dest = BADGE_DIR / f"{team_id}.svg"
    if dest.exists():  # badges are static -- never re-fetch
        return True

    url = BADGE_URL.format(slug=BADGE_SLUG, team_id=team_id)
    resp = requests.get(url, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
    if resp.status_code != 200:
        print(f"  ! {team_id}: HTTP {resp.status_code}", file=sys.stderr)
        return False

    dest.write_bytes(resp.content)  # SVG served as XML bytes, not decoded text
    time.sleep(config.SLEEP_BETWEEN_CALLS)
    return True


def run(seasons: list[int] | None = None) -> None:
    seasons = seasons or config.DEFAULT_SEASONS
    BADGE_DIR.mkdir(parents=True, exist_ok=True)

    team_ids = collect_team_ids(seasons)
    print(f"\nfetching {len(team_ids)} unique badges -> {BADGE_DIR}")

    ok = 0
    for tid in sorted(team_ids, key=int):
        if download_badge(tid):
            ok += 1

    print(f"-> {ok}/{len(team_ids)} badges")


if __name__ == "__main__":
    run()