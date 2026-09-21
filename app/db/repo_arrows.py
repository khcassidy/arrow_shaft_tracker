"""The arrow build: turning a matched set's shafts into arrows, one flat
row per arrow, with a set-level defaults header that cascades the same
way a batch's diameter/wood cascades to its shafts (repo_batches.
update_batch) -- "arrows work like batches" is a literal reuse of that
rule, not just a description.

No stage-event log, no per-stage recording, no rollup: cut length and
both weights are plain fields, typed once and edited directly, exactly
like every other measurement in this app.
"""

from __future__ import annotations

import sqlite3

from core.units import parse_length_in, parse_weight_g

_DEFAULT_COLUMNS = {
    "nockOptionId": ("default_nock_option_id", "nock_option_id", 0),
    "fletchingOptionId": ("default_fletching_option_id", "fletching_option_id", 0),
    "fletchCount": ("default_fletch_count", "fletch_count", 3),
    "pointOptionId": ("default_point_option_id", "point_option_id", 0),
    "finishProductId": ("default_finish_product_id", "finish_product_id", 0),
}

_ARROW_V_SQL = """
  SELECT ar.*, s.batch_id, b.batch_no, s.seq, s.label AS shaft_label,
         s.avg_spine_mlb, s.weight_cg,
         nk.label AS nock_label, fl.label AS fletching_label,
         pt.label AS point_label, fn.label AS finish_label
  FROM arrow ar
  JOIN shaft s ON s.id = ar.shaft_id
  JOIN batch b ON b.id = s.batch_id
  JOIN nock_option nk ON nk.id = ar.nock_option_id
  JOIN fletching_option fl ON fl.id = ar.fletching_option_id
  JOIN point_option pt ON pt.id = ar.point_option_id
  JOIN finish_product fn ON fn.id = ar.finish_product_id
"""


def list_arrows(conn: sqlite3.Connection, set_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        f"{_ARROW_V_SQL} WHERE ar.set_id = ? ORDER BY b.batch_no, s.seq", (set_id,)
    ).fetchall()


def get_arrow(conn: sqlite3.Connection, arrow_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_ARROW_V_SQL} WHERE ar.id = ?", (arrow_id,)).fetchone()


def start_build(conn: sqlite3.Connection, set_id: int) -> list[sqlite3.Row]:
    """Creates one arrow per member shaft of the set, seeded from the
    set's current defaults (falling back to Unknown/3-fletch/no-length
    for whichever default hasn't been set yet). Idempotent: if the set
    already has arrows, returns them unchanged rather than erroring or
    duplicating -- landing on an in-progress build's page re-enters this
    the same way "Build arrows" first created it."""
    set_row = conn.execute(
        "SELECT id, disbanded_at, default_nock_option_id, default_fletching_option_id, "
        "default_fletch_count, default_point_option_id, default_finish_product_id, "
        "default_cut_length_c_in FROM arrow_set WHERE id = ?",
        (set_id,),
    ).fetchone()
    if set_row is None:
        raise KeyError(set_id)
    if set_row["disbanded_at"] is not None:
        raise ValueError(f"set {set_id} is disbanded and can't be built")

    existing = list_arrows(conn, set_id)
    if existing:
        return existing

    members = conn.execute(
        "SELECT s.id FROM shaft s JOIN batch b ON b.id = s.batch_id "
        "WHERE s.consumed_set_id = ? ORDER BY b.batch_no, s.seq",
        (set_id,),
    ).fetchall()
    if not members:
        raise ValueError(f"set {set_id} has no shafts to build")

    nock_id = set_row["default_nock_option_id"] or 0
    fletching_id = set_row["default_fletching_option_id"] or 0
    fletch_count = set_row["default_fletch_count"] or 3
    point_id = set_row["default_point_option_id"] or 0
    finish_id = set_row["default_finish_product_id"] or 0
    cut_length = set_row["default_cut_length_c_in"]

    for member in members:
        conn.execute(
            "INSERT INTO arrow(set_id, shaft_id, nock_option_id, fletching_option_id, "
            "fletch_count, point_option_id, finish_product_id, cut_length_c_in) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (set_id, member["id"], nock_id, fletching_id, fletch_count, point_id, finish_id, cut_length),
        )
    conn.commit()
    return list_arrows(conn, set_id)


