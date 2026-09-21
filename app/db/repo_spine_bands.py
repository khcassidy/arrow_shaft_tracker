"""CRUD for the configurable spine-band list (30-35, 35-40, ... lb).

Deliberately not a 4th kind under repo_lookups.py: that module's tables
are all a plain label plus optional extras, but a band's real data is a
numeric (min, max) pair, and the label here is derived from it, never
typed directly. list_bands/reorder_bands/set_active mirror their
repo_lookups.py counterparts exactly (same sort_order-rewrite-on-reorder
behaviour), duplicated rather than shoehorned in.
"""

from __future__ import annotations

import sqlite3

from core.units import parse_spine_band_lb


def list_bands(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM spine_band ORDER BY sort_order, id").fetchall()


def get_band(conn: sqlite3.Connection, band_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM spine_band WHERE id = ?", (band_id,)).fetchone()


def reorder_bands(conn: sqlite3.Connection, ordered_ids: list[int]) -> None:
    for position, band_id in enumerate(ordered_ids, start=1):
        conn.execute("UPDATE spine_band SET sort_order = ? WHERE id = ?", (position, band_id))
    conn.commit()


def set_active(conn: sqlite3.Connection, band_id: int, is_active: bool) -> None:
    conn.execute(
        "UPDATE spine_band SET is_active = ? WHERE id = ?", (1 if is_active else 0, band_id)
    )
    conn.commit()


def delete_band(conn: sqlite3.Connection, band_id: int) -> None:
    """A band still assigned to a batch fails the schema's own FOREIGN
    KEY constraint (batch.spine_band_id) and surfaces as a 409."""
    if get_band(conn, band_id) is None:
        raise KeyError(band_id)
    conn.execute("DELETE FROM spine_band WHERE id = ?", (band_id,))
    conn.commit()


def _label_for(min_mlb: int, max_mlb: int) -> str:
    def fmt(mlb: int) -> str:
        lb = mlb / 1000
        return f"{lb:g}"

    return f"{fmt(min_mlb)}-{fmt(max_mlb)}"


def create_band(conn: sqlite3.Connection, min_lb: str, max_lb: str) -> int:
    min_mlb = parse_spine_band_lb(min_lb)
    max_mlb = parse_spine_band_lb(max_lb)
    if min_mlb >= max_mlb:
        raise ValueError(f"min ({min_lb}) must be less than max ({max_lb})")
    row = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM spine_band").fetchone()
    cur = conn.execute(
        "INSERT INTO spine_band(label, min_mlb, max_mlb, sort_order) VALUES (?, ?, ?, ?)",
        (_label_for(min_mlb, max_mlb), min_mlb, max_mlb, row["n"]),
    )
    conn.commit()
    return cur.lastrowid


def update_band(
    conn: sqlite3.Connection, band_id: int, *, min_lb: str | None = None, max_lb: str | None = None
) -> None:
    if min_lb is None and max_lb is None:
        return
    current = get_band(conn, band_id)
    if current is None:
        raise ValueError(f"no such spine band {band_id}")
    min_mlb = parse_spine_band_lb(min_lb) if min_lb is not None else current["min_mlb"]
    max_mlb = parse_spine_band_lb(max_lb) if max_lb is not None else current["max_mlb"]
    if min_mlb >= max_mlb:
        raise ValueError(f"min ({min_mlb / 1000:g}) must be less than max ({max_mlb / 1000:g})")
    conn.execute(
        "UPDATE spine_band SET label = ?, min_mlb = ?, max_mlb = ? WHERE id = ?",
        (_label_for(min_mlb, max_mlb), min_mlb, max_mlb, band_id),
    )
    conn.commit()
