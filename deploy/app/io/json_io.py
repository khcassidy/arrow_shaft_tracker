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

Beyond batches, the file also carries the rest of the Configuration tab
(the four arrow-build catalogues, analysis parameter sets, the entry-
validation rule) and every still-active matched Set with its arrow builds.
A disbanded set is deliberately left out: disbanding clears
consumed_set_id on every member (repo_sets.disband_set), so its own
membership is not recoverable from live state -- there is nothing a
restore could reconstruct beyond a name and a timestamp. The entry rule
round-trips for reference only; repo_import.py never writes it back, since
it is a single fixed row (id=1) every database already has one of, not a
label-keyed list a restore could create-if-missing the way it does for
lookups and parameter sets.
"""

from __future__ import annotations

import sqlite3

from core.units import format_length_in, format_weight_cg


def _label_for(options: list[sqlite3.Row], option_id: int | None) -> str | None:
    if option_id is None:
        return None
    for option in options:
        if option["id"] == option_id:
            return option["label"]
    return None


def _length_text(c_in: int | None) -> str | None:
    return format_length_in(c_in) if c_in is not None else None


def _weighted_catalogue_export(rows: list[sqlite3.Row]) -> list[dict]:
    """nock_option/fletching_option/point_option are column-for-column
    identical, so one function exports all three (see
    repo_lookups.create_weighted_option for the same reuse on import)."""
    return [
        {
            "label": r["label"],
            "weightText": r["default_weight_text"],
            "weightUnit": r["default_weight_unit"],
            "notes": r["notes"],
        }
        for r in rows
        if not r["is_unknown"]
    ]


def _entry_rule_export(row: sqlite3.Row) -> dict:
    """Same field set as app/api/params.py's own _entry_rule_dict --
    duplicated rather than imported, since app/io stays below app/api in
    this project's layering (core/db/io have no FastAPI dependency)."""
    return {
        "spineMaxDp": row["spine_max_dp"],
        "weightMaxDp": row["weight_max_dp"],
        "spineStepCp": row["spine_step_cp"],
        "weightStepCg": row["weight_step_cg"],
        "spineHardMinCp": row["spine_hard_min_cp"],
        "spineHardMaxCp": row["spine_hard_max_cp"],
        "spineWarnMinCp": row["spine_warn_min_cp"],
        "spineWarnMaxCp": row["spine_warn_max_cp"],
        "weightHardMinCg": row["weight_hard_min_cg"],
        "weightHardMaxCg": row["weight_hard_max_cg"],
        "weightWarnMinCg": row["weight_warn_min_cg"],
        "weightWarnMaxCg": row["weight_warn_max_cg"],
        "batchOutlierSpineCp": row["batch_outlier_spine_cp"],
        "batchOutlierWeightCg": row["batch_outlier_weight_cg"],
        "grainsPerGram": row["grains_per_gram"],
    }


