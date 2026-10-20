"""Merge player match stats by season and position.

Input:
  pl_stats/{Team}/players_match_stats/{Season}_players_match_stats.csv

Output:
  pl_stats/_merged/players_match_stats/{Season}_players_match_stats.csv
  pl_stats/_merged/players_match_stats/_all_players_match_stats.csv

  pl_stats/_merged/players_match_stats/by_position/{Position}/
      {Season}_{Position}_players_match_stats.csv
      _all_{Position}_players_match_stats.csv
"""

import os
import re
from collections import defaultdict
from glob import glob

import pandas as pd


ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "pl_stats",
    )
)


def season_of(path: str) -> str:
    match = re.search(
        r"(\d{4}-\d{2})",
        os.path.basename(path),
    )

    return match.group(1) if match else "unknown"


def safe_position(position) -> str:
    if pd.isna(position):
        return "Unknown"

    position = str(position).strip()

    if not position:
        return "Unknown"

    return (
        position
        .replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
    )


def main():
    # ---------------------------------------------------------
    # Find source files
    # ---------------------------------------------------------

    pattern = os.path.join(
        ROOT,
        "*",
        "players_match_stats",
        "*_players_match_stats.csv",
    )

    files = [
        path
        for path in glob(pattern)
        if "_merged" not in path
    ]

    print(f"Found {len(files)} player match stat files.")

    if not files:
        print("No files found.")
        return

    # ---------------------------------------------------------
    # Group by season
    # ---------------------------------------------------------

    by_season = defaultdict(list)

    for path in files:
        season = season_of(path)

        if season == "unknown":
            print(f"Skipping unknown season: {path}")
            continue

        df = pd.read_csv(
            path,
            dtype={
                "matchId": str,
                "playerId": str,
                "team_id": str,
            },
        )

        if df.empty:
            continue

        # Add season without fragmentation
        if "season" not in df.columns:
            season_column = pd.DataFrame(
                {
                    "season": [season] * len(df)
                },
                index=df.index,
            )

            df = pd.concat(
                [season_column, df],
                axis=1,
            )

        # Normalize position
        if "position" not in df.columns:
            df["position"] = "Unknown"
        else:
            df["position"] = (
                df["position"]
                .replace("", "Unknown")
                .fillna("Unknown")
            )

        by_season[season].append(df)

    print(
        "Seasons found:",
        ", ".join(sorted(by_season.keys())),
    )

    # ---------------------------------------------------------
    # Output paths
    # ---------------------------------------------------------

    merged_dir = os.path.join(
        ROOT,
        "_merged",
        "players_match_stats",
    )

    position_root = os.path.join(
        merged_dir,
        "by_position",
    )

    os.makedirs(
        merged_dir,
        exist_ok=True,
    )

    os.makedirs(
        position_root,
        exist_ok=True,
    )

    all_seasons = []

    # Holds:
    # position -> list[df]
    all_positions = defaultdict(list)

    # ---------------------------------------------------------
    # Merge each season
    # ---------------------------------------------------------

    for season in sorted(by_season):
        parts = by_season[season]

        merged = pd.concat(
            parts,
            ignore_index=True,
            sort=False,
        )

        # -----------------------------------------------------
        # Deduplicate
        # -----------------------------------------------------

        dedup_cols = [
            c for c in (
                "season",
                "playerId",
                "matchId",
                "team_id",
            )
            if c in merged.columns
        ]

        if len(dedup_cols) == 2:
            before = len(merged)

            merged = merged.drop_duplicates(
                subset=dedup_cols,
                keep="last",
            )

            removed = before - len(merged)

            if removed:
                print(
                    f"{season}: removed "
                    f"{removed} duplicates"
                )

        # -----------------------------------------------------
        # Sort
        # -----------------------------------------------------

        sort_cols = [
            col
            for col in (
                "gameweek",
                "matchId",
                "playerId",
            )
            if col in merged.columns
        ]

        if sort_cols:
            merged = (
                merged
                .sort_values(sort_cols)
                .reset_index(drop=True)
            )

        # -----------------------------------------------------
        # Save full season
        # -----------------------------------------------------

        season_path = os.path.join(
            merged_dir,
            f"{season}_players_match_stats.csv",
        )

        merged.to_csv(
            season_path,
            index=False,
            encoding="utf-8",
        )

        all_seasons.append(merged)

        print(
            f"{season}: "
            f"{len(merged)} rows "
            f"from {len(parts)} team files"
        )

        # -----------------------------------------------------
        # Save season by position
        # -----------------------------------------------------

        for position, group_df in merged.groupby(
            "position",
            dropna=False,
        ):
            pos_name = safe_position(position)

            pos_dir = os.path.join(
                position_root,
                pos_name,
            )

            os.makedirs(
                pos_dir,
                exist_ok=True,
            )

            pos_path = os.path.join(
                pos_dir,
                f"{season}_{pos_name}_players_match_stats.csv",
            )

            group_df.to_csv(
                pos_path,
                index=False,
                encoding="utf-8",
            )

            all_positions[pos_name].append(
                group_df
            )

    # ---------------------------------------------------------
    # Save all seasons master
    # ---------------------------------------------------------

    if all_seasons:
        final = pd.concat(
            all_seasons,
            ignore_index=True,
            sort=False,
        )

        final_path = os.path.join(
            merged_dir,
            "_all_players_match_stats.csv",
        )

        final.to_csv(
            final_path,
            index=False,
            encoding="utf-8",
        )

        print(
            f"\nAll seasons: "
            f"{len(final)} rows"
        )

    # ---------------------------------------------------------
    # Save all seasons by position
    # ---------------------------------------------------------

    for position, parts in all_positions.items():
        final_position = pd.concat(
            parts,
            ignore_index=True,
            sort=False,
        )

        pos_dir = os.path.join(
            position_root,
            position,
        )

        pos_path = os.path.join(
            pos_dir,
            f"_all_{position}_players_match_stats.csv",
        )

        final_position.to_csv(
            pos_path,
            index=False,
            encoding="utf-8",
        )

        print(
            f"{position}: "
            f"{len(final_position)} total rows"
        )


if __name__ == "__main__":
    main()