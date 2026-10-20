"""Merge all teams' per-season player-stat CSVs into one file per season,
as well as merging all teams' positional stats.

Input:
  pl_stats/{team_id}/players_stats/{season}_players_stats.csv
  pl_stats/{team_id}/players_stats/by_position/{position}/{season}_{position}_players_stats.csv
Output:
  pl_stats/_merged/players/{season}_players_stats.csv (+ all_players_stats.csv)
  pl_stats/_merged/players/by_position/{position}/{season}_{position}_players_stats.csv

Every team that played in a season contributes its players' rows; they're
stacked into a single season file (and separated by position).
"""
import os
import re
from collections import defaultdict
from glob import glob

import pandas as pd


def season_of(path: str) -> str:
    m = re.search(r"(\d{4}-\d{2})", os.path.basename(path))
    return m.group(1) if m else "unknown"


def team_id_of(path: str) -> str:
    # Handles both root players_stats and by_position nested paths
    # .../pl_stats/{team_id}/players_stats/...
    parts = path.split(os.sep)
    try:
        idx = parts.index("players_stats")
        return parts[idx - 1]
    except ValueError:
        return "unknown"


def main(root: str | None = None, per_season: bool = True):
    if root:
        root = os.path.abspath(root)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root = os.path.join(os.path.dirname(script_dir), "pl_stats")
    if not os.path.isdir(root):
        raise SystemExit(f"root does not exist: {root}\n(cwd={os.getcwd()})")

    # 1. Glob all CSVs in the players_stats tree (including by_position)
    pattern = os.path.join(root, "*", "players_stats", "**", "*_players_stats.csv")
    files = [f for f in glob(pattern, recursive=True) if "_merged" not in f]

    # Structure: by_category["All" or position_name][season] = [df1, df2...]
    by_category: dict[str, dict[str, list[pd.DataFrame]]] = defaultdict(lambda: defaultdict(list))

    print(f"Scanning {len(files)} files...")
    for f in files:
        season = season_of(f)

        # Determine if this is a general season file or a positional file
        parent_dir = os.path.basename(os.path.dirname(f))

        if parent_dir == "players_stats":
            category = "All"
        else:
            category = parent_dir # The position name (e.g., "M", "F", "D", "G", "Unknown")

        df = pd.read_csv(
            f,
            dtype={"matchId": str},
        )

        if "season" not in df.columns:
            season_col = pd.DataFrame(
                {"season": [season] * len(df)},
                index=df.index,
            )

            df = pd.concat(
                [season_col, df],
                axis=1,
            )

        by_category[category][season].append(df)

    print(f"Found files across {len(by_category['All'])} seasons.")

    # 2. Base merged output directory
    merged_base = os.path.join(root, "_merged", "players")
    os.makedirs(merged_base, exist_ok=True)

    # 3. Process and merge
    for category, season_dict in by_category.items():
        if category == "All":
            out_dir = merged_base
            prefix = ""
            print("\n=== Merging All Players ===")
        else:
            out_dir = os.path.join(merged_base, "by_position", category)
            os.makedirs(out_dir, exist_ok=True)
            prefix = f"{category}_"
            print(f"\n=== Merging Position: {category} ===")

        all_parts = []
        for season in sorted(season_dict):
            merged = pd.concat(
                season_dict[season],
                ignore_index=True,
                sort=False,
            )

            dedup_cols = [
                c for c in (
                    "season",
                    "team_id",
                    "playerId",
                )
                if c in merged.columns
            ]

            if dedup_cols:
                merged = merged.drop_duplicates(
                    subset=dedup_cols,
                    keep="last",
                )
            sort_keys = [k for k in ("gameweek", "matchId") if k in merged.columns]
            if sort_keys:
                merged = merged.sort_values(sort_keys).reset_index(drop=True)
            all_parts.append(merged)

            print(f"  {season}: {len(merged)} rows from {len(season_dict[season])} team files")

            if per_season:
                file_name = f"{season}_{prefix}players_stats.csv" if category != "All" else f"{season}_players_stats.csv"
                merged.to_csv(os.path.join(out_dir, file_name), index=False)

        # Create the "_all" master file for this category
        if all_parts:
            final = pd.concat(all_parts, ignore_index=True)
            master_name = f"_all_{prefix}players_stats.csv" if category != "All" else "_all_players_stats.csv"
            out_path = os.path.join(out_dir, master_name)
            final.to_csv(out_path, index=False)
            print(f"  -> Wrote {master_name}: {len(final)} rows, {len(final.columns)} cols")


if __name__ == "__main__":
    main()