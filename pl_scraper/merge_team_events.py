"""Concatenate a team's per-season event-stat CSVs into one CSV per team.

Input : pl_stats/{team_id}/events_stats/{season}_events_stats.csv
Output: pl_stats/_merged/teams/{team_id}_events_stats.csv  (+ all_team_events_stats.csv)

Each input row is one team's stats for one match. This just stacks every
season for a given team into a single file, adding a `season` column so rows
stay distinguishable. No pivoting, no derived fields.
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
    folder = os.path.basename(
        os.path.dirname(
            os.path.dirname(path)
        )
    )

    match = re.search(r"_(\d+)$", folder)

    return match.group(1) if match else folder


def main(root: str | None = None):
    if root:
        root = os.path.abspath(root)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root = os.path.join(os.path.dirname(script_dir), "pl_stats")
    if not os.path.isdir(root):
        raise SystemExit(f"root does not exist: {root}\n(cwd={os.getcwd()})")

    pattern = os.path.join(root, "*", "events_stats", "*_events_stats.csv")
    files = [f for f in glob(pattern) if "_merged" not in f]

    by_team: dict[str, list[pd.DataFrame]] = defaultdict(list)
    for f in files:
        df = pd.read_csv(f, dtype={"matchId": str})

        if "season" not in df.columns:
            season_col = pd.DataFrame(
                {"season": [season_of(f)] * len(df)},
                index=df.index,
            )

            df = pd.concat(
                [season_col, df],
                axis=1,
            )
        by_team[team_id_of(f)].append(df)
    print(f"Found {len(files)} files across {len(by_team)} teams")

    merged_dir = os.path.join(root, "_merged", "teams")
    os.makedirs(merged_dir, exist_ok=True)

    all_parts = []
    for team_id in sorted(by_team):
        merged = pd.concat(by_team[team_id], ignore_index=True)
        sort_keys = [k for k in ("season", "gameweek", "matchId") if k in merged.columns]
        if sort_keys:
            merged = merged.sort_values(sort_keys).reset_index(drop=True)
        all_parts.append(merged)
        merged.to_csv(
            os.path.join(merged_dir, f"{team_id}_events_stats.csv"), index=False)
        print(f"  {team_id}: {len(merged)} rows across "
              f"{merged['season'].nunique()} seasons")


if __name__ == "__main__":
    main()