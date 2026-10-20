"""Wrappers over the Pulselive endpoints. Each method owns its cache path so the
entry-point scripts never touch URL formatting or cache layout directly."""
from . import config
from .http import cached_get


def _season_cache(season: int) -> "config.Path":
    return config.CACHE_DIR / config.season_dir_name(season)


def get_teams(season: int) -> list[dict]:
    payload = cached_get(
        config.EP_TEAMS.format(season=season),
        _season_cache(season) / "teams_list.json",
    )
    return payload.get("data", []) if isinstance(payload, dict) else []


def get_squad(season: int, team_id: str) -> list[dict]:
    """Raw player entries for a team's squad (shape varies; callers normalize)."""
    payload = cached_get(
        config.EP_SQUAD.format(season=season, team_id=team_id),
        _season_cache(season) / f"squad_team_{team_id}.json",
    )
    return payload.get("players", []) if isinstance(payload, dict) else []


def get_player_stats(season: int, player_id: str) -> dict:
    payload = cached_get(
        config.EP_PLAYER_STATS.format(season=season, player_id=player_id),
        _season_cache(season) / "stats" / f"player_{player_id}.json",
    )
    return payload if isinstance(payload, dict) else {}


def get_team_matches(season: int, team_id: str) -> list[dict]:
    payload = cached_get(
        config.EP_MATCHES.format(season=season, team_id=team_id),
        _season_cache(season) / f"matches_team{team_id}.json",
    )
    return payload.get("data", []) if isinstance(payload, dict) else []


def get_match_stats(season: int, match_id: str) -> list[dict]:
    payload = cached_get(
        config.EP_MATCH_STATS.format(match_id=match_id),
        _season_cache(season) / f"stats_{match_id}.json",
    )
    return payload if isinstance(payload, list) else []