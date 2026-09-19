"""Batch creation and listing.

Creating a batch pre-creates its blank shaft rows in the same transaction,
so entry becomes pure UPDATE: seq and label are allocated up front, no row
ever appears or shifts under the cursor, and "partly measured" is the
natural resting state rather than a special case.
"""

from __future__ import annotations

import re
import sqlite3

from core.derive import spine_band_status
from core.labels import required_seq_width, shaft_label

_NOMINAL_RANGE_RE = re.compile(r"^(\d+)-(\d+)#?$")


def parse_nominal_range(label: str | None) -> tuple[int | None, int | None]:
    """'55-60#' -> (55, 60). Display-only: never feeds the analysis."""
    if not label:
        return None, None
    match = _NOMINAL_RANGE_RE.match(label.strip())
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def create_batch(
    conn: sqlite3.Connection,
    *,
    batch_no: int,
    expected_count: int,
    nominal_spine_label: str | None = None,
    nominal_min_lb: int | None = None,
    nominal_max_lb: int | None = None,
    diameter_id: int = 0,
    wood_id: int = 0,
    shop_id: int | None = None,
    purchase_date: str | None = None,
    description: str | None = None,
    entry_mode: str = "per_shaft",
    length_c_in: int | None = None,
    spine_band_id: int | None = None,
) -> int:
    seq_width = required_seq_width(expected_count)
    cur = conn.execute(
        """INSERT INTO batch
           (batch_no, seq_width, nominal_spine_label, nominal_min_lb, nominal_max_lb,
            diameter_id, wood_id, shop_id, purchase_date, expected_count,
            description, entry_mode, entry_pass, length_c_in, spine_band_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            batch_no,
            seq_width,
            nominal_spine_label,
            nominal_min_lb,
            nominal_max_lb,
            diameter_id,
            wood_id,
            shop_id,
            purchase_date,
            expected_count,
            description,
            entry_mode,
            "spine" if entry_mode == "per_field" else None,
            length_c_in,
            spine_band_id,
        ),
    )
    batch_id = cur.lastrowid
    for seq in range(1, expected_count + 1):
        label = shaft_label(batch_no, seq, seq_width)
        conn.execute(
            "INSERT INTO shaft(batch_id, seq, label, diameter_id, wood_id) VALUES (?, ?, ?, ?, ?)",
            (batch_id, seq, label, diameter_id, wood_id),
        )
    conn.commit()
    return batch_id


def get_batch(conn: sqlite3.Connection, batch_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM batch WHERE id = ?", (batch_id,)).fetchone()


def delete_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    """Deletes a batch and every one of its shafts. Refused if any shaft
    is already consumed into a set -- same rule as delete_shaft, for the
    same reason: that record needs to stay put for the set's history.
    Spine readings cascade with their shaft (ON DELETE CASCADE); the
    shaft rows must be deleted before the batch row, since
    shaft.batch_id REFERENCES batch(id) ON DELETE RESTRICT.
    """
    batch = get_batch(conn, batch_id)
    if batch is None:
        raise ValueError(f"no such batch {batch_id}")
    consumed = conn.execute(
        "SELECT COUNT(*) AS n FROM shaft WHERE batch_id = ? AND consumed_set_id IS NOT NULL",
        (batch_id,),
    ).fetchone()["n"]
    if consumed:
        raise ValueError(
            f"cannot delete batch {batch['batch_no']}: {consumed} of its shafts "
            f"are already used in a set"
        )
    conn.execute("DELETE FROM shaft WHERE batch_id = ?", (batch_id,))
    conn.execute("DELETE FROM batch WHERE id = ?", (batch_id,))
    conn.commit()


def list_batches(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM batch ORDER BY batch_no").fetchall()


# Whitelist: db_fields passed to update_batch become column names in an
# f-string UPDATE, so only names this module itself produces are trusted.
_ALLOWED_BATCH_COLUMNS = {
    "nominal_spine_label",
    "nominal_min_lb",
    "nominal_max_lb",
    "diameter_id",
    "wood_id",
    "shop_id",
    "purchase_date",
    "description",
    "length_c_in",
    "spine_band_id",
}


def update_batch(conn: sqlite3.Connection, batch_id: int, fields: dict) -> None:
    """Edits batch metadata after creation: spine label, diameter, wood,
    shop, purchase date, comments, default length. batch_no goes through
    rename_batch_no instead, since it needs to relabel every shaft in the
    batch. seq_width is never editable: it is derived once from the count
    at creation and every label's padding depends on it staying fixed.

    A diameter_id or wood_id change cascades to every shaft in the batch
    still carrying the *old* value: the default assumption is that one
    batch is one diameter and one wood throughout, so correcting the
    batch corrects its shafts too (see core/grouping.py's partition
    query, which reads diameter_id/wood_id from the shaft row, not the
    batch row). A shaft already consumed into a set is excluded, since
    that set's own diameterId/woodId was fixed at build time and must
    not silently drift out of step with its member; a shaft whose
    diameter_id/wood_id no longer matches the batch's old value is also
    excluded, since it has already been deliberately set apart from the
    rest of the batch. length_c_in cascades too, but via a different
    mechanism already in place: a shaft's own length_c_in stays NULL
    until someone types an override, and shaft_entry_v's
    effective_length_c_in reads it live, so no explicit cascade is
    needed here for that column.
    """
    if not fields:
        return
    unknown = set(fields) - _ALLOWED_BATCH_COLUMNS
    if unknown:
        raise ValueError(f"not a batch column: {unknown}")

    old_batch = None
    if "diameter_id" in fields or "wood_id" in fields:
        old_batch = get_batch(conn, batch_id)
        if old_batch is None:
            raise ValueError(f"no such batch {batch_id}")

    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [batch_id]
    conn.execute(
        f"UPDATE batch SET {columns}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
        f"WHERE id = ?",
        values,
    )

    if old_batch is not None:
        for column in ("diameter_id", "wood_id"):
            if column in fields:
                conn.execute(
                    f"UPDATE shaft SET {column} = ? WHERE batch_id = ? AND {column} = ? "
                    f"AND consumed_set_id IS NULL",
                    (fields[column], batch_id, old_batch[column]),
                )

    conn.commit()


def rename_batch_no(conn: sqlite3.Connection, batch_id: int, new_batch_no: int) -> None:
    """Changes a batch's number and relabels every one of its shafts to
    match (seq and seq_width stay fixed, only the batch_no prefix changes).
    The batch_no UPDATE hits the table's UNIQUE constraint first if the
    number is already taken, so relabelling never runs against a batch_no
    that didn't actually become ours -- and once it succeeds, no other
    batch can hold that prefix, so the relabel can't collide either.
    """
    batch = get_batch(conn, batch_id)
    if batch is None:
        raise ValueError(f"no such batch {batch_id}")
    conn.execute(
        "UPDATE batch SET batch_no = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
        "WHERE id = ?",
        (new_batch_no, batch_id),
    )
    shafts = conn.execute(
        "SELECT id, seq FROM shaft WHERE batch_id = ?", (batch_id,)
    ).fetchall()
    for shaft in shafts:
        new_label = shaft_label(new_batch_no, shaft["seq"], batch["seq_width"])
        conn.execute("UPDATE shaft SET label = ? WHERE id = ?", (new_label, shaft["id"]))
    conn.commit()


def set_entry_mode(conn: sqlite3.Connection, batch_id: int, entry_mode: str) -> None:
    """Backs the F2 mode-toggle key in the entry grid. entry_pass resets to
    the first per_field pass on entry, or clears entirely for per_shaft."""
    entry_pass = "spine" if entry_mode == "per_field" else None
    conn.execute(
        "UPDATE batch SET entry_mode = ?, entry_pass = ?, "
        "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
        (entry_mode, entry_pass, batch_id),
    )
    conn.commit()


def batch_summary(conn: sqlite3.Connection, batch_id: int) -> dict:
    row = conn.execute(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN weight_cg IS NOT NULL AND avg_spine_mlb IS NOT NULL
                      AND quality <> 'JUNK'
                 THEN 1 ELSE 0 END) AS available,
             SUM(CASE WHEN quality = 'JUNK' THEN 1 ELSE 0 END) AS junk,
             SUM(CASE WHEN consumed_set_id IS NOT NULL THEN 1 ELSE 0 END) AS consumed,
             MIN(avg_spine_mlb) AS min_avg_spine_mlb,
             MAX(avg_spine_mlb) AS max_avg_spine_mlb,
             MIN(weight_cg) AS min_weight_cg,
             MAX(weight_cg) AS max_weight_cg
           FROM shaft WHERE batch_id = ?""",
        (batch_id,),
    ).fetchone()
    result = {
        "total": row["total"],
        "available": row["available"],
        "junk": row["junk"],
        "consumed": row["consumed"],
        "minAvgSpineMlb": row["min_avg_spine_mlb"],
        "maxAvgSpineMlb": row["max_avg_spine_mlb"],
        "minWeightCg": row["min_weight_cg"],
        "maxWeightCg": row["max_weight_cg"],
        "spineBand": None,
        "spineCheck": None,
    }

    batch = get_batch(conn, batch_id)
    if batch["spine_band_id"] is not None:
        band = conn.execute(
            "SELECT * FROM spine_band WHERE id = ?", (batch["spine_band_id"],)
        ).fetchone()
        result["spineBand"] = {
            "id": band["id"],
            "label": band["label"],
            "minMlb": band["min_mlb"],
            "maxMlb": band["max_mlb"],
        }
        measured = conn.execute(
            "SELECT label, avg_spine_mlb FROM shaft "
            "WHERE batch_id = ? AND avg_spine_mlb IS NOT NULL ORDER BY seq",
            (batch_id,),
        ).fetchall()
        below, above, in_spec = [], [], 0
        for shaft in measured:
            status = spine_band_status(shaft["avg_spine_mlb"], band["min_mlb"], band["max_mlb"])
            if status == "BELOW":
                below.append(shaft)
            elif status == "ABOVE":
                above.append(shaft)
            else:
                in_spec += 1
        result["spineCheck"] = {
            "inSpecCount": in_spec,
            "belowCount": len(below),
            "aboveCount": len(above),
            "unmeasuredCount": result["total"] - len(measured),
            "below": [{"label": s["label"], "avgSpineMlb": s["avg_spine_mlb"]} for s in below],
            "above": [{"label": s["label"], "avgSpineMlb": s["avg_spine_mlb"]} for s in above],
        }
    return result


