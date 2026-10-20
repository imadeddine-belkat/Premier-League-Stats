"""Squad ETL: detailed official squad lists per team/season.
Output: pl_stats/{Team}/squad/{Season}_squad.csv
"""
import pandas as pd

from pl import client, config
from pl.parse import unwrap_player


def _squad_row(entry: dict) -> dict:
    p = unwrap_player(entry)
    name = p.get("name") or {}
    country = p.get("country") or {}
    dates = p.get("dates") or {}
    birth = dates.get("birth")
    return {
        "playerId": p.get("id"),
        "displayName": name.get("display"),
        "firstName": name.get("first"),
        "lastName": name.get("last"),
        "shirtNumber": p.get("shirtNum"),
        "position": p.get("position"),
        "preferredFoot": p.get("preferredFoot"),
        "nationality": country.get("country"),
        "isoCode": country.get("isoCode"),
        "birthDate": birth,
        "birthCountry": p.get("countryOfBirth"),
        "age": config.calc_age(birth),
        "height_cm": p.get("height"),
        "weight_kg": p.get("weight"),
        "joinDate": dates.get("joinedClub"),
        "onLoan": bool(p.get("loan")),
    }


def run(season: int) -> None:
    label = config.season_dir_name(season)
    print(f"\n=== Squads for {label} ===")
    teams = client.get_teams(season)
    print(f"[{label}] {len(teams)} teams")

    for team in teams:
        tid, tname = team.get("id"), team.get("shortName", team.get("name"))
        if not (tid and tname):
            continue

        rows = [_squad_row(e) for e in client.get_squad(season, tid)]
        if not rows:
            print(f"  No squad data for {tname}.")
            continue

        out_dir = config.team_dir(tid, tname) / "squad"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{label}_squad.csv"
        pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8")
        print(f"  Saved: {out_path} ({len(rows)} players)")


if __name__ == "__main__":
    run(2026)