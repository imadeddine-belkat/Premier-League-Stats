"""Single entrypoint for the whole PL pipeline. Edit the variables below, then
run this file (e.g. press Run in the IDE). No command-line arguments.

Order: scrapers -> index/badges -> mergers.
"""
import os
import shutil
from pathlib import Path

# config.CACHE_DIR is relative, so pin the cwd to this script's folder.
os.chdir(Path(__file__).resolve().parent)

from pl import client, config  # noqa: E402
import badges_scraper  # noqa: E402
import build_index  # noqa: E402
import merge_season_events  # noqa: E402
import merge_season_player_match_stats  # noqa: E402
import merge_season_players  # noqa: E402
import merge_team_events  # noqa: E402
import scrape_player_stats  # noqa: E402
import scrape_squads  # noqa: E402
import scrape_team_stats  # noqa: E402

# ----------------------------------------------------------------- settings
SEASONS = [2026]            # season start years to scrape (2026 -> 2026-27)
GAMEWEEK = None            # None = whole season; e.g. 7 = only that gameweek's match stats
CLEAR_CACHE = True          # cached_get never expires: True refetches SEASONS from the API

# scrapers
RUN_TEAM_STATS = True       # pl_stats/{Team}/events_stats
RUN_SQUADS = True           # pl_stats/{Team}/squad
RUN_PLAYER_STATS = True     # pl_stats/{Team}/players_stats (+ by_position)

# index / badges (walk every season in config.DEFAULT_SEASONS; cached, so cheap)
RUN_BUILD_INDEX = True      # pl_stats/_index
RUN_BADGES = False          # pl_stats/_badges (static, rarely needs a rerun)

# mergers (read everything under pl_stats, not just SEASONS)
RUN_MERGE_SEASON_EVENTS = True          # _merged/events
RUN_MERGE_TEAM_EVENTS = True            # _merged/teams
RUN_MERGE_SEASON_PLAYERS = True         # _merged/players
RUN_MERGE_PLAYER_MATCH_STATS = False    # _merged/players_match_stats (no scraper feeds it yet)
MERGE_PER_SEASON_PLAYERS = True         # also write one file per season, not just _all_
# -------------------------------------------------------------------------


def clear_season_cache(season: int) -> None:
    cache = config.CACHE_DIR / config.season_dir_name(season)
    if cache.exists():
        shutil.rmtree(cache)
        print(f"Cleared cache: {cache}")


def scrape(season: int) -> None:
    if CLEAR_CACHE:
        clear_season_cache(season)
    if not client.get_teams(season):
        raise SystemExit(f"No teams returned for season {season}; aborting.")
    if RUN_TEAM_STATS:
        scrape_team_stats.run(season, GAMEWEEK)
    if RUN_SQUADS:
        scrape_squads.run(season)
    if RUN_PLAYER_STATS:
        scrape_player_stats.run(season)


def main() -> None:
    for season in SEASONS:
        scrape(season)

    if RUN_BUILD_INDEX:
        build_index.run()
    if RUN_BADGES:
        badges_scraper.run()

    if RUN_MERGE_SEASON_EVENTS:
        merge_season_events.main()
    if RUN_MERGE_TEAM_EVENTS:
        merge_team_events.main()
    if RUN_MERGE_SEASON_PLAYERS:
        merge_season_players.main(per_season=MERGE_PER_SEASON_PLAYERS)
    if RUN_MERGE_PLAYER_MATCH_STATS:
        merge_season_player_match_stats.main()


if __name__ == "__main__":
    main()