def extend_batch(conn: sqlite3.Connection, batch_id: int, additional_count: int) -> int:
    """Handle a miscounted purchase: append more blank rows. seq_width is
    fixed at creation, so a physically marked shaft's label never changes
    silently when the batch grows -- extending past the fixed width fails
    instead."""
    batch = get_batch(conn, batch_id)
    if batch is None:
        raise ValueError(f"no such batch {batch_id}")
    current_max_seq = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS n FROM shaft WHERE batch_id = ?", (batch_id,)
    ).fetchone()["n"]
    new_total = current_max_seq + additional_count
    new_seq_width = required_seq_width(new_total)
    if new_seq_width != batch["seq_width"]:
        raise ValueError(
            f"extending batch {batch_id} to {new_total} shafts needs seq_width "
            f"{new_seq_width}, but it was fixed at {batch['seq_width']} at creation"
        )
    for seq in range(current_max_seq + 1, new_total + 1):
        label = shaft_label(batch["batch_no"], seq, batch["seq_width"])
        conn.execute(
            "INSERT INTO shaft(batch_id, seq, label, diameter_id, wood_id) VALUES (?, ?, ?, ?, ?)",
            (batch_id, seq, label, batch["diameter_id"], batch["wood_id"]),
        )
    conn.execute("UPDATE batch SET expected_count = ? WHERE id = ?", (new_total, batch_id))
    conn.commit()
    return new_total


