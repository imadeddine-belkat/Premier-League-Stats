import requests
import pandas as pd
import os
import json
import re
from datetime import datetime


def get_current_season():
    now = datetime.now()
    if now.month >= 7:
        return f"{now.year}-{str(now.year + 1)[2:]}"
    return f"{now.year - 1}-{str(now.year)[2:]}"


def clean_filename(name):
    return re.sub(r'(?u)[^-\w.]', '', str(name).strip().replace(' ', '_'))


def main():
    season = get_current_season()
    print(f"🚀 Starting Teams & Metadata Sync for {season}")

    base_url = "https://fantasy.premierleague.com/api/"
    headers = {"User-Agent": "Mozilla/5.0"}
    os.makedirs(season, exist_ok=True)

    # 1. Fetch & Save Bootstrap (Metadata)
    print("📥 Fetching bootstrap-static data...")
    bootstrap_res = requests.get(base_url + "bootstrap-static/", headers=headers)
    bootstrap_data = bootstrap_res.json()

    with open(os.path.join(season, "raw_bootstrap_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(bootstrap_data, f, indent=4)

    # 2. Save ID Lists
    print("📊 Generating ID mapping lists...")
    team_dict = {t['id']: t['name'] for t in bootstrap_data['teams']}
    pd.DataFrame(bootstrap_data['teams'])[['id', 'name', 'short_name', 'code']].to_csv(
        os.path.join(season, "teams_id_list.csv"), index=False)

    player_rows = [{'id': p['id'], 'first_name': p['first_name'], 'second_name': p['second_name'], 'team_id': p['team'],
                    'team_name': team_dict.get(p['team'])} for p in bootstrap_data['elements']]
    pd.DataFrame(player_rows).to_csv(os.path.join(season, "players_id_list.csv"), index=False)

    # 3. Fetch & Save Fixtures / Team GW Data
    print("📅 Fetching and parsing fixtures...")
    fixtures_res = requests.get(base_url + "fixtures/", headers=headers)
    fixtures_data = fixtures_res.json()

    with open(os.path.join(season, "fixtures.json"), "w", encoding="utf-8") as f:
        json.dump(fixtures_data, f, indent=4)

    team_gw_data = []
    for f in fixtures_data:
        gw = f.get('event')
        if not gw: continue

        t_h, t_a = f['team_h'], f['team_a']

        team_gw_data.append(
            {'team_id': t_h, 'team_name': team_dict.get(t_h), 'gw': gw, 'is_home': True, 'opponent_id': t_a,
             'opponent_name': team_dict.get(t_a), 'team_score': f.get('team_h_score'),
             'opponent_score': f.get('team_a_score'), 'difficulty': f.get('team_h_difficulty'),
             'finished': f.get('finished')})
        team_gw_data.append(
            {'team_id': t_a, 'team_name': team_dict.get(t_a), 'gw': gw, 'is_home': False, 'opponent_id': t_h,
             'opponent_name': team_dict.get(t_h), 'team_score': f.get('team_a_score'),
             'opponent_score': f.get('team_h_score'), 'difficulty': f.get('team_a_difficulty'),
             'finished': f.get('finished')})

    # Save Team Data
    if team_gw_data:
        df_all_teams = pd.DataFrame(team_gw_data)
        for t_id, t_name in team_dict.items():
            t_dir = os.path.join(season, "teams", f"{clean_filename(t_name)}_{t_id}")
            os.makedirs(t_dir, exist_ok=True)
            df_all_teams[df_all_teams['team_id'] == t_id].sort_values('gw').to_csv(os.path.join(t_dir, "gw.csv"),
                                                                                   index=False)

        gw_dir = os.path.join(season, "gws")
        os.makedirs(gw_dir, exist_ok=True)
        for gw_num, df_gw in df_all_teams.groupby('gw'):
            df_gw.to_csv(os.path.join(gw_dir, f"gw_{int(gw_num)}_teams.csv"), index=False)

    print("🎉 Teams & Metadata sync complete!\n")


if __name__ == "__main__":
    main()