"""CRUD for the configurable spine-band list. Same endpoint shapes as
app/api/lookups.py (list, create, patch, reorder), but a dedicated router
since a band's real fields (min/max, in pounds) don't fit that module's
label-centric row shape -- see repo_spine_bands.py's docstring."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import SpineBandCreateRequest, SpineBandOrderRequest, SpineBandPatchRequest
from app.db import repo_spine_bands
from app.deps import get_db

router = APIRouter(prefix="/api/spine-bands", tags=["spine-bands"])


def _row_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "label": row["label"],
        "minMlb": row["min_mlb"],
        "maxMlb": row["max_mlb"],
        "sortOrder": row["sort_order"],
        "isActive": bool(row["is_active"]),
    }


@router.get("")
def list_spine_bands(db: sqlite3.Connection = Depends(get_db)):
    return [_row_dict(r) for r in repo_spine_bands.list_bands(db)]


@router.post("", status_code=201)
def create_spine_band(body: SpineBandCreateRequest, db: sqlite3.Connection = Depends(get_db)):
    try:
        band_id = repo_spine_bands.create_band(db, body.minLb, body.maxLb)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _row_dict(repo_spine_bands.get_band(db, band_id))


@router.patch("/{band_id}")
def patch_spine_band(
    band_id: int, body: SpineBandPatchRequest, db: sqlite3.Connection = Depends(get_db)
):
    if repo_spine_bands.get_band(db, band_id) is None:
        raise HTTPException(404, f"no such spine band {band_id}")
    fields = body.model_dump(exclude_unset=True)
    is_active = fields.pop("isActive", None)
    try:
        repo_spine_bands.update_band(
            db, band_id, min_lb=fields.get("minLb"), max_lb=fields.get("maxLb")
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if is_active is not None:
        repo_spine_bands.set_active(db, band_id, is_active)
    return _row_dict(repo_spine_bands.get_band(db, band_id))


@router.put("/order")
def reorder_spine_bands(body: SpineBandOrderRequest, db: sqlite3.Connection = Depends(get_db)):
    repo_spine_bands.reorder_bands(db, body.ids)
    return [_row_dict(r) for r in repo_spine_bands.list_bands(db)]


@router.delete("/{band_id}")
def delete_spine_band(band_id: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        repo_spine_bands.delete_band(db, band_id)
    except KeyError:
        raise HTTPException(404, f"no such spine band {band_id}")
    return {"status": "deleted"}
