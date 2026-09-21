"""One router, dispatching on {kind} in {'diameter', 'wood', 'shop',
'nock', 'fletching', 'point', 'finish'}."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import LookupCreateRequest, LookupOrderRequest, LookupPatchRequest
from app.db import repo_lookups
from app.deps import get_db
from core.units import parse_arrow_weight

router = APIRouter(prefix="/api/lookups/{kind}", tags=["lookups"])

_KINDS = {"diameter", "wood", "shop", "nock", "fletching", "point", "finish"}


def _check_kind(kind: str) -> None:
    if kind not in _KINDS:
        raise HTTPException(404, f"unknown lookup kind {kind!r}")


def _row_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    out = {
        "id": data["id"],
        "label": data["label"],
        "sortOrder": data["sort_order"],
        "isActive": bool(data.get("is_active", 1)),
    }
    if "is_unknown" in data:
        out["isUnknown"] = bool(data["is_unknown"])
    if "sixty_fourths" in data:
        out["sixtyFourths"] = data["sixty_fourths"]
    if "url" in data:
        out["url"] = data["url"]
    if "notes" in data:
        out["notes"] = data["notes"]
    if "default_unit_weight_cgr" in data:
        # Same field names the create/patch body uses, so a generic caller
        # (config.js's buildLookupSection) can read a row and write it back
        # unchanged with no per-kind name translation.
        out["unitWeightCgr"] = data["default_unit_weight_cgr"]
        out["weightText"] = data["default_weight_text"]
        out["weightUnit"] = data["default_weight_unit"]
    if "brand" in data:
        out["brand"] = data["brand"]
    return out


@router.get("")
def list_lookup(kind: str, db: sqlite3.Connection = Depends(get_db)):
    _check_kind(kind)
    return [_row_dict(r) for r in repo_lookups.list_options(db, kind)]


@router.post("", status_code=201)
def create_lookup(
    kind: str, body: LookupCreateRequest, db: sqlite3.Connection = Depends(get_db)
):
    _check_kind(kind)
    if kind == "diameter":
        option_id = repo_lookups.create_diameter_option(db, body.label, body.sixtyFourths)
    elif kind == "wood":
        option_id = repo_lookups.create_wood_option(db, body.label)
    elif kind == "shop":
        option_id = repo_lookups.create_shop(db, body.label, body.url, body.notes)
    elif kind in repo_lookups.WEIGHTED_KINDS:
        option_id = repo_lookups.create_weighted_option(
            db, kind, body.label, body.weightText, body.weightUnit, body.notes
        )
    else:
        option_id = repo_lookups.create_finish_product(db, body.label, body.brand, body.url, body.notes)
    return _row_dict(repo_lookups.get_option(db, kind, option_id))


_LOOKUP_FIELD_MAP = {
    "label": "label",
    "sixtyFourths": "sixty_fourths",
    "url": "url",
    "notes": "notes",
    "brand": "brand",
}


@router.patch("/{option_id}")
def patch_lookup(
    kind: str, option_id: int, body: LookupPatchRequest, db: sqlite3.Connection = Depends(get_db)
):
    _check_kind(kind)
    fields = body.model_dump(exclude_unset=True)
    is_active = fields.pop("isActive", None)
    weight_text_given = "weightText" in fields
    weight_text = fields.pop("weightText", None)
    weight_unit_given = "weightUnit" in fields
    weight_unit = fields.pop("weightUnit", None)

    db_fields = {_LOOKUP_FIELD_MAP[k]: v for k, v in fields.items()}
    if (weight_text_given or weight_unit_given) and kind in repo_lookups.WEIGHTED_KINDS:
        current = repo_lookups.get_option(db, kind, option_id)
        if current is None:
            raise HTTPException(404, f"no such {kind} option {option_id}")
        text = weight_text if weight_text_given else current["default_weight_text"]
        unit = weight_unit if weight_unit_given else current["default_weight_unit"]
        if not text:
            text, unit = None, None
        db_fields["default_weight_text"] = text
        db_fields["default_weight_unit"] = unit
        # UnitError -> 422 via the registered handler; deliberately not
        # caught here, same as app/api/batches.py's parse_length_in call.
        db_fields["default_unit_weight_cgr"] = parse_arrow_weight(text, unit) if text else None

    try:
        repo_lookups.update_option(db, kind, option_id, db_fields)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if is_active is not None:
        repo_lookups.set_active(db, kind, option_id, is_active)
    row = repo_lookups.get_option(db, kind, option_id)
    if row is None:
        raise HTTPException(404, f"no such {kind} option {option_id}")
    return _row_dict(row)


@router.put("/order")
def reorder_lookup(
    kind: str, body: LookupOrderRequest, db: sqlite3.Connection = Depends(get_db)
):
    _check_kind(kind)
    repo_lookups.reorder_options(db, kind, body.ids)
    return [_row_dict(r) for r in repo_lookups.list_options(db, kind)]


@router.delete("/{option_id}")
def delete_lookup(kind: str, option_id: int, db: sqlite3.Connection = Depends(get_db)):
    _check_kind(kind)
    try:
        repo_lookups.delete_option(db, kind, option_id)
    except KeyError:
        raise HTTPException(404, f"no such {kind} option {option_id}")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "deleted"}
