"""CSV/JSON import: stage into import_run for preview, then commit.

Both formats feed the same pipeline through one canonical row shape --
csv_io.to_staged_rows() and json_io.to_staged_rows() each adapt their own
format into it, so everything below reads exactly one set of keys:
  batchNo, seq, diameter, wood, shop, purchaseDate, nominalSpineLabel,
  spineBand, batchLength, description, entryMode, spineA, spineB,
  weightText, weightUnit, length, quality, notes

Staging always validates shape, positivity and the hard plausibility band
up front (via core.units and core.validate), so a committed import should
never fail on a value it already accepted at preview time. Commit reuses
create_batch and patch_shaft_entry rather than re-implementing batch/shaft
writes -- one place owns "how a batch and its shafts get written".

A lookup label the database does not have yet is NOT an error. It is
staged for creation, listed in the report's lookupsToCreate section, and
created at commit. This is what makes a JSON backup restorable into a
fresh database: 0001_initial.sql seeds diameter_option and wood_option but
seeds no shops at all, so before this, every restore of a backup that
named a shop failed on every row that carried one. The two-phase preview
is exactly where a person checks that a new label is a real new shop and
not a typo, so blocking the whole file on it bought nothing.

Labels, not resolved ids, are what the staged payload carries. Resolution
happens at commit, against the lookup tables as they stand then -- so a
preview staged before a shop existed still commits correctly once it does,
whether this import creates it or a person does.

Scope, deliberately: import only ever CREATES batches whose batch_no does
not already exist. A batch_no already present is reported and skipped,
never merged or overwritten -- that avoids the much harder problem of
reconciling seq/seq_width against an existing batch, and the grid already
handles editing an existing batch's shafts.
"""

from __future__ import annotations

import json
import secrets
import sqlite3

from app.db import repo_batches, repo_lookups, repo_shafts, repo_spine_bands
from core.units import UnitError, parse_length_in, parse_spine_lb, parse_weight
from core.validate import check_spine_reading, check_weight_reading

_QUALITY_VALUES = {"USABLE", "BAD", "JUNK"}
_LOOKUP_KINDS = ("diameter", "wood", "shop")

# Batch-level fields every row of that batch carries a copy of. The first
# row that names one wins, matching how the rest of the batch meta is read.
_BATCH_META_KEYS = (
    "nominalSpineLabel",
    "purchaseDate",
    "description",
    "entryMode",
    "spineBand",
    "batchLength",
)


def _key(label: str | None) -> str:
    """Lookup labels match case-insensitively, and ignore surrounding space."""
    return (label or "").strip().lower()


def _lookup_maps(conn: sqlite3.Connection) -> dict:
    def by_label(table):
        return {
            _key(r["label"]): r["id"]
            for r in conn.execute(f"SELECT id, label FROM {table}").fetchall()
        }

    return {
        "diameter": by_label("diameter_option"),
        "wood": by_label("wood_option"),
        "shop": by_label("shop"),
    }


def _band_map(conn: sqlite3.Connection) -> dict:
    return {
        _key(r["label"]): r["id"]
        for r in conn.execute("SELECT id, label FROM spine_band").fetchall()
    }


