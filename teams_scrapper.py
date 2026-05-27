import requests
import pandas as pd
import os
import json
import re
from datetime import datetime

ROOT = "fpl_stats"


def get_current_season():
    now = datetime.now()
    if now.month >= 9:
        return f"{now.year}-{str(now.year + 1)[2:]}"
    return f"{now.year - 1}-{str(now.year)[2:]}"


def clean_filename(name):
    return re.sub(r'(?u)[^-\w.]', '', str(name).strip().replace(' ', '_'))


def main():
    season = get_current_season()
    print(f"Starting Teams & Metadata Sync for {season}")

    base_url = "https://fantasy.premierleague.com/api/"
    headers = {"User-Agent": "Mozilla/5.0"}

    meta_dir = os.path.join(ROOT, "metadata", season)
    gw_dir = os.path.join(ROOT, "gameweeks", season)
    os.makedirs(meta_dir, exist_ok=True)
    os.makedirs(gw_dir, exist_ok=True)

    # 1. Fetch & Save Bootstrap (Metadata)
    print("Fetching bootstrap-static data...")
    bootstrap_res = requests.get(base_url + "bootstrap-static/", headers=headers)
    bootstrap_data = bootstrap_res.json()

    with open(os.path.join(meta_dir, "raw_bootstrap_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(bootstrap_data, f, indent=4)

    # 2. Save ID & Code Mapping Lists
    print("Generating mapping lists with IDs and Codes...")
    team_info = {t['id']: {'name': t['name'], 'code': t['code']} for t in bootstrap_data['teams']}

    pd.DataFrame(bootstrap_data['teams'])[['id', 'code', 'name', 'short_name']].to_csv(
        os.path.join(meta_dir, "teams_id_list.csv"), index=False)

    player_rows = [{
        'id': p['id'],
        'code': p['code'],
        'first_name': p['first_name'],
        'second_name': p['second_name'],
        'team_id': p['team'],
        'team_code': p['team_code'],
        'team_name': team_info.get(p['team'], {}).get('name', 'Unknown')
    } for p in bootstrap_data['elements']]
    pd.DataFrame(player_rows).to_csv(os.path.join(meta_dir, "players_id_list.csv"), index=False)

    # 3. Fetch & Save Fixtures
    print("Fetching and parsing fixtures...")
    fixtures_res = requests.get(base_url + "fixtures/", headers=headers)
    fixtures_data = fixtures_res.json()

    with open(os.path.join(meta_dir, "fixtures.json"), "w", encoding="utf-8") as f:
        json.dump(fixtures_data, f, indent=4)
    pd.DataFrame(fixtures_data).to_csv(os.path.join(meta_dir, "fixtures.csv"), index=False)

    # 4. Build Team GW Data
    team_gw_data = []
    for f in fixtures_data:
        gw = f.get('event')
        if not gw:
            continue

        t_h, t_a = f['team_h'], f['team_a']
        th_data = team_info.get(t_h, {})
        ta_data = team_info.get(t_a, {})

        team_gw_data.append({
            'team_code': th_data.get('code'), 'team_name': th_data.get('name'),
            'gw': gw, 'is_home': True,
            'opponent_code': ta_data.get('code'), 'opponent_name': ta_data.get('name'),
            'team_score': f.get('team_h_score'), 'opponent_score': f.get('team_a_score'),
            'difficulty': f.get('team_h_difficulty'), 'finished': f.get('finished')
        })
        team_gw_data.append({
            'team_code': ta_data.get('code'), 'team_name': ta_data.get('name'),
            'gw': gw, 'is_home': False,
            'opponent_code': th_data.get('code'), 'opponent_name': th_data.get('name'),
            'team_score': f.get('team_a_score'), 'opponent_score': f.get('team_h_score'),
            'difficulty': f.get('team_a_difficulty'), 'finished': f.get('finished')
        })

    # 5. Save Per-Team Files (team-first, season-in-filename)
    if team_gw_data:
        df_all_teams = pd.DataFrame(team_gw_data)
        for t_id, info in team_info.items():
            team_name = clean_filename(info['name'])
            t_dir = os.path.join(ROOT, "teams", team_name)
            os.makedirs(t_dir, exist_ok=True)
            df_all_teams[df_all_teams['team_code'] == info['code']].sort_values('gw').to_csv(
                os.path.join(t_dir, f"{season}_gw_stats.csv"), index=False)

        # Per-gameweek aggregate
        for gw_num, df_gw in df_all_teams.groupby('gw'):
            df_gw.to_csv(os.path.join(gw_dir, f"gw_{int(gw_num)}_teams.csv"), index=False)

    print("Teams & Metadata sync complete!\n")


if __name__ == "__main__":
    main()