def update_defaults(conn: sqlite3.Connection, set_id: int, fields: dict) -> sqlite3.Row:
    """fields uses the request's own camelCase keys. Each one that maps to
    a _DEFAULT_COLUMNS entry both updates arrow_set's own default and
    cascades to every arrow in the set still carrying the *old* default
    (falling back to that column's built-in fallback when no default had
    ever been set) -- an arrow already edited away from the default is
    left alone, exactly the divergence check update_batch already applies
    to a shaft's diameter_id/wood_id. cutLength is separate: arrow_set has
    no NOT NULL fallback for it, so the old-value comparison is a plain
    NULL-safe equality, no fallback substitution needed."""
    old = conn.execute("SELECT * FROM arrow_set WHERE id = ?", (set_id,)).fetchone()
    if old is None:
        raise KeyError(set_id)

    sets, values = [], []
    for key, (default_col, arrow_col, fallback) in _DEFAULT_COLUMNS.items():
        if key in fields:
            sets.append(f"{default_col} = ?")
            values.append(fields[key])
    if "cutLength" in fields:
        cut_length_c_in = parse_length_in(fields["cutLength"]) if fields["cutLength"] else None
        sets.append("default_cut_length_c_in = ?")
        values.append(cut_length_c_in)

    if not sets:
        return old

    conn.execute(f"UPDATE arrow_set SET {', '.join(sets)} WHERE id = ?", [*values, set_id])

    for key, (default_col, arrow_col, fallback) in _DEFAULT_COLUMNS.items():
        if key not in fields:
            continue
        old_value = old[default_col] if old[default_col] is not None else fallback
        conn.execute(
            f"UPDATE arrow SET {arrow_col} = ? WHERE set_id = ? AND {arrow_col} = ?",
            (fields[key], set_id, old_value),
        )
    if "cutLength" in fields:
        old_cut_length = old["default_cut_length_c_in"]
        if old_cut_length is None:
            conn.execute(
                "UPDATE arrow SET cut_length_c_in = ? WHERE set_id = ? AND cut_length_c_in IS NULL",
                (cut_length_c_in, set_id),
            )
        else:
            conn.execute(
                "UPDATE arrow SET cut_length_c_in = ? WHERE set_id = ? AND cut_length_c_in = ?",
                (cut_length_c_in, set_id, old_cut_length),
            )

    conn.commit()
    return conn.execute("SELECT * FROM arrow_set WHERE id = ?", (set_id,)).fetchone()


_ARROW_EXTRA_COLUMNS = {
    "nockOptionId": "nock_option_id",
    "fletchingOptionId": "fletching_option_id",
    "fletchCount": "fletch_count",
    "pointOptionId": "point_option_id",
    "finishProductId": "finish_product_id",
    "notes": "notes",
}


def update_arrow(conn: sqlite3.Connection, arrow_id: int, fields: dict) -> sqlite3.Row:
    """fields uses the request's own camelCase keys, including the three
    that need their raw text parsed here (cutLength, afterFinishWeight,
    finishedWeight) rather than in the API layer, so a UnitError raised
    mid-way through a multi-field PATCH still leaves earlier fields in
    this same dict applied together in one UPDATE, not partially."""
    if get_arrow(conn, arrow_id) is None:
        raise KeyError(arrow_id)

    columns, values = [], []
    for key, column in _ARROW_EXTRA_COLUMNS.items():
        if key in fields:
            columns.append(f"{column} = ?")
            values.append(fields[key])
    if "cutLength" in fields:
        columns.append("cut_length_c_in = ?")
        values.append(parse_length_in(fields["cutLength"]) if fields["cutLength"] else None)
    if "afterFinishWeight" in fields:
        columns.append("after_finish_weight_cg = ?")
        raw = fields["afterFinishWeight"]
        values.append(parse_weight_g(raw) if raw else None)
    if "finishedWeight" in fields:
        columns.append("finished_weight_cg = ?")
        raw = fields["finishedWeight"]
        values.append(parse_weight_g(raw) if raw else None)

    if columns:
        columns.append("updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')")
        conn.execute(f"UPDATE arrow SET {', '.join(columns)} WHERE id = ?", [*values, arrow_id])
        conn.commit()
    return get_arrow(conn, arrow_id)


def cancel_build(conn: sqlite3.Connection, set_id: int) -> None:
    """Deletes every arrow of a set, undoing a build started by mistake.
    Refused once any arrow carries a real measurement -- a cut length or
    either weight -- so a build that's actually under way can't be wiped
    by an accidental click; disbanding the set itself remains the way to
    walk back further than that."""
    rows = conn.execute(
        "SELECT id, cut_length_c_in, after_finish_weight_cg, finished_weight_cg "
        "FROM arrow WHERE set_id = ?",
        (set_id,),
    ).fetchall()
    if not rows:
        return
    started = [
        r for r in rows
        if r["cut_length_c_in"] is not None
        or r["after_finish_weight_cg"] is not None
        or r["finished_weight_cg"] is not None
    ]
    if started:
        raise ValueError(f"set {set_id} already has {len(started)} arrow(s) with a recorded measurement")
    conn.execute("DELETE FROM arrow WHERE set_id = ?", (set_id,))
    conn.commit()
