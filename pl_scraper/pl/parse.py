"""Normalizers for the squad endpoint, whose player entries come in two shapes:
either {"player": {...}} or the player dict inline. Both player_stats and squad
scrapers needed this unwrap, so it lives here once."""


def unwrap_player(entry: dict) -> dict:
    if isinstance(entry, dict) and "player" in entry:
        return entry["player"] or {}
    return entry or {}


def player_id_name(entry: dict) -> tuple | None:
    """(id, display_name) from a squad entry, or None if no id."""
    p = unwrap_player(entry)
    name_info = p.get("name") or {}
    pid = p.get("id")
    display = name_info.get("display") if isinstance(name_info, dict) else name_info
    return (pid, display) if pid else None