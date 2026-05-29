import requests
import pandas as pd
import os
import time
import json
import re
from datetime import datetime
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = "fpl_stats"
CACHE_DIR = Path("fpl_cache")


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
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
    """Fetch element-summary with disk cache. Returns parsed JSON or None."""
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
    time.sleep(0.3)  # only sleep on real network hits, not cache reads
    return payload


def main():
    season = get_current_season()
    print(f"Starting Players Sync for {season}")

    base_url = "https://fantasy.premierleague.com/api/"
    session = make_session()

    print("Fetching master player list...")
    players_meta = get_with_retry(session, base_url + "bootstrap-static/").json()['elements']
    print(f"Processing {len(players_meta)} players...")

    all_player_gw_data = []

    for i, p in enumerate(players_meta):
        try:
            payload = cached_player_summary(session, season, base_url, p['id'])
        except requests.RequestException:
            print(f"    Skipping {p['id']} after retries")
            time.sleep(1.0)
            continue

        if not payload:
            continue

        history = payload.get('history', [])
        if not history:
            continue

        for gw in history:
            gw['player_code'] = p['code']
            gw['first_name'] = p['first_name']
            gw['second_name'] = p['second_name']
            all_player_gw_data.append(gw)

        p_name = f"{clean_filename(p['first_name'])}_{clean_filename(p['second_name'])}_{p['code']}"
        gw_dir = os.path.join(ROOT, "players", p_name)
        os.makedirs(gw_dir, exist_ok=True)
        pd.DataFrame(history).to_csv(os.path.join(gw_dir, f"{season}_gw_stats.csv"), index=False)

        if (i + 1) % 100 == 0:
            print(f" Progress: {i + 1}/{len(players_meta)}...")

    if all_player_gw_data:
        print("Saving aggregate index...")
        idx_dir = os.path.join(ROOT, "_index", "players")
        os.makedirs(idx_dir, exist_ok=True)
        pd.DataFrame(all_player_gw_data).to_csv(
            os.path.join(idx_dir, f"{season}_all_players_gw.csv"), index=False)

    print("Players sync complete!")


if __name__ == "__main__":
    main()