def _weight_text(cg: int | None) -> str | None:
    return format_weight_cg(cg) if cg is not None else None


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
    nocks_all = conn.execute("SELECT * FROM nock_option ORDER BY sort_order").fetchall()
    fletchings_all = conn.execute("SELECT * FROM fletching_option ORDER BY sort_order").fetchall()
    points_all = conn.execute("SELECT * FROM point_option ORDER BY sort_order").fetchall()
    finishes_all = conn.execute("SELECT * FROM finish_product ORDER BY sort_order").fetchall()

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

    sets = []
    for set_row in conn.execute(
        "SELECT * FROM arrow_set WHERE disbanded_at IS NULL ORDER BY id"
    ).fetchall():
        arrows_by_shaft = {
            a["shaft_id"]: a
            for a in conn.execute(
                "SELECT * FROM arrow WHERE set_id = ?", (set_row["id"],)
            ).fetchall()
        }
        members = []
        for m in conn.execute(
            "SELECT * FROM shaft_entry_v WHERE consumed_set_id = ? ORDER BY batch_no, seq",
            (set_row["id"],),
        ).fetchall():
            arrow_row = arrows_by_shaft.get(m["id"])
            arrow = None
            if arrow_row is not None:
                arrow = {
                    "nock": _label_for(nocks_all, arrow_row["nock_option_id"]),
                    "fletching": _label_for(fletchings_all, arrow_row["fletching_option_id"]),
                    "fletchCount": arrow_row["fletch_count"],
                    "point": _label_for(points_all, arrow_row["point_option_id"]),
                    "finish": _label_for(finishes_all, arrow_row["finish_product_id"]),
                    "cutLength": _length_text(arrow_row["cut_length_c_in"]),
                    "afterFinishWeight": _weight_text(arrow_row["after_finish_weight_cg"]),
                    "afterFletchingWeight": _weight_text(arrow_row["after_fletching_weight_cg"]),
                    "finishedWeight": _weight_text(arrow_row["finished_weight_cg"]),
                    "notes": arrow_row["notes"],
                }
            members.append({"batchNo": m["batch_no"], "seq": m["seq"], "arrow": arrow})

        sets.append(
            {
                "name": set_row["name"],
                "diameter": _label_for(diameters_all, set_row["diameter_id"]),
                "wood": _label_for(woods_all, set_row["wood_id"]),
                "targetSize": set_row["target_size"],
                "notes": set_row["notes"],
                "defaults": {
                    "nock": _label_for(nocks_all, set_row["default_nock_option_id"]),
                    "fletching": _label_for(fletchings_all, set_row["default_fletching_option_id"]),
                    "fletchCount": set_row["default_fletch_count"],
                    "point": _label_for(points_all, set_row["default_point_option_id"]),
                    "finish": _label_for(finishes_all, set_row["default_finish_product_id"]),
                    "cutLength": _length_text(set_row["default_cut_length_c_in"]),
                },
                "members": members,
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
        "nocks": _weighted_catalogue_export(nocks_all),
        "fletchings": _weighted_catalogue_export(fletchings_all),
        "points": _weighted_catalogue_export(points_all),
        "finishes": [
            {"label": f["label"], "brand": f["brand"], "url": f["url"], "notes": f["notes"]}
            for f in finishes_all
            if not f["is_unknown"]
        ],
        "spineBands": [
            {
                "label": b["label"],
                "minLb": f"{b['min_mlb'] / 1000:g}",
                "maxLb": f"{b['max_mlb'] / 1000:g}",
            }
            for b in bands_all
        ],
        "paramSets": [
            {
                "name": p["name"],
                "isDefault": bool(p["is_default"]),
                "spineTolMlb": p["spine_tol_mlb"],
                "weightTolCg": p["weight_tol_cg"],
                "objective": p["objective"],
                "dozenSize": p["dozen_size"],
                "specMinMlb": p["spec_min_mlb"],
                "specMaxMlb": p["spec_max_mlb"],
                "abTolCp": p["ab_tol_cp"],
                "minGroupSize": p["min_group_size"],
                "lengthTolCIn": p["length_tol_c_in"],
            }
            for p in conn.execute(
                "SELECT * FROM param_set ORDER BY is_default DESC, name"
            ).fetchall()
        ],
        "entryRule": _entry_rule_export(conn.execute("SELECT * FROM entry_rule WHERE id = 1").fetchone()),
        "batches": batches,
        "sets": sets,
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


def catalogue_definitions(data: dict) -> dict:
    """Same idea as lookup_definitions above, for the four arrow-build
    catalogues, keyed by lowercased label -- a nock/fletching/point named
    by a Set's defaults or an arrow's own build but missing from the
    target database is created WITH its weight/notes (or brand/url/notes
    for a finish), not as a bare label."""

    def index(items, extra_keys):
        out = {}
        for item in items or []:
            label = (item.get("label") or "").strip()
            if label:
                out[label.lower()] = {key: item.get(key) for key in extra_keys}
        return out

    weighted_keys = ("weightText", "weightUnit", "notes")
    return {
        "nock": index(data.get("nocks"), weighted_keys),
        "fletching": index(data.get("fletchings"), weighted_keys),
        "point": index(data.get("points"), weighted_keys),
        "finish": index(data.get("finishes"), ("brand", "url", "notes")),
    }


def param_set_definitions(data: dict) -> list[dict]:
    """The file's own analysis parameter sets, passed through as-is --
    unlike a lookup label, a parameter set is never referenced by a batch
    or shaft row, so every one the file names is offered for creation,
    not just the ones something else in the file happens to use."""
    return data.get("paramSets") or []


def to_staged_sets(data: dict) -> list[dict]:
    """The file's own matched Sets (each with its arrow build state),
    passed through as-is -- the export shape above already IS the shape
    repo_import.py stages, so unlike to_staged_rows there is no reshaping
    to do; a CSV import simply never calls this, since a Set can span
    batches and a CSV row cannot express that."""
    return data.get("sets") or []


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
