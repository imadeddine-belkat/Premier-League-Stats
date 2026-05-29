import requests
import pandas as pd
import os
import time
import json
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = "fpl_stats"
CACHE_DIR = Path("fpl_cache")

FIXTURE_COLS = ["fixture", "opponent_team", "was_home", "kickoff_time",
                "team_h_score", "team_a_score", "round"]

SUM_COLS = ["total_points", "minutes", "goals_scored", "assists", "clean_sheets",
            "goals_conceded", "own_goals", "penalties_saved", "penalties_missed",
            "yellow_cards", "red_cards", "saves", "bonus", "bps",
            "influence", "creativity", "threat",
            "clearances_blocks_interceptions", "recoveries", "tackles",
            "defensive_contribution", "starts",
            "expected_goals", "expected_assists", "expected_goal_involvements",
            "expected_goals_conceded", "transfers_balance", "selected",
            "transfers_in", "transfers_out"]


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=2.0,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["GET"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    return s


def get_current_season():
    now = datetime.now()
    if now.month >= 8:
        return f"{now.year}-{str(now.year + 1)[2:]}"
    return f"{now.year - 1}-{str(now.year)[2:]}"


def clean_filename(name):
    return re.sub(r'(?u)[^-\w.]', '', str(name).strip().replace(' ', '_'))


def get_with_retry(session, url, max_attempts=5, base=2.0):
    for attempt in range(1, max_attempts + 1):
        try:
            return session.get(url, timeout=(10, 30))
        except requests.RequestException as e:
            if attempt == max_attempts:
                raise
            wait = base * (2 ** (attempt - 1))
            print(f"    retry {attempt}/{max_attempts} after {wait:.0f}s: {type(e).__name__}")
            time.sleep(wait)


def cached_player_summary(session, season, base_url, p_id):
    cache_path = CACHE_DIR / season / f"player_{p_id}.json"
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    res = get_with_retry(session, f"{base_url}element-summary/{p_id}/")
    if res.status_code != 200:
        return None
    payload = res.json()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f)
    time.sleep(0.3)
    return payload


def write_metadata(season, boot, team_lookup):
    """Dump ID mappings & raw bootstrap so other scripts share one source of truth."""
    meta_dir = os.path.join(ROOT, "metadata", season)
    os.makedirs(meta_dir, exist_ok=True)

    with open(os.path.join(meta_dir, "raw_bootstrap_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(boot, f)

    pd.DataFrame(boot["teams"])[["id", "name", "short_name"]].to_csv(
        os.path.join(meta_dir, "teams_id_list.csv"), index=False)

    pd.DataFrame([{
        "id": p["id"], "code": p["code"], "first_name": p["first_name"],
        "second_name": p["second_name"], "team": p["team"],
        "team_name": team_lookup.get(p["team"], ""), "element_type": p["element_type"],
    } for p in boot["elements"]]).to_csv(
        os.path.join(meta_dir, "players_id_list.csv"), index=False)


def main():
    season = get_current_season()
    print(f"Starting Team-aggregate GW Sync for {season}")

    base_url = "https://fantasy.premierleague.com/api/"
    session = make_session()

    print("Fetching bootstrap-static...")
    boot = get_with_retry(session, base_url + "bootstrap-static/").json()
    players_meta = boot["elements"]
    team_lookup = {t["id"]: t["name"] for t in boot["teams"]}

    write_metadata(season, boot, team_lookup)

    print(f"Processing {len(players_meta)} players across {len(team_lookup)} teams...")

    buckets = defaultdict(list)  # (team_id, round) -> [player gw dicts]

    for i, p in enumerate(players_meta):
        try:
            payload = cached_player_summary(session, season, base_url, p["id"])
        except requests.RequestException:
            print(f"    Skipping {p['id']} after retries")
            time.sleep(1.0)
            continue
        if not payload:
            continue
        history = payload.get("history", [])
        if not history:
            continue
        for gw in history:
            buckets[(p["team"], gw["round"])].append(gw)

        if (i + 1) % 100 == 0:
            print(f" Progress: {i + 1}/{len(players_meta)}...")

    if not buckets:
        print("No data collected.")
        return

    team_rows = defaultdict(list)  # team_id -> [aggregated gw rows]

    for (team_id, rnd), gws in buckets.items():
        df = pd.DataFrame(gws)
        agg = {}

        for c in FIXTURE_COLS:
            if c in df.columns:
                agg[c] = df[c].iloc[0]

            # opponent_team is an ID -> add the readable name
        if "opponent_team" in agg:
            agg["opponent_team_name"] = team_lookup.get(agg["opponent_team"], str(agg["opponent_team"]))

        for c in SUM_COLS:
            if c in df.columns:
                agg[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).sum()

        agg["ict_index"] = round(
            (agg.get("influence", 0) + agg.get("creativity", 0) + agg.get("threat", 0)) / 10, 1)
        if "value" in df.columns:
            agg["avg_value"] = round(pd.to_numeric(df["value"], errors="coerce").mean(), 1)

        agg["team_id"] = team_id
        agg["team"] = team_lookup.get(team_id, str(team_id))
        agg["players_used"] = len(df)
        agg["players_played"] = int((pd.to_numeric(df["minutes"], errors="coerce") > 0).sum())

        team_rows[team_id].append(agg)

    print(f"Writing {len(team_rows)} team directories...")
    idx_all = []
    for team_id, rows in team_rows.items():
        team_name = clean_filename(team_lookup.get(team_id, str(team_id)))
        base_dir = os.path.join(ROOT, "teams", team_name)

        tdf = pd.DataFrame(rows).sort_values("round")

        # gameweeks/ : the aggregated per-GW squad stats
        gw_dir = os.path.join(base_dir, "gameweeks")
        os.makedirs(gw_dir, exist_ok=True)
        tdf.to_csv(os.path.join(gw_dir, f"{season}_gw_stats.csv"), index=False)

        # fixtures/ : just the match-level facts, one row per fixture, no stats
        fx_dir = os.path.join(base_dir, "fixtures")
        os.makedirs(fx_dir, exist_ok=True)
        fx_cols = [c for c in FIXTURE_COLS if c in tdf.columns]
        tdf[fx_cols].drop_duplicates("fixture").sort_values("round").to_csv(
            os.path.join(fx_dir, f"{season}_fixtures.csv"), index=False)

        idx_all.append(tdf)

    idx_dir = os.path.join(ROOT, "_index", "teams")
    os.makedirs(idx_dir, exist_ok=True)
    pd.concat(idx_all, ignore_index=True).sort_values(["team", "round"]).to_csv(
        os.path.join(idx_dir, f"{season}_all_teams_gw.csv"), index=False)

    print("Team-aggregate sync complete!")


if __name__ == "__main__":
    main()