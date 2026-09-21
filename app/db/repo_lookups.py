"""CRUD for the ordered lookup lists: diameter, wood, shop, and the four
arrow-build catalogues (nock, fletching, point, finish).

sort_order is deliberately not unique. Reordering rewrites 1..n in one
transaction so a pull-down never falls back to alphabetical order -- that
is the explicit requirement the column exists for.
"""

from __future__ import annotations

import sqlite3

from core.units import parse_arrow_weight

_TABLES = {
    "diameter": "diameter_option",
    "wood": "wood_option",
    "shop": "shop",
    "nock": "nock_option",
    "fletching": "fletching_option",
    "point": "point_option",
    "finish": "finish_product",
}

# The three catalogues sharing one identical column shape (label, a
# default unit weight in centigrains with its own text/unit audit pair,
# notes) -- see create_weighted_option below. Public: app/api/lookups.py
# reads this to know which kinds need their weight recomputed on PATCH.
WEIGHTED_KINDS = {"nock", "fletching", "point"}


class UnknownLookupKind(ValueError):
    pass


def _table(kind: str) -> str:
    try:
        return _TABLES[kind]
    except KeyError:
        raise UnknownLookupKind(kind) from None


def list_options(conn: sqlite3.Connection, kind: str) -> list[sqlite3.Row]:
    table = _table(kind)
    return conn.execute(f"SELECT * FROM {table} ORDER BY sort_order, id").fetchall()


def get_option(conn: sqlite3.Connection, kind: str, option_id: int) -> sqlite3.Row | None:
    table = _table(kind)
    return conn.execute(f"SELECT * FROM {table} WHERE id = ?", (option_id,)).fetchone()


def reorder_options(conn: sqlite3.Connection, kind: str, ordered_ids: list[int]) -> None:
    table = _table(kind)
    for position, option_id in enumerate(ordered_ids, start=1):
        conn.execute(f"UPDATE {table} SET sort_order = ? WHERE id = ?", (position, option_id))
    conn.commit()


def _next_sort_order(conn: sqlite3.Connection, table: str) -> int:
    # Exclude the Unknown sentinel (sort_order = 999) everywhere it exists,
    # so a newly created option lands after the real entries, not after
    # Unknown -- shop is the one table with no such sentinel to exclude.
    where = "" if table == "shop" else "WHERE is_unknown = 0"
    row = conn.execute(
        f"SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM {table} {where}"
    ).fetchone()
    return row["n"]


def create_diameter_option(conn: sqlite3.Connection, label: str, sixty_fourths: int | None) -> int:
    sort_order = _next_sort_order(conn, "diameter_option")
    cur = conn.execute(
        "INSERT INTO diameter_option(label, sixty_fourths, sort_order) VALUES (?, ?, ?)",
        (label, sixty_fourths, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def create_wood_option(conn: sqlite3.Connection, label: str) -> int:
    sort_order = _next_sort_order(conn, "wood_option")
    cur = conn.execute(
        "INSERT INTO wood_option(label, sort_order) VALUES (?, ?)", (label, sort_order)
    )
    conn.commit()
    return cur.lastrowid


def create_shop(conn: sqlite3.Connection, label: str, url: str | None, notes: str | None) -> int:
    sort_order = _next_sort_order(conn, "shop")
    cur = conn.execute(
        "INSERT INTO shop(label, sort_order, url, notes) VALUES (?, ?, ?, ?)",
        (label, sort_order, url, notes),
    )
    conn.commit()
    return cur.lastrowid


def create_weighted_option(
    conn: sqlite3.Connection,
    kind: str,
    label: str,
    weight_text: str | None,
    weight_unit: str | None,
    notes: str | None,
) -> int:
    """One function for nock, fletching and point: the three catalogues
    are column-for-column identical. weight_text/weight_unit are the
    audit pair the archer actually typed; default_unit_weight_cgr is
    derived from them here, through core.units.parse_arrow_weight, never
    computed a second way at any other call site. Both empty means "not
    catalogued yet" -- a real, valid state, not an error."""
    table = _TABLES[kind]
    unit_weight_cgr = parse_arrow_weight(weight_text, weight_unit) if weight_text else None
    sort_order = _next_sort_order(conn, table)
    cur = conn.execute(
        f"INSERT INTO {table}"
        "(label, default_unit_weight_cgr, default_weight_text, default_weight_unit, notes, sort_order)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (label, unit_weight_cgr, weight_text, weight_unit, notes, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def create_finish_product(
    conn: sqlite3.Connection, label: str, brand: str | None, url: str | None, notes: str | None
) -> int:
    sort_order = _next_sort_order(conn, "finish_product")
    cur = conn.execute(
        "INSERT INTO finish_product(label, brand, url, notes, sort_order) VALUES (?, ?, ?, ?, ?)",
        (label, brand, url, notes, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def set_active(conn: sqlite3.Connection, kind: str, option_id: int, is_active: bool) -> None:
    table = _table(kind)
    conn.execute(
        f"UPDATE {table} SET is_active = ? WHERE id = ?", (1 if is_active else 0, option_id)
    )
    conn.commit()


# Per-kind whitelist beyond "label", which every kind allows. Guards the
# f-string UPDATE below the same way the other repo modules' whitelists do.
_EXTRA_COLUMNS = {
    "diameter": {"sixty_fourths"},
    "wood": set(),
    "shop": {"url", "notes"},
    "nock": {"default_weight_text", "default_weight_unit", "default_unit_weight_cgr", "notes"},
    "fletching": {"default_weight_text", "default_weight_unit", "default_unit_weight_cgr", "notes"},
    "point": {"default_weight_text", "default_weight_unit", "default_unit_weight_cgr", "notes"},
    "finish": {"brand", "url", "notes"},
}


def update_option(conn: sqlite3.Connection, kind: str, option_id: int, fields: dict) -> None:
    """fields uses DB column names (label, sixty_fourths, url, notes)."""
    if not fields:
        return
    table = _table(kind)
    allowed = {"label"} | _EXTRA_COLUMNS[kind]
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"not editable on {kind}: {unknown}")
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [option_id]
    conn.execute(f"UPDATE {table} SET {columns} WHERE id = ?", values)
    conn.commit()


def delete_option(conn: sqlite3.Connection, kind: str, option_id: int) -> None:
    """Refuses the Unknown sentinel (id=0, is_unknown=1) outright -- every
    kind but shop enforces exactly one via a partial UNIQUE index, so it
    isn't a real catalogue entry a person could have meant to remove. A
    row still referenced by a shaft or batch fails the schema's own
    FOREIGN KEY constraint (PRAGMA foreign_keys=ON, see app/db/connection.py)
    and surfaces as a 409 -- no special-casing for "in use" needed here."""
    row = get_option(conn, kind, option_id)
    if row is None:
        raise KeyError(option_id)
    if "is_unknown" in row.keys() and row["is_unknown"]:
        raise ValueError(f"the Unknown {kind} option cannot be deleted")
    table = _table(kind)
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (option_id,))
    conn.commit()
