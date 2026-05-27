import requests
import pandas as pd
import os
import time
import re
from datetime import datetime

ROOT = "fpl_stats"


def get_current_season():
    now = datetime.now()
    if now.month >= 7:
        return f"{now.year}-{str(now.year + 1)[2:]}"
    return f"{now.year - 1}-{str(now.year)[2:]}"


def clean_filename(name):
    return re.sub(r'(?u)[^-\w.]', '', str(name).strip().replace(' ', '_'))


def main():
    season = get_current_season()
    print(f"🚀 Starting Players Sync for {season}")

    base_url = "https://fantasy.premierleague.com/api/"
    headers = {"User-Agent": "Mozilla/5.0"}

    gw_dir = os.path.join(ROOT, "gameweeks", season)
    os.makedirs(gw_dir, exist_ok=True)

    # 1. Fetch base player list
    print("Fetching master player list...")
    bootstrap_res = requests.get(base_url + "bootstrap-static/", headers=headers)
    players_meta = bootstrap_res.json()['elements']

    print(f"👤 Processing {len(players_meta)} players...")
    all_player_gw_data = []

    # 2. Loop through players
    for i, p in enumerate(players_meta):
        p_id = p['id']
        p_code = p['code']

        p_folder = f"{clean_filename(p['first_name'])}_{clean_filename(p['second_name'])}_{p_code}"
        p_dir = os.path.join(ROOT, "players", p_folder)

        p_res = requests.get(f"{base_url}element-summary/{p_id}/", headers=headers)
        if p_res.status_code != 200:
            continue

        history = p_res.json().get('history', [])
        if not history:
            continue

        for gw in history:
            gw['player_code'] = p_code
            gw['first_name'] = p['first_name']
            gw['second_name'] = p['second_name']
            all_player_gw_data.append(gw)

        os.makedirs(p_dir, exist_ok=True)
        pd.DataFrame(history).to_csv(
            os.path.join(p_dir, f"{season}_gw_stats.csv"), index=False)

        if (i + 1) % 100 == 0:
            print(f" Progress: {i + 1}/{len(players_meta)} players compiled...")

        time.sleep(0.1)

    # 3. Save merged Player GW files
    if all_player_gw_data:
        print("Saving merged player gameweek files...")
        df_all_players = pd.DataFrame(all_player_gw_data)
        for gw_num, df_gw in df_all_players.groupby('round'):
            df_gw.to_csv(os.path.join(gw_dir, f"gw_{int(gw_num)}_players.csv"), index=False)

    print("Players sync complete!")


if __name__ == "__main__":
    main()