def insert_shaft(conn: sqlite3.Connection, batch_id: int, after_seq: int) -> int:
    """Inserts one new blank shaft immediately after after_seq (0 inserts
    at the very front; after_seq == the current last seq is equivalent to
    appending). Every shaft at or past that position shifts up by one --
    processed highest-seq-first, so no (batch_id, seq) or label collides
    with a row that hasn't moved yet. Same seq_width guard as extend_batch:
    a shaft's label never changes silently because the batch grew past the
    width fixed at creation.
    """
    batch = get_batch(conn, batch_id)
    if batch is None:
        raise ValueError(f"no such batch {batch_id}")
    current_max_seq = conn.execute(
        "SELECT COALESCE(MAX(seq), 0) AS n FROM shaft WHERE batch_id = ?", (batch_id,)
    ).fetchone()["n"]
    if after_seq < 0 or after_seq > current_max_seq:
        raise ValueError(f"after_seq {after_seq} is out of range for batch {batch_id}")

    new_total = current_max_seq + 1
    new_seq_width = required_seq_width(new_total)
    if new_seq_width != batch["seq_width"]:
        raise ValueError(
            f"inserting into batch {batch_id} needs seq_width {new_seq_width}, "
            f"but it was fixed at {batch['seq_width']} at creation"
        )

    shifting = conn.execute(
        "SELECT id, seq FROM shaft WHERE batch_id = ? AND seq > ? ORDER BY seq DESC",
        (batch_id, after_seq),
    ).fetchall()
    for row in shifting:
        new_seq = row["seq"] + 1
        new_label = shaft_label(batch["batch_no"], new_seq, batch["seq_width"])
        conn.execute(
            "UPDATE shaft SET seq = ?, label = ? WHERE id = ?", (new_seq, new_label, row["id"])
        )

    inserted_seq = after_seq + 1
    inserted_label = shaft_label(batch["batch_no"], inserted_seq, batch["seq_width"])
    conn.execute(
        "INSERT INTO shaft(batch_id, seq, label, diameter_id, wood_id) VALUES (?, ?, ?, ?, ?)",
        (batch_id, inserted_seq, inserted_label, batch["diameter_id"], batch["wood_id"]),
    )
    conn.execute("UPDATE batch SET expected_count = ? WHERE id = ?", (new_total, batch_id))
    conn.commit()
    return inserted_seq


