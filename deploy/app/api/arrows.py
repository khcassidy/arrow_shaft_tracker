"""Single-arrow edits. The set-scoped collection endpoints (start a
build, list, edit the defaults header, cancel a build) live on
app/api/sets.py's own router instead, since they all key off set_id
first -- this file is the one place an individual arrow_id is the key,
matching PATCH /api/shafts/{id}'s own shape.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import ArrowPatchRequest
from app.db import repo_arrows
from app.deps import get_db
from core.units import format_length_in, format_weight_cg

router = APIRouter(prefix="/api/arrows", tags=["arrows"])


def _row_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    return {
        "id": data["id"],
        "setId": data["set_id"],
        "shaftId": data["shaft_id"],
        "shaftLabel": data["shaft_label"],
        "batchNo": data["batch_no"],
        "seq": data["seq"],
        "avgSpineMlb": data["avg_spine_mlb"],
        "weightCg": data["weight_cg"],
        "nockOptionId": data["nock_option_id"],
        "nockLabel": data["nock_label"],
        "fletchingOptionId": data["fletching_option_id"],
        "fletchingLabel": data["fletching_label"],
        "fletchCount": data["fletch_count"],
        "pointOptionId": data["point_option_id"],
        "pointLabel": data["point_label"],
        "finishProductId": data["finish_product_id"],
        "finishLabel": data["finish_label"],
        "cutLength": format_length_in(data["cut_length_c_in"]) if data["cut_length_c_in"] is not None else None,
        "afterFinishWeight": format_weight_cg(data["after_finish_weight_cg"])
        if data["after_finish_weight_cg"] is not None
        else None,
        "afterFletchingWeight": format_weight_cg(data["after_fletching_weight_cg"])
        if data["after_fletching_weight_cg"] is not None
        else None,
        "finishedWeight": format_weight_cg(data["finished_weight_cg"])
        if data["finished_weight_cg"] is not None
        else None,
        "notes": data["notes"],
        "createdAt": data["created_at"],
        "updatedAt": data["updated_at"],
    }


@router.patch("/{arrow_id}")
def patch_arrow(arrow_id: int, body: ArrowPatchRequest, db: sqlite3.Connection = Depends(get_db)):
    fields = body.model_dump(exclude_unset=True)
    try:
        row = repo_arrows.update_arrow(db, arrow_id, fields)
    except KeyError:
        raise HTTPException(404, f"no such arrow {arrow_id}")
    return _row_dict(row)
