"""One-shot gameweek refresh of the PL stats for a single season.

Runs team event stats, squads and player season stats in order, after clearing
that season's disk cache (cached_get never expires, so stale files would
otherwise be reused forever).

Usage (from anywhere):
    python pl_scraper/scrape_gw.py            # current season (2026 -> 2026-27)
    python pl_scraper/scrape_gw.py --season 2025
    python pl_scraper/scrape_gw.py --keep-cache
"""
import argparse
import os
import shutil
from pathlib import Path

# config.CACHE_DIR is relative, so pin the cwd to this script's folder.
os.chdir(Path(__file__).resolve().parent)

from pl import client, config  # noqa: E402
import scrape_player_stats  # noqa: E402
import scrape_squads  # noqa: E402
import scrape_team_stats  # noqa: E402

CURRENT_SEASON = 2026


def clear_season_cache(season: int) -> None:
    cache = config.CACHE_DIR / config.season_dir_name(season)
    if cache.exists():
        shutil.rmtree(cache)
        print(f"Cleared cache: {cache}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=CURRENT_SEASON,
                    help="season start year (default: %(default)s)")
    ap.add_argument("--keep-cache", action="store_true",
                    help="reuse cached API responses instead of refetching")
    args = ap.parse_args()

    if not args.keep_cache:
        clear_season_cache(args.season)

    if not client.get_teams(args.season):
        raise SystemExit(f"No teams returned for season {args.season}; aborting.")

    scrape_team_stats.run(args.season)
    scrape_squads.run(args.season)
    scrape_player_stats.run(args.season)


if __name__ == "__main__":
    main()
