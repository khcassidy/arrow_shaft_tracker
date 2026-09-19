"""JSON: the full-fidelity backup format. Unlike CSV's derived grams/grains
pair, a shaft's weight here is its exact (weightText, weightUnit) --
whichever the archer actually typed -- so a round trip through export and
back never loses or re-derives anything.

"Full fidelity" also means the file carries the lists a batch points at,
not only the labels it uses: diameters, woods, shops and spine bands each
come out with their own attributes, and repo_import.py creates any the
target database lacks. That matters most for shops, which 0001_initial.sql
seeds none of -- a backup restored into a fresh database has to bring its
own shops with it or every batch loses the shop it was bought from.

Length round-trips as the shaft's OWN override, never its effective value.
shaft.length_c_in stays NULL on a shaft that just inherits its batch
default, and writing the inherited value back would turn every one of them
into an explicit override that no longer follows the batch.
"""

from __future__ import annotations

import sqlite3

from core.units import format_length_in


def _label_for(options: list[sqlite3.Row], option_id: int | None) -> str | None:
    if option_id is None:
        return None
    for option in options:
        if option["id"] == option_id:
            return option["label"]
    return None


def _length_text(c_in: int | None) -> str | None:
    return format_length_in(c_in) if c_in is not None else None


def export_json(conn: sqlite3.Connection) -> dict:
    diameters_all = conn.execute(
        "SELECT id, label, sixty_fourths, is_unknown FROM diameter_option ORDER BY sort_order"
    ).fetchall()
    woods_all = conn.execute(
        "SELECT id, label, is_unknown FROM wood_option ORDER BY sort_order"
    ).fetchall()
    shops_all = conn.execute("SELECT id, label, url, notes FROM shop ORDER BY sort_order").fetchall()
    bands_all = conn.execute(
        "SELECT id, label, min_mlb, max_mlb FROM spine_band ORDER BY sort_order"
    ).fetchall()

    batches = []
    for batch in conn.execute("SELECT * FROM batch ORDER BY batch_no").fetchall():
        shafts = []
        for shaft in conn.execute(
            "SELECT * FROM shaft_entry_v WHERE batch_id = ? ORDER BY seq", (batch["id"],)
        ).fetchall():
            shafts.append(
                {
                    "seq": shaft["seq"],
                    "spineA": shaft["spine_a_text"],
                    "spineB": shaft["spine_b_text"],
                    "weightText": shaft["weight_text"],
                    "weightUnit": shaft["weight_unit"],
                    "length": _length_text(shaft["length_c_in"]),
                    "quality": shaft["quality"],
                    "notes": shaft["notes"],
                }
            )
        batches.append(
            {
                "batchNo": batch["batch_no"],
                "nominalSpineLabel": batch["nominal_spine_label"],
                "diameter": _label_for(diameters_all, batch["diameter_id"]),
                "wood": _label_for(woods_all, batch["wood_id"]),
                "shop": _label_for(shops_all, batch["shop_id"]),
                "spineBand": _label_for(bands_all, batch["spine_band_id"]),
                "purchaseDate": batch["purchase_date"],
                "length": _length_text(batch["length_c_in"]),
                "description": batch["description"],
                "entryMode": batch["entry_mode"],
                "shafts": shafts,
            }
        )

    return {
        "diameters": [
            {"label": d["label"], "sixtyFourths": d["sixty_fourths"]}
            for d in diameters_all
            if not d["is_unknown"]
        ],
        "woods": [{"label": w["label"]} for w in woods_all if not w["is_unknown"]],
        "shops": [{"label": s["label"], "url": s["url"], "notes": s["notes"]} for s in shops_all],
        "spineBands": [
            {
                "label": b["label"],
                "minLb": f"{b['min_mlb'] / 1000:g}",
                "maxLb": f"{b['max_mlb'] / 1000:g}",
            }
            for b in bands_all
        ],
        "batches": batches,
    }


def lookup_definitions(data: dict) -> dict:
    """The file's own diameter/wood/shop lists, keyed by lowercased label,
    for repo_import.stage_rows(). A label the target database lacks is
    created from this, so it keeps its attributes instead of arriving bare.
    A list the file does not have simply yields no definitions: the label
    still gets created, just with nothing but its label."""

    def index(items, extra_keys):
        out = {}
        for item in items or []:
            label = (item.get("label") or "").strip()
            if label:
                out[label.lower()] = {key: item.get(key) for key in extra_keys}
        return out

    return {
        "diameter": index(data.get("diameters"), ("sixtyFourths",)),
        "wood": index(data.get("woods"), ()),
        "shop": index(data.get("shops"), ("url", "notes")),
    }


def band_definitions(data: dict) -> dict:
    """The file's own spine-band list, keyed by lowercased label. A band is
    a numeric (min, max) pair, so unlike the lookup lists above, a band the
    file names but does not define cannot be created at all."""
    out = {}
    for item in data.get("spineBands") or []:
        label = (item.get("label") or "").strip()
        if label and item.get("minLb") is not None and item.get("maxLb") is not None:
            out[label.lower()] = {"minLb": item["minLb"], "maxLb": item["maxLb"]}
    return out


def to_staged_rows(data: dict) -> list[dict]:
    """Flattens the export shape above into the canonical staged-row list
    app/db/repo_import.py works in -- one dict per shaft, batch-level
    fields copied onto every row, exactly like a CSV row would carry them.
    A batch's own default length rides along as batchLength, separate from
    the shaft's own length, so the override relationship survives."""
    rows = []
    for batch in data.get("batches", []):
        for shaft in batch.get("shafts", []):
            rows.append(
                {
                    "batchNo": batch.get("batchNo"),
                    "seq": shaft.get("seq"),
                    "diameter": batch.get("diameter"),
                    "wood": batch.get("wood"),
                    "shop": batch.get("shop"),
                    "spineBand": batch.get("spineBand"),
                    "purchaseDate": batch.get("purchaseDate"),
                    "nominalSpineLabel": batch.get("nominalSpineLabel"),
                    "batchLength": batch.get("length"),
                    "description": batch.get("description"),
                    "entryMode": batch.get("entryMode"),
                    "spineA": shaft.get("spineA"),
                    "spineB": shaft.get("spineB"),
                    "weightText": shaft.get("weightText"),
                    "weightUnit": shaft.get("weightUnit"),
                    "length": shaft.get("length"),
                    "quality": shaft.get("quality"),
                    "notes": shaft.get("notes"),
                }
            )
    return rows
