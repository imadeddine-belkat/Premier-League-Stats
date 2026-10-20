"""Merge all teams' event-stat CSVs into one file per season.

Input:
  pl_stats/{TeamName}_{team_id}/events_stats/{Season}_events_stats.csv

Output:
  pl_stats/_merged/events/{Season}_events_stats.csv
  pl_stats/_merged/events/_all_events_stats.csv

Identity rule:
  team_id is authoritative.
  Folder/team short name is ignored for deduplication.
"""

import os
import re
from collections import defaultdict
from glob import glob

import pandas as pd


def season_of(path: str) -> str:
    match = re.search(
        r"(\d{4}-\d{2})",
        os.path.basename(path),
    )

    return match.group(1) if match else "unknown"


def team_id_from_folder(path: str) -> str | None:
    """
    Examples:

      Arsenal_3   -> 3
      ARS_3       -> 3
      A_7         -> 7
      Villa_7     -> 7

    Folder name is NOT the team identity.
    Only the numeric suffix is.
    """
    folder = os.path.basename(
        os.path.dirname(
            os.path.dirname(path)
        )
    )

    match = re.search(r"_(\d+)$", folder)

    return match.group(1) if match else None


def main(root: str | None = None):
    if root:
        root = os.path.abspath(root)
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root = os.path.join(os.path.dirname(script_dir), "pl_stats")
    if not os.path.isdir(root):
        raise SystemExit(f"root does not exist: {root}\n(cwd={os.getcwd()})")

    # ---------------------------------------------------------
    # Find source files
    # ---------------------------------------------------------

    pattern = os.path.join(
        root,
        "*",
        "events_stats",
        "*_events_stats.csv",
    )

    files = [
        path
        for path in glob(pattern)
        if "_merged" not in path
    ]

    print(f"Found {len(files)} event files.")

    # ---------------------------------------------------------
    # Group by season
    # ---------------------------------------------------------

    by_season: dict[
        str,
        list[pd.DataFrame],
    ] = defaultdict(list)

    for path in files:
        season = season_of(path)
        folder_team_id = team_id_from_folder(path)

        if season == "unknown":
            print(f"Skipping unknown season: {path}")
            continue

        df = pd.read_csv(
            path,
            dtype={
                "matchId": str,
                "team_id": str,
            },
        )

        if df.empty:
            continue

        # -----------------------------------------------------
        # Ensure season exists
        # -----------------------------------------------------

        if "season" not in df.columns:
            df = pd.concat(
                [
                    pd.DataFrame(
                        {
                            "season": [season] * len(df)
                        },
                        index=df.index,
                    ),
                    df,
                ],
                axis=1,
            )

        # -----------------------------------------------------
        # Ensure team_id exists
        #
        # Prefer the team_id already inside the CSV.
        # Fall back to the numeric suffix from the folder.
        # -----------------------------------------------------

        if "team_id" not in df.columns:
            if folder_team_id is None:
                print(
                    f"Skipping file with no team_id: {path}"
                )
                continue

            df["team_id"] = folder_team_id

        else:
            df["team_id"] = (
                df["team_id"]
                .astype("string")
                .str.strip()
            )

            # Fill missing ids from folder suffix
            if folder_team_id is not None:
                df["team_id"] = df["team_id"].fillna(
                    folder_team_id
                )

        by_season[season].append(df)

    print(
        f"Found {len(by_season)} seasons."
    )

    # ---------------------------------------------------------
    # Output directory
    # ---------------------------------------------------------

    merged_dir = os.path.join(
        root,
        "_merged",
        "events",
    )

    os.makedirs(
        merged_dir,
        exist_ok=True,
    )

    all_parts = []

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
        # Normalize IDs
        # -----------------------------------------------------

        if "matchId" in merged.columns:
            merged["matchId"] = (
                merged["matchId"]
                .astype("string")
                .str.strip()
            )

        if "team_id" in merged.columns:
            merged["team_id"] = (
                merged["team_id"]
                .astype("string")
                .str.strip()
            )

        # -----------------------------------------------------
        # Deduplicate
        #
        # Same match + same team = same logical row.
        #
        # Arsenal_3 and ARS_3 are therefore treated as
        # the same source team when team_id == 3.
        # -----------------------------------------------------

        required = {
            "matchId",
            "team_id",
        }

        if required.issubset(merged.columns):
            before = len(merged)

            merged = merged.drop_duplicates(
                subset=[
                    "matchId",
                    "team_id",
                ],
                keep="last",
            )

            removed = before - len(merged)

            if removed:
                print(
                    f"  {season}: removed "
                    f"{removed} duplicate rows"
                )

        # -----------------------------------------------------
        # Remove filesystem-only metadata
        # -----------------------------------------------------

        if "team_folder" in merged.columns:
            merged = merged.drop(
                columns=["team_folder"]
            )

        # -----------------------------------------------------
        # Sort
        # -----------------------------------------------------

        sort_keys = [
            key
            for key in (
                "gameweek",
                "kickoff",
                "matchId",
                "team_id",
            )
            if key in merged.columns
        ]

        if sort_keys:
            merged = (
                merged
                .sort_values(sort_keys)
                .reset_index(drop=True)
            )

        # -----------------------------------------------------
        # Save season
        # -----------------------------------------------------

        out_path = os.path.join(
            merged_dir,
            f"{season}_events_stats.csv",
        )

        merged.to_csv(
            out_path,
            index=False,
            encoding="utf-8",
        )

        all_parts.append(merged)

        print(
            f"  {season}: "
            f"{len(merged)} rows "
            f"from {len(parts)} source files"
        )

    # ---------------------------------------------------------
    # Merge all seasons
    # ---------------------------------------------------------

    if all_parts:
        final = pd.concat(
            all_parts,
            ignore_index=True,
            sort=False,
        )

        # Safety dedup across all seasons too
        dedup_cols = [
            col
            for col in (
                "season",
                "matchId",
                "team_id",
            )
            if col in final.columns
        ]

        if len(dedup_cols) == 3:
            final = final.drop_duplicates(
                subset=dedup_cols,
                keep="last",
            )

        final_path = os.path.join(
            merged_dir,
            "_all_events_stats.csv",
        )

        final.to_csv(
            final_path,
            index=False,
            encoding="utf-8",
        )

        print(
            "\n"
            f"Wrote master: "
            f"{len(final)} rows, "
            f"{len(final.columns)} columns"
        )


if __name__ == "__main__":
    main()