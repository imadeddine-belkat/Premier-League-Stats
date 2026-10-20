"""Player season-stats ETL, team-driven.

Outputs:
  - pl_stats/{Team}/players_stats/{Season}_players_stats.csv
  - pl_stats/{Team}/players_stats/by_position/{position}/{Season}_{position}_players_stats.csv
  - players/by_position/{position}/{Season}_{position}_players_stats.csv
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from pl import client, config
from pl.parse import player_id_name


# Start conservatively.
# You can try 12 later if the API handles it without 429/403 errors.
MAX_WORKERS = 8


def _stats_row(
    season: int,
    label: str,
    team_id,
    team_name: str,
    pid,
    fallback_name,
) -> dict | None:
    payload = client.get_player_stats(season, pid)
    stats = payload.get("stats")

    if not stats:
        print(f"    No stats for {fallback_name} ({pid}) — skipped.")
        return None

    # Skip players where the stats object exists,
    # but every value is null/empty.
    has_real_stats = any(
        value not in (None, "", [], {})
        for value in stats.values()
    )

    if not has_real_stats:
        print(f"    Empty stats for {fallback_name} ({pid}) — skipped.")
        return None

    meta = payload.get("player") or {}

    return {
        "playerId": pid,
        "playerName": meta.get("name") or fallback_name,
        "position": meta.get("position"),

        # Use the historical team currently being scraped,
        # not currentTeam from the player payload.
        "team_name": team_name,
        "team_id": team_id,

        "nationality": (meta.get("country") or {}).get("country"),
        "season": label,
        **stats,
    }


def _fetch_team_players(
    season: int,
    label: str,
    team_id,
    team_name: str,
) -> list[dict]:
    """
    Read player stats sequentially.

    client.get_player_stats() uses cached_get(), so cached
    player JSON files are reused when available.
    """

    squad = client.get_squad(season, team_id)

    rows = []

    for entry in squad:
        player = player_id_name(entry)

        if not player:
            continue

        pid, name = player

        try:
            row = _stats_row(
                season,
                label,
                team_id,
                team_name,
                pid,
                name,
            )

            if row is not None:
                rows.append(row)

        except Exception as exc:
            print(
                f"    Failed stats for {name} ({pid}): {exc}"
            )

    return rows


def _normalize_positions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure every row has a usable position value.
    """

    if "position" in df.columns:
        df["position"] = (
            df["position"]
            .replace("", "Unknown")
            .fillna("Unknown")
        )
    else:
        df["position"] = "Unknown"

    return df


def run(season: int) -> None:
    label = config.season_dir_name(season)

    print(f"\n=== Player Stats for {label} ===")

    teams = client.get_teams(season)

    print(f"[{label}] {len(teams)} teams")

    if not teams:
        return

    all_season_rows = []

    for team in teams:
        tid = team.get("id")
        tname = team.get("shortName") or team.get("name")

        if not tid or not tname:
            continue

        print(f"  {tname}")

        rows = _fetch_team_players(
            season=season,
            label=label,
            team_id=tid,
            team_name=tname,
        )

        if not rows:
            print(f"    No valid player stats for {tname}.")
            continue

        # Stable ordering after concurrent fetching.
        rows.sort(
            key=lambda row: str(row.get("playerName") or "")
        )

        all_season_rows.extend(rows)

        # ---------------------------------------------------------
        # Team output directory
        # ---------------------------------------------------------

        out_dir = (
            config.team_dir(tid, tname)
            / "players_stats"
        )

        out_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ---------------------------------------------------------
        # 1. Save all players for this team
        # ---------------------------------------------------------

        df_team = pd.DataFrame(rows)
        df_team = _normalize_positions(df_team)

        out_path = (
            out_dir
            / f"{label}_players_stats.csv"
        )

        df_team.to_csv(
            out_path,
            index=False,
            encoding="utf-8",
        )

        print(
            f"    Saved: {out_path} "
            f"({len(df_team)} players)"
        )

        # ---------------------------------------------------------
        # 2. Save team stats by position
        # ---------------------------------------------------------

        for position, group_df in df_team.groupby(
            "position",
            dropna=False,
        ):
            pos_str = config.safe_name(
                str(position)
            )

            pos_dir = (
                out_dir
                / "by_position"
                / pos_str
            )

            pos_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            pos_path = (
                pos_dir
                / f"{label}_{pos_str}_players_stats.csv"
            )

            group_df.to_csv(
                pos_path,
                index=False,
                encoding="utf-8",
            )

    # -------------------------------------------------------------
    # 3. Save global season stats by position
    # -------------------------------------------------------------

    if not all_season_rows:
        print(
            f"  No valid player stats found for {label}."
        )
        return

    df_all = pd.DataFrame(all_season_rows)
    df_all = _normalize_positions(df_all)

    for position, group_df in df_all.groupby(
        "position",
        dropna=False,
    ):
        pos_str = config.safe_name(
            str(position)
        )

        global_pos_dir = (
            config.OUTPUT_ROOT
            / "players"
            / "by_position"
            / pos_str
        )

        global_pos_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        global_pos_path = (
            global_pos_dir
            / f"{label}_{pos_str}_players_stats.csv"
        )

        group_df.to_csv(
            global_pos_path,
            index=False,
            encoding="utf-8",
        )

    print(
        f"  Saved global stats by position "
        f"for {label} "
        f"({len(df_all)} players)."
    )


if __name__ == "__main__":
    run(2026)