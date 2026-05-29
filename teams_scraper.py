import requests
import pandas as pd
import os
import json
import re
from datetime import datetime

ROOT = "fpl_stats"


def get_current_season():
    now = datetime.now()
    if now.month >= 8:
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
    os.makedirs(meta_dir, exist_ok=True)

    print("Fetching bootstrap-static data...")
    bootstrap_data = requests.get(base_url + "bootstrap-static/", headers=headers).json()

    with open(os.path.join(meta_dir, "raw_bootstrap_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(bootstrap_data, f, indent=4)

    print("Generating mapping lists with IDs and Codes...")
    team_info = {t['id']: {'name': t['name'], 'code': t['code']} for t in bootstrap_data['teams']}

    pd.DataFrame(bootstrap_data['teams'])[['id', 'code', 'name', 'short_name']].to_csv(
        os.path.join(meta_dir, "teams_id_list.csv"), index=False)

    player_rows = [{
        'id': p['id'], 'code': p['code'],
        'first_name': p['first_name'], 'second_name': p['second_name'],
        'team_id': p['team'], 'team_code': p['team_code'],
        'team_name': team_info.get(p['team'], {}).get('name', 'Unknown')
    } for p in bootstrap_data['elements']]
    pd.DataFrame(player_rows).to_csv(os.path.join(meta_dir, "players_id_list.csv"), index=False)

    print("Fetching and parsing fixtures...")
    fixtures_data = requests.get(base_url + "fixtures/", headers=headers).json()
    with open(os.path.join(meta_dir, "fixtures.json"), "w", encoding="utf-8") as f:
        json.dump(fixtures_data, f, indent=4)

    # Build per-team GW rows
    team_gw_data = []
    for f in fixtures_data:
        gw = f.get('event')
        if not gw:
            continue
        th, ta = team_info.get(f['team_h'], {}), team_info.get(f['team_a'], {})
        team_gw_data.append({
            'team_code': th.get('code'), 'team_name': th.get('name'), 'gw': gw, 'is_home': True,
            'opponent_code': ta.get('code'), 'opponent_name': ta.get('name'),
            'team_score': f.get('team_h_score'), 'opponent_score': f.get('team_a_score'),
            'difficulty': f.get('team_h_difficulty'), 'finished': f.get('finished'),
        })
        team_gw_data.append({
            'team_code': ta.get('code'), 'team_name': ta.get('name'), 'gw': gw, 'is_home': False,
            'opponent_code': th.get('code'), 'opponent_name': th.get('name'),
            'team_score': f.get('team_a_score'), 'opponent_score': f.get('team_h_score'),
            'difficulty': f.get('team_a_difficulty'), 'finished': f.get('finished'),
        })

    if not team_gw_data:
        print("No team GW data.\n")
        return

    df_all = pd.DataFrame(team_gw_data)

    # Per-team: fpl_stats/teams/{Team}/gameweeks/{season}_gw_stats.csv
    for info in team_info.values():
        team_name = clean_filename(info['name'])
        gw_dir = os.path.join(ROOT, "teams", team_name, "gameweeks")
        fx_dir = os.path.join(ROOT, "teams", team_name, "fixtures")
        os.makedirs(gw_dir, exist_ok=True)
        os.makedirs(fx_dir, exist_ok=True)

        team_df = df_all[df_all['team_code'] == info['code']].sort_values('gw')
        team_df.to_csv(os.path.join(gw_dir, f"{season}_gw_stats.csv"), index=False)
        # fixtures = same rows minus result columns, but kept separate for the pl_stats parallel
        team_df[['gw', 'is_home', 'opponent_name', 'opponent_code', 'difficulty', 'finished']].to_csv(
            os.path.join(fx_dir, f"{season}_fixtures.csv"), index=False)

    # Cross-team aggregate index: fpl_stats/_index/teams/{season}_all_teams_gw.csv
    idx_dir = os.path.join(ROOT, "_index", "teams")
    os.makedirs(idx_dir, exist_ok=True)
    df_all.sort_values(['gw', 'team_name']).to_csv(
        os.path.join(idx_dir, f"{season}_all_teams_gw.csv"), index=False)

    print("Teams & Metadata sync complete!\n")


if __name__ == "__main__":
    main()