def delete_shaft(conn: sqlite3.Connection, batch_id: int, seq: int) -> None:
    """Deletes one shaft and closes the numbering gap: every later shaft
    shifts down by one -- processed lowest-seq-first, so the slot each row
    moves into is always already empty. Readings cascade-delete with their
    shaft (ON DELETE CASCADE); a shaft already consumed into a set is
    refused, since that record needs to stay put for the set's history.
    """
    batch = get_batch(conn, batch_id)
    if batch is None:
        raise ValueError(f"no such batch {batch_id}")
    shaft = conn.execute(
        "SELECT id, consumed_set_id FROM shaft WHERE batch_id = ? AND seq = ?",
        (batch_id, seq),
    ).fetchone()
    if shaft is None:
        raise ValueError(f"no such shaft {batch_id}-{seq}")
    if shaft["consumed_set_id"] is not None:
        raise ValueError("cannot delete a shaft that has already been used in a set")

    conn.execute("DELETE FROM shaft WHERE id = ?", (shaft["id"],))

    shifting = conn.execute(
        "SELECT id, seq FROM shaft WHERE batch_id = ? AND seq > ? ORDER BY seq ASC",
        (batch_id, seq),
    ).fetchall()
    for row in shifting:
        new_seq = row["seq"] - 1
        new_label = shaft_label(batch["batch_no"], new_seq, batch["seq_width"])
        conn.execute(
            "UPDATE shaft SET seq = ?, label = ? WHERE id = ?", (new_seq, new_label, row["id"])
        )

    conn.execute(
        "UPDATE batch SET expected_count = ? WHERE id = ?",
        (batch["expected_count"] - 1, batch_id),
    )
    conn.commit()