def stage_rows(
    conn: sqlite3.Connection,
    rows: list[dict],
    source_name: str,
    fmt: str,
    lookup_defs: dict | None = None,
    band_defs: dict | None = None,
) -> dict:
    """rows must already be in the canonical staged-row shape (see the module
    docstring) -- callers use csv_io.to_staged_rows() or
    json_io.to_staged_rows() to get there from a raw upload.

    lookup_defs and band_defs give the extra attributes for a label this
    database does not have yet, keyed by lowercased label (see
    json_io.lookup_definitions and json_io.band_definitions). A JSON backup
    carries them, so a shop it creates keeps its url and notes, and a
    diameter keeps its sixty_fourths. A CSV carries bare labels only, so it
    passes neither, and anything created from one starts with just a label.
    """
    lookups = _lookup_maps(conn)
    bands = _band_map(conn)
    defs = lookup_defs or {}
    band_defs = band_defs or {}
    existing_batch_nos = {
        r["batch_no"] for r in conn.execute("SELECT batch_no FROM batch").fetchall()
    }
    rules = conn.execute("SELECT * FROM entry_rule WHERE id = 1").fetchone()

    errors: list[str] = []
    all_batch_nos: set[int] = set()
    groups: dict[int, dict] = {}  # batch_no -> {"meta": {...}, "shafts": {seq: {...}}}
    to_create: dict[str, dict] = {kind: {} for kind in _LOOKUP_KINDS}
    bands_to_create: dict[str, dict] = {}

    for i, row in enumerate(rows):
        line = i + 2  # header is line 1
        if row.get("batchNo") is None or row.get("seq") is None:
            errors.append(f"row {line}: missing batch number or seq")
            continue
        try:
            batch_no = int(row["batchNo"])
            seq = int(row["seq"])
        except (TypeError, ValueError):
            errors.append(f"row {line}: batch and seq must be whole numbers")
            continue
        all_batch_nos.add(batch_no)
        if batch_no in existing_batch_nos:
            continue  # reported in the summary, not per row

        group = groups.setdefault(batch_no, {"meta": {}, "shafts": {}})
        meta = group["meta"]
        for meta_key in _BATCH_META_KEYS:
            value = row.get(meta_key)
            if value and meta_key not in meta:
                meta[meta_key] = value

        for kind in _LOOKUP_KINDS:
            label = (row.get(kind) or "").strip()
            if not label:
                continue
            meta.setdefault(kind, label)
            key = _key(label)
            if key not in lookups[kind] and key not in to_create[kind]:
                to_create[kind][key] = {"label": label, **defs.get(kind, {}).get(key, {})}

        band_label = (row.get("spineBand") or "").strip()
        if band_label:
            key = _key(band_label)
            if key not in bands and key not in bands_to_create and key in band_defs:
                bands_to_create[key] = {"label": band_label, **band_defs[key]}

        spine_a_cp = spine_b_cp = None
        try:
            if row.get("spineA"):
                spine_a_cp = parse_spine_lb(row["spineA"])
                issue = next(iter(check_spine_reading(
                    spine_a_cp, step_cp=rules["spine_step_cp"],
                    hard_min_cp=rules["spine_hard_min_cp"], hard_max_cp=rules["spine_hard_max_cp"],
                    warn_min_cp=rules["spine_warn_min_cp"], warn_max_cp=rules["spine_warn_max_cp"],
                )), None)
                if issue and issue.blocking:
                    errors.append(f"row {line}: spine A {issue.message}")
            if row.get("spineB"):
                spine_b_cp = parse_spine_lb(row["spineB"])
        except UnitError as exc:
            errors.append(f"row {line}: spine reading -- {exc}")

        weight_cg = None
        weight_text, weight_unit = row.get("weightText"), row.get("weightUnit")
        if weight_text:
            try:
                weight_cg = parse_weight(weight_text, weight_unit)
                issue = next(iter(check_weight_reading(
                    weight_cg, step_cg=rules["weight_step_cg"],
                    hard_min_cg=rules["weight_hard_min_cg"], hard_max_cg=rules["weight_hard_max_cg"],
                    warn_min_cg=rules["weight_warn_min_cg"], warn_max_cg=rules["weight_warn_max_cg"],
                )), None)
                if issue and issue.blocking:
                    errors.append(f"row {line}: weight {issue.message}")
            except UnitError as exc:
                errors.append(f"row {line}: weight -- {exc}")

        length_text = row.get("length")
        if length_text:
            try:
                parse_length_in(length_text)
            except UnitError as exc:
                errors.append(f"row {line}: length -- {exc}")
                length_text = None

        quality = row.get("quality")
        if quality:
            quality = quality.strip().upper()
            if quality not in _QUALITY_VALUES:
                errors.append(f"row {line}: unknown quality '{quality}'")
                quality = None

        if seq in group["shafts"]:
            errors.append(f"row {line}: duplicate seq {seq} in batch {batch_no}")
            continue

        group["shafts"][seq] = {
            "spineA": row.get("spineA") if spine_a_cp else None,
            "spineB": row.get("spineB") if spine_b_cp else None,
            "weightText": weight_text if weight_cg else None,
            "weightUnit": weight_unit if weight_cg else None,
            "length": length_text,
            "quality": quality,
            "notes": row.get("notes"),
        }

    # A batch length that will not parse is reported once for the batch, not
    # once per row: it is one batch-level value that every row repeats.
    for batch_no, group in groups.items():
        raw = group["meta"].get("batchLength")
        if not raw:
            continue
        try:
            parse_length_in(raw)
        except UnitError as exc:
            errors.append(f"batch {batch_no}: length -- {exc}")
            group["meta"].pop("batchLength")

    row_count = sum(len(g["shafts"]) for g in groups.values())
    report = {
        "rowCount": row_count,
        "batchesNew": sorted(groups.keys()),
        "batchesSkippedExisting": sorted(all_batch_nos & existing_batch_nos),
        "lookupsToCreate": {
            kind: sorted(entry["label"] for entry in to_create[kind].values())
            for kind in _LOOKUP_KINDS
        },
        "spineBandsToCreate": sorted(entry["label"] for entry in bands_to_create.values()),
        "errors": errors,
    }

    payload = {
        "groups": groups,
        "lookupsToCreate": to_create,
        "spineBandsToCreate": bands_to_create,
    }
    token = secrets.token_urlsafe(16)
    conn.execute(
        "INSERT INTO import_run"
        "(token, source_name, format, mode, row_count, status, payload_json, report_json) "
        "VALUES (?, ?, ?, 'create_only', ?, 'previewed', ?, ?)",
        (token, source_name, fmt, row_count, json.dumps(payload), json.dumps(report)),
    )
    conn.commit()
    return {"token": token, "report": report}


