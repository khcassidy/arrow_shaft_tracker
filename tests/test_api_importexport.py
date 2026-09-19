import json

import pytest


@pytest.fixture
def batch_with_data(client):
    r = client.post(
        "/api/batches",
        json={"batchNo": 19, "expectedCount": 2, "nominalSpineLabel": "55-60#"},
    )
    batch_id = r.json()["id"]
    client.patch(
        f"/api/batches/{batch_id}/shafts/1",
        json={"spineA": "56", "spineB": "55", "weight": "23.23", "weightUnit": "g"},
    )
    client.patch(
        f"/api/batches/{batch_id}/shafts/2",
        json={"spineA": "58", "weight": "350", "weightUnit": "gr"},
    )
    return batch_id


# ---- export ----


def test_export_json_shape(client, batch_with_data):
    r = client.get("/api/export/json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    data = r.json()
    assert len(data["batches"]) == 1
    batch = data["batches"][0]
    assert batch["batchNo"] == 19
    assert batch["nominalSpineLabel"] == "55-60#"
    shafts = {s["seq"]: s for s in batch["shafts"]}
    assert shafts[1]["spineA"] == "56"
    assert shafts[1]["weightText"] == "23.23"
    assert shafts[1]["weightUnit"] == "g"
    assert shafts[2]["weightText"] == "350"
    assert shafts[2]["weightUnit"] == "gr"


def test_export_csv_all_shafts(client, batch_with_data):
    r = client.get("/api/export/csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.text.lstrip("﻿")
    lines = text.strip().split("\r\n")
    assert lines[0].split(",")[:3] == ["Batch", "Seq", "Label"]
    assert any("19-01" in line for line in lines)
    assert any("23.23" in line for line in lines)


def test_export_batch_csv(client, batch_with_data):
    r = client.get(f"/api/batches/{batch_with_data}/export/csv")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    text = r.text.lstrip("﻿")
    assert "19-01" in text
    assert "19-02" in text


def test_export_batch_csv_missing_batch_404(client):
    r = client.get("/api/batches/999/export/csv")
    assert r.status_code == 404


# ---- import: CSV ----

CSV_TEXT = (
    "Batch,Seq,Diameter,Wood,SpineA,SpineB,WeightG,Quality,Notes\r\n"
    '30,1,"11/32""",Northern Pine,56,55,23.23,USABLE,first\r\n'
    '30,2,"11/32""",Northern Pine,58,58,24.70,,second\r\n'
)


def test_import_csv_preview_reports_new_batch(client):
    r = client.post(
        "/api/import/preview",
        files={"file": ("shafts.csv", CSV_TEXT, "text/csv")},
        data={"format": "csv"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["report"]["batchesNew"] == [30]
    assert body["report"]["rowCount"] == 2
    assert body["report"]["errors"] == []
    assert body["token"]


def test_import_csv_commit_creates_batch_and_shafts(client):
    preview = client.post(
        "/api/import/preview",
        files={"file": ("shafts.csv", CSV_TEXT, "text/csv")},
        data={"format": "csv"},
    ).json()
    r = client.post("/api/import/commit", json={"token": preview["token"]})
    assert r.status_code == 200
    assert r.json()["batchesCreated"] == 1
    assert r.json()["shaftsWritten"] == 2

    batches = client.get("/api/batches").json()
    batch = next(b for b in batches if b["batchNo"] == 30)
    shafts = client.get(f"/api/batches/{batch['id']}/shafts").json()
    row1 = next(s for s in shafts if s["seq"] == 1)
    assert row1["spineACp"] == 5600
    assert row1["spineBCp"] == 5500
    assert row1["weightCg"] == 2323
    assert row1["quality"] == "USABLE"
    assert row1["notes"] == "first"


def test_import_csv_unknown_diameter_is_staged_for_creation_not_an_error(client):
    """A label the database does not have yet is offered for creation, not
    treated as a failure. The preview is where a person catches a typo."""
    csv_text = "Batch,Seq,Diameter,SpineA\r\n40,1,9/16 made up,56\r\n"
    r = client.post(
        "/api/import/preview",
        files={"file": ("new-diameter.csv", csv_text, "text/csv")},
        data={"format": "csv"},
    )
    body = r.json()
    assert body["report"]["errors"] == []
    assert body["report"]["lookupsToCreate"]["diameter"] == ["9/16 made up"]


def test_import_csv_commit_rejected_when_preview_had_errors(client):
    bad_csv = "Batch,Seq,SpineA\r\n40,1,not a number\r\n"
    preview = client.post(
        "/api/import/preview",
        files={"file": ("bad.csv", bad_csv, "text/csv")},
        data={"format": "csv"},
    ).json()
    assert preview["report"]["errors"]
    r = client.post("/api/import/commit", json={"token": preview["token"]})
    assert r.status_code == 400


def test_import_csv_creates_the_shop_it_names(client):
    """The regression this path exists to prevent: 0001_initial.sql seeds no
    shops at all, so before a lookup label became creatable, every row that
    named any shop failed with "unknown shop" and blocked the whole file."""
    csv_text = (
        "Batch,Seq,Shop,SpineA\r\n"
        "41,1,Dutch Bow Store,56\r\n"
        "41,2,Dutch Bow Store,57\r\n"
    )
    preview = client.post(
        "/api/import/preview",
        files={"file": ("shafts.csv", csv_text, "text/csv")},
        data={"format": "csv"},
    ).json()
    assert preview["report"]["errors"] == []
    assert preview["report"]["lookupsToCreate"]["shop"] == ["Dutch Bow Store"]

    commit = client.post("/api/import/commit", json={"token": preview["token"]}).json()
    assert commit["lookupsCreated"]["shop"] == ["Dutch Bow Store"]

    shops = client.get("/api/lookups/shop").json()
    shop = next(s for s in shops if s["label"] == "Dutch Bow Store")
    batch = next(b for b in client.get("/api/batches").json() if b["batchNo"] == 41)
    assert batch["shopId"] == shop["id"]


def test_import_csv_reuses_an_existing_shop_whatever_its_case(client):
    client.post("/api/lookups/shop", json={"label": "Dutch Bow Store"})
    csv_text = "Batch,Seq,Shop,SpineA\r\n42,1,  dutch bow STORE ,56\r\n"
    preview = client.post(
        "/api/import/preview",
        files={"file": ("shafts.csv", csv_text, "text/csv")},
        data={"format": "csv"},
    ).json()
    assert preview["report"]["lookupsToCreate"]["shop"] == []
    client.post("/api/import/commit", json={"token": preview["token"]})
    assert len(client.get("/api/lookups/shop").json()) == 1


def test_import_csv_skips_rows_for_existing_batch_no(client, batch_with_data):
    csv_text = "Batch,Seq,SpineA\r\n19,1,50\r\n"  # batch 19 already exists
    r = client.post(
        "/api/import/preview",
        files={"file": ("shafts.csv", csv_text, "text/csv")},
        data={"format": "csv"},
    )
    body = r.json()
    assert body["report"]["batchesSkippedExisting"] == [19]
    assert body["report"]["batchesNew"] == []
    assert body["report"]["rowCount"] == 0


def test_import_commit_cannot_run_twice(client):
    preview = client.post(
        "/api/import/preview",
        files={"file": ("shafts.csv", CSV_TEXT, "text/csv")},
        data={"format": "csv"},
    ).json()
    client.post("/api/import/commit", json={"token": preview["token"]})
    r = client.post("/api/import/commit", json={"token": preview["token"]})
    assert r.status_code == 400


def test_import_commit_unknown_token_400(client):
    r = client.post("/api/import/commit", json={"token": "does-not-exist"})
    assert r.status_code == 400


# ---- import: JSON round trip ----


def test_import_json_round_trips_an_export(client, batch_with_data):
    export = client.get("/api/export/json").json()
    export["batches"][0]["batchNo"] = 77  # avoid colliding with the existing batch

    preview = client.post(
        "/api/import/preview",
        files={"file": ("backup.json", json.dumps(export), "application/json")},
        data={"format": "json"},
    ).json()
    assert preview["report"]["batchesNew"] == [77]

    commit = client.post("/api/import/commit", json={"token": preview["token"]}).json()
    assert commit["batchesCreated"] == 1

    batches = client.get("/api/batches").json()
    new_batch = next(b for b in batches if b["batchNo"] == 77)
    shafts = client.get(f"/api/batches/{new_batch['id']}/shafts").json()
    row2 = next(s for s in shafts if s["seq"] == 2)
    assert row2["weightText"] == "350"
    assert row2["weightUnit"] == "gr"
    assert row2["weightCg"] == 2268  # 350 gr -> 22.68 g, matching core/units.py


def _restore(client, export, filename="backup.json"):
    """Previews and commits a JSON backup, and returns the commit result."""
    preview = client.post(
        "/api/import/preview",
        files={"file": (filename, json.dumps(export), "application/json")},
        data={"format": "json"},
    ).json()
    assert preview["report"]["errors"] == [], preview["report"]["errors"]
    return preview, client.post(
        "/api/import/commit", json={"token": preview["token"]}
    ).json()


def test_export_json_carries_the_shop_a_batch_was_bought_from(client, batch_with_data):
    shop = client.post(
        "/api/lookups/shop",
        json={"label": "Dutch Bow Store", "url": "https://example.test", "notes": "EU"},
    ).json()
    client.patch(f"/api/batches/{batch_with_data}", json={"shopId": shop["id"]})

    export = client.get("/api/export/json").json()
    assert export["batches"][0]["shop"] == "Dutch Bow Store"
    assert {"label": "Dutch Bow Store", "url": "https://example.test", "notes": "EU"} in (
        export["shops"]
    )


def test_import_json_restores_a_shop_into_a_database_that_has_none(client):
    """The exact failure the archer hit: a backup naming a shop, restored
    into a database seeded with no shops. Every row reported "unknown shop"
    and nothing could be committed at all."""
    backup = {
        "diameters": [{"label": '11/32"', "sixtyFourths": 22}],
        "woods": [{"label": "Northern Pine"}],
        "shops": [{"label": "Dutch Bow Store", "url": "https://example.test", "notes": "EU"}],
        "batches": [
            {
                "batchNo": 21,
                "nominalSpineLabel": "55-60#",
                "diameter": '11/32"',
                "wood": "Northern Pine",
                "shop": "Dutch Bow Store",
                "purchaseDate": "2026-09-01",
                "shafts": [
                    {"seq": 1, "spineA": "56", "spineB": "55", "weightText": "23.23",
                     "weightUnit": "g"},
                    {"seq": 2, "spineA": "58", "spineB": "58", "weightText": "24.70",
                     "weightUnit": "g"},
                ],
            }
        ],
    }
    assert client.get("/api/lookups/shop").json() == []

    preview, commit = _restore(client, backup)
    assert preview["report"]["lookupsToCreate"]["shop"] == ["Dutch Bow Store"]
    assert commit["batchesCreated"] == 1
    assert commit["shaftsWritten"] == 2

    shop = client.get("/api/lookups/shop").json()[0]
    assert shop["label"] == "Dutch Bow Store"
    assert shop["url"] == "https://example.test"  # attributes come from the file
    assert shop["notes"] == "EU"
    batch = next(b for b in client.get("/api/batches").json() if b["batchNo"] == 21)
    assert batch["shopId"] == shop["id"]


def test_import_json_creates_a_wood_the_seed_does_not_have(client):
    backup = {
        "woods": [{"label": "Sitka Spruce"}],
        "batches": [
            {"batchNo": 22, "wood": "Sitka Spruce", "shafts": [{"seq": 1, "spineA": "56"}]}
        ],
    }
    preview, _ = _restore(client, backup)
    assert preview["report"]["lookupsToCreate"]["wood"] == ["Sitka Spruce"]
    woods = client.get("/api/lookups/wood").json()
    wood = next(w for w in woods if w["label"] == "Sitka Spruce")
    batch = next(b for b in client.get("/api/batches").json() if b["batchNo"] == 22)
    assert batch["woodId"] == wood["id"]


def test_import_json_round_trips_length_and_spine_band(client):
    """Length keeps the batch-default/per-shaft-override split: shaft 1
    inherits, shaft 2 overrides, and both stay that way after a restore."""
    bands = client.get("/api/spine-bands").json()
    band_id = next(b["id"] for b in bands if b["label"] == "55-60")
    r = client.post(
        "/api/batches",
        json={"batchNo": 23, "expectedCount": 2, "nominalSpineLabel": "55-60#",
              "length": "32", "spineBandId": band_id},
    )
    batch_id = r.json()["id"]
    client.patch(f"/api/batches/{batch_id}/shafts/2", json={"length": "31.5"})

    export = client.get("/api/export/json").json()
    exported = export["batches"][0]
    assert exported["length"] == "32.00"
    assert exported["spineBand"] == "55-60"
    assert exported["shafts"][0]["length"] is None  # inherits, never materialised
    assert exported["shafts"][1]["length"] == "31.50"

    exported["batchNo"] = 24
    _restore(client, export)

    new_batch = next(b for b in client.get("/api/batches").json() if b["batchNo"] == 24)
    assert new_batch["lengthCIn"] == 3200
    assert new_batch["spineBandId"] == band_id
    shafts = client.get(f"/api/batches/{new_batch['id']}/shafts").json()
    assert shafts[0]["lengthCIn"] is None
    assert shafts[1]["lengthCIn"] == 3150


def test_export_csv_has_a_length_column(client):
    r = client.post(
        "/api/batches", json={"batchNo": 25, "expectedCount": 1, "length": "32"}
    )
    client.patch(f"/api/batches/{r.json()['id']}/shafts/1", json={"spineA": "56"})
    text = client.get("/api/export/csv").text.lstrip("﻿")
    header, row = text.strip().split("\r\n")[:2]
    columns = header.split(",")
    assert "Length" in columns
    assert row.split(",")[columns.index("Length")] == "32.00"  # effective, inherited
