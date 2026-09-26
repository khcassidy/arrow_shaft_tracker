"""Builds CSV export row dicts: export_shaft_rows joins shaft_entry_v with
the lookup labels a human-readable file needs instead of raw ids;
export_arrow_rows does the same for one set's arrow build, reusing
repo_arrows.list_arrows rather than re-joining its five tables again here.

length_text is the shaft's EFFECTIVE length (its own override, else the
batch default), formatted back to inches. That is what the flat CSV wants
on every row -- see app/io/csv_io.py for why the backup format does the
opposite and keeps the override separate."""

from __future__ import annotations

import sqlite3

from app.db import repo_arrows
from core.units import format_length_in, format_weight_cg


def export_shaft_rows(conn: sqlite3.Connection, batch_id: int | None = None) -> list[dict]:
    where = "WHERE sev.batch_id = ?" if batch_id is not None else ""
    params = (batch_id,) if batch_id is not None else ()
    rows = conn.execute(
        f"""SELECT sev.batch_no, sev.seq, sev.label,
                   d.label AS diameter_label, w.label AS wood_label, sh.label AS shop_label,
                   b.purchase_date, b.nominal_spine_label,
                   sb.label AS spine_band_label,
                   sev.spine_a_text, sev.spine_b_text,
                   sev.weight_text, sev.weight_unit,
                   sev.effective_length_c_in,
                   sev.quality, sev.notes
            FROM shaft_entry_v sev
            JOIN batch b ON b.id = sev.batch_id
            JOIN diameter_option d ON d.id = sev.diameter_id
            JOIN wood_option w ON w.id = sev.wood_id
            LEFT JOIN shop sh ON sh.id = b.shop_id
            LEFT JOIN spine_band sb ON sb.id = b.spine_band_id
            {where}
            ORDER BY sev.batch_no, sev.seq""",
        params,
    ).fetchall()
    out = []
    for row in rows:
        record = dict(row)
        c_in = record.pop("effective_length_c_in")
        record["length_text"] = format_length_in(c_in) if c_in is not None else None
        out.append(record)
    return out


def _weight_text(cg: int | None) -> str | None:
    return format_weight_cg(cg) if cg is not None else None


def _weight_delta_text(base_cg: int | None, other_cg: int | None) -> str | None:
    if base_cg is None or other_cg is None:
        return None
    return format_weight_cg(other_cg - base_cg)


def export_arrow_rows(conn: sqlite3.Connection, set_id: int) -> list[dict]:
    """One row per arrow, the same fields and three computed deltas the
    Arrow Set page's own grid shows (see arrowset.js's computeDeltaCg and
    friends) -- an export of "what's on screen", not a second, differently
    -shaped view of the arrow table."""
    out = []
    for row in repo_arrows.list_arrows(conn, set_id):
        weight_cg = row["weight_cg"]
        after_finish_cg = row["after_finish_weight_cg"]
        after_fletching_cg = row["after_fletching_weight_cg"]
        finished_cg = row["finished_weight_cg"]
        out.append(
            {
                "batch_no": row["batch_no"],
                "seq": row["seq"],
                "shaft_label": row["shaft_label"],
                "nock_label": row["nock_label"],
                "fletching_label": row["fletching_label"],
                "fletch_count": row["fletch_count"],
                "point_label": row["point_label"],
                "finish_label": row["finish_label"],
                "cut_length_text": (
                    format_length_in(row["cut_length_c_in"])
                    if row["cut_length_c_in"] is not None
                    else None
                ),
                "bare_weight_text": _weight_text(weight_cg),
                "after_finish_weight_text": _weight_text(after_finish_cg),
                "delta_text": _weight_delta_text(weight_cg, after_finish_cg),
                "after_fletching_weight_text": _weight_text(after_fletching_cg),
                "fletching_delta_text": _weight_delta_text(weight_cg, after_fletching_cg),
                "finished_weight_text": _weight_text(finished_cg),
                "total_delta_text": _weight_delta_text(weight_cg, finished_cg),
                "notes": row["notes"],
            }
        )
    return out
