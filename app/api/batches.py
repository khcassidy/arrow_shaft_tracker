"""Batch endpoints: create, list, get, summary, and extend (for a
miscounted purchase)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from core.units import parse_length_in

from app.api.schemas import BatchCreateRequest, BatchExtendRequest, BatchPatchRequest
from app.db import repo_batches
from app.deps import get_db

router = APIRouter(prefix="/api/batches", tags=["batches"])

_BATCH_FIELD_MAP = {
    "diameterId": "diameter_id",
    "woodId": "wood_id",
    "shopId": "shop_id",
    "purchaseDate": "purchase_date",
    "description": "description",
    "spineBandId": "spine_band_id",
}


def _batch_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "batchNo": row["batch_no"],
        "seqWidth": row["seq_width"],
        "nominalSpineLabel": row["nominal_spine_label"],
        "nominalMinLb": row["nominal_min_lb"],
        "nominalMaxLb": row["nominal_max_lb"],
        "diameterId": row["diameter_id"],
        "woodId": row["wood_id"],
        "shopId": row["shop_id"],
        "purchaseDate": row["purchase_date"],
        "expectedCount": row["expected_count"],
        "description": row["description"],
        "entryMode": row["entry_mode"],
        "entryPass": row["entry_pass"],
        "lengthCIn": row["length_c_in"],
        "spineBandId": row["spine_band_id"],
    }


@router.get("")
def list_batches(db: sqlite3.Connection = Depends(get_db)):
    return [_batch_dict(r) for r in repo_batches.list_batches(db)]


@router.post("", status_code=201)
def create_batch(body: BatchCreateRequest, db: sqlite3.Connection = Depends(get_db)):
    nominal_min, nominal_max = repo_batches.parse_nominal_range(body.nominalSpineLabel)
    length_c_in = parse_length_in(body.length) if body.length is not None else None
    batch_id = repo_batches.create_batch(
        db,
        batch_no=body.batchNo,
        expected_count=body.expectedCount,
        nominal_spine_label=body.nominalSpineLabel,
        nominal_min_lb=nominal_min,
        nominal_max_lb=nominal_max,
        diameter_id=body.diameterId,
        wood_id=body.woodId,
        shop_id=body.shopId,
        purchase_date=body.purchaseDate,
        description=body.description,
        entry_mode=body.entryMode,
        length_c_in=length_c_in,
        spine_band_id=body.spineBandId,
    )
    return _batch_dict(repo_batches.get_batch(db, batch_id))


@router.get("/{batch_id}")
def get_batch(batch_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = repo_batches.get_batch(db, batch_id)
    if row is None:
        raise HTTPException(404, f"no such batch {batch_id}")
    return _batch_dict(row)


@router.patch("/{batch_id}")
def patch_batch(
    batch_id: int, body: BatchPatchRequest, db: sqlite3.Connection = Depends(get_db)
):
    row = repo_batches.get_batch(db, batch_id)
    if row is None:
        raise HTTPException(404, f"no such batch {batch_id}")

    fields = body.model_dump(exclude_unset=True)
    entry_mode = fields.pop("entryMode", None)
    batch_no = fields.pop("batchNo", None)
    nominal_label_given = "nominalSpineLabel" in fields
    nominal_label = fields.pop("nominalSpineLabel", None)
    length_given = "length" in fields
    length_raw = fields.pop("length", None)

    db_fields = {_BATCH_FIELD_MAP[k]: v for k, v in fields.items()}
    if nominal_label_given:
        nominal_min, nominal_max = repo_batches.parse_nominal_range(nominal_label)
        db_fields["nominal_spine_label"] = nominal_label
        db_fields["nominal_min_lb"] = nominal_min
        db_fields["nominal_max_lb"] = nominal_max
    if length_given:
        db_fields["length_c_in"] = parse_length_in(length_raw) if length_raw is not None else None

    if batch_no is not None:
        repo_batches.rename_batch_no(db, batch_id, batch_no)
    if db_fields:
        repo_batches.update_batch(db, batch_id, db_fields)
    if entry_mode is not None:
        repo_batches.set_entry_mode(db, batch_id, entry_mode)

    return _batch_dict(repo_batches.get_batch(db, batch_id))


@router.delete("/{batch_id}")
def delete_batch(batch_id: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        repo_batches.delete_batch(db, batch_id)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("no such batch"):
            raise HTTPException(404, message) from exc
        raise HTTPException(400, message) from exc
    return {"status": "deleted"}


@router.get("/{batch_id}/summary")
def get_batch_summary(batch_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = repo_batches.get_batch(db, batch_id)
    if row is None:
        raise HTTPException(404, f"no such batch {batch_id}")
    return repo_batches.batch_summary(db, batch_id)


@router.post("/{batch_id}/shafts:extend")
def extend_batch(
    batch_id: int, body: BatchExtendRequest, db: sqlite3.Connection = Depends(get_db)
):
    try:
        new_total = repo_batches.extend_batch(db, batch_id, body.additionalCount)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"expectedCount": new_total}
