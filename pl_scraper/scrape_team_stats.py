"""Team match-stats ETL, team-driven with per-match dedup.
Output: pl_stats/{ShortName}/{Season}_events_stats.csv

Transform logic (build_rows, column selection) is local to this script — it's
not shared with the squad/player scrapers, so it doesn't belong in the package.
"""
from collections import defaultdict

import re
import pandas as pd
import requests

from pl import client, config

META_COLS = ["matchId", "gameweek", "kickoff", "team_id", "team", "venue"]

# Drop fine-grained shot placement: any att* with a placement suffix.
# Matches attSvLowCentre, attGoalHighLeft, attObxLeft, attRfGoal, attMissHighLeft...
PLACEMENT_RE = re.compile(
    r"^att(Bx|Obx|Sv|Hd|Lf|Rf|Cmiss|Miss|Goal|Ibox|Obox|Open|Obp)"
    r"(Low|High|Centre|Left|Right|Goal|Miss|Total|Target|Blocked|Post)",
)

# Redundant after the home/away merge (opponent's mirror exists).
DROP_EXACT = {
    "goalsConceded", "goalsConcededIbox", "goalsConcededObox",
    "cleanSheet", "goals"  # = (opponent goals == 0), derivable
}

# Noise / non-stats that flatten in from nested dicts.
DROP_NESTED_PREFIX = ("fastestPlayer",)

def keep_stat(col: str) -> bool:
    if col in DROP_EXACT:
        return False
    if col.startswith(DROP_NESTED_PREFIX):
        return False
    if PLACEMENT_RE.match(col):
        return False
    return True

def build_rows(match: dict, stats_payload: list[dict]) -> list[tuple]:
    """(team_id, shortName, row) per side present in the stats payload."""
    rows = []
    for block in stats_payload:
        if not (isinstance(block, dict) and "side" in block):
            continue
        side = block["side"]
        team_id = block["teamId"]
        stats = block.get("stats", {})

        if side == "Home":
            own, opp, venue = match["homeTeam"], match["awayTeam"], "Home"
        else:
            own, opp, venue = match["awayTeam"], match["homeTeam"], "Away"

        gf, ga = own.get("score", 0), opp.get("score", 0)
        result = "W" if gf > ga else "L" if gf < ga else "D"

        # Flatten one level of nested stat dicts -> {parent_child: value}.
        flat = {}
        for k, v in stats.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    flat[f"{k}_{sk}"] = sv
            else:
                flat[k] = v

        short = own.get("shortName", own.get("name"))
        rows.append((str(team_id), short, {
            "matchId": match["matchId"],
            "gameweek": match.get("matchWeek"),
            "kickoff": match["kickoff"],
            "team_id": str(team_id),
            "team": short,
            "venue": venue,
            **flat,
        }))
    return rows


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    meta = [c for c in META_COLS if c in df.columns]
    rest = sorted(c for c in df.columns if c not in meta and keep_stat(c))
    return df[meta + rest]


def run(season: int) -> None:
    label = config.season_dir_name(season)
    teams = client.get_teams(season)
    print(f"[{label}] {len(teams)} teams")

    short_by_id: dict[str, str] = {}
    matches_by_id: dict[str, dict] = {}

    for t in teams:
        tid = str(t["id"])
        short_by_id[tid] = t.get("shortName", t["name"])
        try:
            matches = client.get_team_matches(season, tid)
        except requests.RequestException as e:
            print(f"  team {tid} matches failed: {e} — skipping")
            continue
        for m in matches:
            matches_by_id[m["matchId"]] = m  # dedup: each match seen by 2 teams
        print(f"  {short_by_id[tid]}: {len(matches)} matches")

    print(f"[{label}] {len(matches_by_id)} unique matches")

    by_team: dict[str, dict] = defaultdict(lambda: {"name": None, "rows": []})
    for mid, m in matches_by_id.items():
        if m.get("period") in config.UNPLAYED_PERIODS:
            continue
        try:
            stats = client.get_match_stats(season, mid)
        except requests.RequestException as e:
            print(f"  match {mid} stats failed: {e} — skipping")
            continue
        if not stats:
            continue
        for team_id, short_name, row in build_rows(m, stats):
            by_team[team_id]["name"] = short_by_id.get(team_id, short_name)
            by_team[team_id]["rows"].append(row)

    for team_id, payload in by_team.items():
        if not payload["rows"]:
            continue

        new_df = pd.DataFrame(payload["rows"])
        new_df["matchId"] = new_df["matchId"].astype(str)

        team_dir = config.team_dir(team_id, payload["name"]) / "events_stats"
        team_dir.mkdir(parents=True, exist_ok=True)
        out_path = team_dir / f"{label}_events_stats.csv"

        # Idempotent upsert: merge with any existing file, dedup on matchId.
        if out_path.exists():
            old = pd.read_csv(out_path, dtype={"matchId": str})
            combined = pd.concat([old, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["matchId"], keep="last")
        else:
            combined = new_df

        combined = combined.sort_values("matchId").reset_index(drop=True)
        combined = _order_columns(combined)
        combined.to_csv(out_path, index=False)
        print(f"wrote {out_path}  ({len(combined)} matches, {len(combined.columns)} cols)")


if __name__ == "__main__":
    run(2026)