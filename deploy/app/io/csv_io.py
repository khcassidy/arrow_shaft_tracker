"""CSV import/export: the plain-text interchange format for everything or
a single batch. Every value round-trips as text -- no cell is ever parsed
through float() here; core.units does that, later, from the exact string.

This is the flat, human-editable format, not the backup format -- JSON is
that (see app/io/json_io.py). Two consequences are deliberate. Length
exports as the shaft's EFFECTIVE length, so a spreadsheet shows a real
number on every row rather than blanks on the shafts that inherit their
batch default, and an import writes it back as that shaft's own length.
SpineBand exports as a label only, so an import matches an existing band
and never creates one -- a band needs a numeric (min, max) pair that a
bare label cannot supply.
"""

from __future__ import annotations

import csv
import io

EXPORT_FIELDNAMES = [
    "Batch",
    "Seq",
    "Label",
    "Diameter",
    "Wood",
    "Shop",
    "PurchaseDate",
    "SpineRangeLabel",
    "SpineA",
    "SpineB",
    "WeightG",
    "WeightGr",
    "Length",
    "SpineBand",
    "Quality",
    "Notes",
]

# Header aliases the importer accepts, normalised (lowercased, spaces and
# punctuation stripped) -> canonical column name. Covers the export's own
# headers plus a few common spellings a hand-edited spreadsheet might use.
_HEADER_ALIASES = {
    "batch": "Batch",
    "batchno": "Batch",
    "batch#": "Batch",
    "seq": "Seq",
    "shaft": "Seq",
    "shaft#": "Seq",
    "label": "Label",
    "diameter": "Diameter",
    "wood": "Wood",
    "woodsort": "Wood",
    "shop": "Shop",
    "purchasedate": "PurchaseDate",
    "spinerangelabel": "SpineRangeLabel",
    "spinerange": "SpineRangeLabel",
    "spinea": "SpineA",
    "spineb": "SpineB",
    "weightg": "WeightG",
    "weightgrams": "WeightG",
    "weightgr": "WeightGr",
    "weightgrains": "WeightGr",
    "length": "Length",
    "lengthin": "Length",
    "lengthinches": "Length",
    "spineband": "SpineBand",
    "band": "SpineBand",
    "quality": "Quality",
    "notes": "Notes",
    "comments": "Notes",
}


def _normalize_header(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum())


def read_csv_rows(text: str) -> list[dict]:
    """Parses CSV text (BOM tolerated) into a list of dicts keyed by the
    canonical column names above. A column this importer doesn't recognise
    is dropped; a row is returned even if some canonical columns are
    missing (they come back as None)."""
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    header_map = {}
    for raw_name in reader.fieldnames:
        canonical = _HEADER_ALIASES.get(_normalize_header(raw_name))
        if canonical:
            header_map[raw_name] = canonical

    rows = []
    for raw_row in reader:
        row = {}
        for raw_name, canonical in header_map.items():
            value = raw_row.get(raw_name)
            value = value.strip() if isinstance(value, str) else value
            row[canonical] = value if value else None
        rows.append(row)
    return rows


def from_export_rows(db_rows: list[dict]) -> list[dict]:
    """Converts repo_export.export_shaft_rows() dicts (a single
    weight_text/weight_unit pair) into EXPORT_FIELDNAMES-shaped rows with
    separate WeightG/WeightGr columns, for write_csv()."""
    out = []
    for r in db_rows:
        out.append(
            {
                "Batch": r["batch_no"],
                "Seq": r["seq"],
                "Label": r["label"],
                "Diameter": r["diameter_label"],
                "Wood": r["wood_label"],
                "Shop": r["shop_label"],
                "PurchaseDate": r["purchase_date"],
                "SpineRangeLabel": r["nominal_spine_label"],
                "SpineA": r["spine_a_text"],
                "SpineB": r["spine_b_text"],
                "WeightG": r["weight_text"] if r["weight_unit"] == "g" else None,
                "WeightGr": r["weight_text"] if r["weight_unit"] == "gr" else None,
                "Length": r["length_text"],
                "SpineBand": r["spine_band_label"],
                "Quality": r["quality"],
                "Notes": r["notes"],
            }
        )
    return out


def to_staged_rows(rows: list[dict]) -> list[dict]:
    """Adapts read_csv_rows()'s PascalCase columns to the canonical
    staged-row shape app/db/repo_import.py works in. Grams wins if a row
    somehow carries both WeightG and WeightGr."""
    staged = []
    for row in rows:
        if row.get("WeightG"):
            weight_text, weight_unit = row["WeightG"], "g"
        elif row.get("WeightGr"):
            weight_text, weight_unit = row["WeightGr"], "gr"
        else:
            weight_text, weight_unit = None, None
        staged.append(
            {
                "batchNo": row.get("Batch"),
                "seq": row.get("Seq"),
                "diameter": row.get("Diameter"),
                "wood": row.get("Wood"),
                "shop": row.get("Shop"),
                "spineBand": row.get("SpineBand"),
                "purchaseDate": row.get("PurchaseDate"),
                "nominalSpineLabel": row.get("SpineRangeLabel"),
                "batchLength": None,
                "description": None,
                "entryMode": None,
                "spineA": row.get("SpineA"),
                "spineB": row.get("SpineB"),
                "weightText": weight_text,
                "weightUnit": weight_unit,
                "length": row.get("Length"),
                "quality": row.get("Quality"),
                "notes": row.get("Notes"),
            }
        )
    return staged


ARROW_EXPORT_FIELDNAMES = [
    "Label",
    "Nock",
    "Fletching",
    "FletchCount",
    "Point",
    "Finish",
    "CutLength",
    "BareWeightG",
    "AfterFinishWeightG",
    "DeltaG",
    "AfterFletchingWeightG",
    "FletchingDeltaG",
    "FinishedWeightG",
    "TotalDeltaG",
    "Notes",
]


def from_arrow_export_rows(db_rows: list[dict]) -> list[dict]:
    """Converts repo_export.export_arrow_rows() dicts into
    ARROW_EXPORT_FIELDNAMES-shaped rows for write_csv(). One-way: unlike
    the shaft export above, there is no matching arrow import -- a set's
    membership and per-arrow build state come from the JSON backup format
    instead (app/io/json_io.py), which carries the batchNo/seq a CSV row
    alone can't reconstruct a shaft from."""
    out = []
    for r in db_rows:
        out.append(
            {
                "Label": r["shaft_label"],
                "Nock": r["nock_label"],
                "Fletching": r["fletching_label"],
                "FletchCount": r["fletch_count"],
                "Point": r["point_label"],
                "Finish": r["finish_label"],
                "CutLength": r["cut_length_text"],
                "BareWeightG": r["bare_weight_text"],
                "AfterFinishWeightG": r["after_finish_weight_text"],
                "DeltaG": r["delta_text"],
                "AfterFletchingWeightG": r["after_fletching_weight_text"],
                "FletchingDeltaG": r["fletching_delta_text"],
                "FinishedWeightG": r["finished_weight_text"],
                "TotalDeltaG": r["total_delta_text"],
                "Notes": r["notes"],
            }
        )
    return out


def write_csv(rows: list[dict], fieldnames: list[str] = EXPORT_FIELDNAMES) -> str:
    """Writes rows (dicts keyed by `fieldnames`) to CSV text: a UTF-8 BOM
    (so Excel opens it as UTF-8 rather than guessing) and CRLF line
    endings. csv.writer already uses \\r\\n by default -- do not also
    replace \\n, or every line ending doubles to \\r\\r\\n."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    return "﻿" + buf.getvalue()
