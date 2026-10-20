"""Build Premier League indexes.

Creates:
  - pl_stats/_teams_index.json
  - pl_stats/_players_index.json
  - pl_stats/_index/{Season}_players.json
"""

import json

from pl import client, config
from pl.parse import player_id_name


def load_json(path) -> dict:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, OSError):
        return {}


def save_json(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    sorted_data = dict(
        sorted(
            data.items(),
            key=lambda item: int(item[0]),
        )
    )

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            sorted_data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def run() -> None:
    index_dir = config.OUTPUT_ROOT / "_index"
    index_dir.mkdir(parents=True, exist_ok=True)

    teams_index_path = index_dir  / "_teams_index.json"
    players_index_path = index_dir / "_players_index.json"

    teams_index = load_json(teams_index_path)
    players_index = load_json(players_index_path)

    print(
        f"Loaded {len(teams_index)} teams "
        f"and {len(players_index)} players."
    )

    for season in config.DEFAULT_SEASONS:
        label = config.season_dir_name(season)

        print(f"\n=== {label} ===")

        teams = client.get_teams(season)

        if not teams:
            print("  No teams found.")
            continue

        season_players = {}

        for team in teams:
            team_id = team.get("id")
            team_name = (
                team.get("name")
                or team.get("shortName")
            )

            if not team_id or not team_name:
                continue

            team_id = str(team_id)

            # Global team index
            if team_id not in teams_index:
                teams_index[team_id] = config.safe_name(team_name)

            print(
                f"  {team_name} ({team_id})"
            )

            squad = client.get_squad(
                season,
                team_id,
            )

            count = 0

            for entry in squad:
                player = player_id_name(entry)

                if not player:
                    continue

                player_id, player_name = player

                if not player_id or not player_name:
                    continue

                player_id = str(player_id)

                # Global player index
                players_index[player_id] = player_name

                # Season player index
                season_players[player_id] = player_name

                count += 1

            print(
                f"    {count} players"
            )

        # -----------------------------------------
        # Save season index
        # -----------------------------------------

        season_index_path = (
            index_dir
            / f"{label}_players.json"
        )

        save_json(
            season_index_path,
            season_players,
        )

        # -----------------------------------------
        # Update global indexes
        # -----------------------------------------

        save_json(
            teams_index_path,
            teams_index,
        )

        save_json(
            players_index_path,
            players_index,
        )

        print(
            f"  Saved {season_index_path} "
            f"({len(season_players)} players)"
        )

    print("\n=== Complete ===")
    print(
        f"Teams indexed: {len(teams_index)}"
    )
    print(
        f"Players indexed: {len(players_index)}"
    )


if __name__ == "__main__":
    run()