def _create_missing_lookups(conn: sqlite3.Connection, to_create: dict) -> tuple[dict, dict]:
    """Creates every staged label the database still lacks. Returns the
    refreshed label -> id maps, and what this call actually created. Each
    label is re-checked against the live table first, so one that a person
    added between preview and commit is reused, not failed on its UNIQUE."""
    lookups = _lookup_maps(conn)
    created: dict[str, list[str]] = {kind: [] for kind in _LOOKUP_KINDS}
    for kind in _LOOKUP_KINDS:
        for entry in (to_create.get(kind) or {}).values():
            label = (entry.get("label") or "").strip()
            key = _key(label)
            if not label or key in lookups[kind]:
                continue
            if kind == "diameter":
                option_id = repo_lookups.create_diameter_option(
                    conn, label, entry.get("sixtyFourths")
                )
            elif kind == "wood":
                option_id = repo_lookups.create_wood_option(conn, label)
            else:
                option_id = repo_lookups.create_shop(
                    conn, label, entry.get("url"), entry.get("notes")
                )
            lookups[kind][key] = option_id
            created[kind].append(label)
    return lookups, created


def _create_missing_bands(conn: sqlite3.Connection, bands_to_create: dict) -> tuple[dict, list]:
    """Same idea as _create_missing_lookups, for spine bands. A band needs a
    numeric (min, max) pair, never just a label, so only a band the source
    file defined bounds for is created -- see json_io.band_definitions."""
    bands = _band_map(conn)
    created: list[str] = []
    for entry in (bands_to_create or {}).values():
        label = (entry.get("label") or "").strip()
        key = _key(label)
        min_lb, max_lb = entry.get("minLb"), entry.get("maxLb")
        if not label or key in bands or min_lb is None or max_lb is None:
            continue
        bands[key] = repo_spine_bands.create_band(conn, str(min_lb), str(max_lb))
        created.append(label)
    return bands, created


def commit_import(conn: sqlite3.Connection, token: str) -> dict:
    run = conn.execute("SELECT * FROM import_run WHERE token = ?", (token,)).fetchone()
    if run is None:
        raise ValueError(f"no staged import {token}")
    if run["status"] != "previewed":
        raise ValueError(f"import {token} is already {run['status']}")
    if run["report_json"] and json.loads(run["report_json"]).get("errors"):
        raise ValueError("this import has errors and cannot be committed")

    payload = json.loads(run["payload_json"])
    # A payload staged before the payload grew its own wrapper is the bare
    # groups dict. Nothing in such a payload needs creating, so the empty
    # to-create maps below are the correct reading of it.
    groups = payload.get("groups", payload)

    lookups, lookups_created = _create_missing_lookups(conn, payload.get("lookupsToCreate", {}))
    bands, bands_created = _create_missing_bands(conn, payload.get("spineBandsToCreate", {}))

    batches_created = 0
    shafts_written = 0

    for batch_no_str, group in groups.items():
        batch_no = int(batch_no_str)
        meta = group["meta"]
        expected_count = max((int(s) for s in group["shafts"]), default=0)
        nominal_min, nominal_max = repo_batches.parse_nominal_range(meta.get("nominalSpineLabel"))
        batch_length = meta.get("batchLength")

        batch_id = repo_batches.create_batch(
            conn,
            batch_no=batch_no,
            expected_count=expected_count,
            nominal_spine_label=meta.get("nominalSpineLabel"),
            nominal_min_lb=nominal_min,
            nominal_max_lb=nominal_max,
            diameter_id=lookups["diameter"].get(_key(meta.get("diameter")), 0),
            wood_id=lookups["wood"].get(_key(meta.get("wood")), 0),
            shop_id=lookups["shop"].get(_key(meta.get("shop"))),
            purchase_date=meta.get("purchaseDate"),
            description=meta.get("description"),
            entry_mode=meta.get("entryMode") or "per_shaft",
            length_c_in=parse_length_in(batch_length) if batch_length else None,
            spine_band_id=bands.get(_key(meta.get("spineBand"))),
        )
        batches_created += 1

        for seq_str, shaft_data in group["shafts"].items():
            seq = int(seq_str)
            fields = {
                k: v
                for k, v in {
                    "spineA": shaft_data.get("spineA"),
                    "spineB": shaft_data.get("spineB"),
                    "weight": shaft_data.get("weightText"),
                    "weightUnit": shaft_data.get("weightUnit"),
                    "length": shaft_data.get("length"),
                    "quality": shaft_data.get("quality"),
                    "notes": shaft_data.get("notes"),
                }.items()
                if v is not None
            }
            if fields:
                repo_shafts.patch_shaft_entry(conn, batch_id, seq, fields)
            shafts_written += 1

    conn.execute(
        "UPDATE import_run SET status = 'committed', created_count = ?, "
        "committed_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE token = ?",
        (batches_created, token),
    )
    conn.commit()
    return {
        "batchesCreated": batches_created,
        "shaftsWritten": shafts_written,
        "lookupsCreated": lookups_created,
        "spineBandsCreated": bands_created,
    }
