def test_list_spine_bands_is_seeded_and_ordered(client):
    r = client.get("/api/spine-bands")
    labels = [b["label"] for b in r.json()]
    assert labels == ["30-35", "35-40", "40-45", "45-50", "50-55", "55-60", "60-65", "65-70"]


def test_create_spine_band_appends_at_end(client):
    r = client.post("/api/spine-bands", json={"minLb": "70", "maxLb": "75"})
    assert r.status_code == 201
    created = r.json()
    assert created["label"] == "70-75"
    assert created["minMlb"] == 70000
    assert created["maxMlb"] == 75000

    r = client.get("/api/spine-bands")
    bands = r.json()
    assert bands[-1]["id"] == created["id"]


def test_create_spine_band_rejects_max_not_greater_than_min(client):
    r = client.post("/api/spine-bands", json={"minLb": "50", "maxLb": "50"})
    assert r.status_code == 400
    r = client.post("/api/spine-bands", json={"minLb": "50", "maxLb": "45"})
    assert r.status_code == 400


def test_patch_spine_band_updates_bounds_and_relabels(client):
    r = client.post("/api/spine-bands", json={"minLb": "70", "maxLb": "75"})
    band_id = r.json()["id"]

    r = client.patch(f"/api/spine-bands/{band_id}", json={"maxLb": "80"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "70-80"
    assert body["maxMlb"] == 80000
    assert body["minMlb"] == 70000  # untouched


def test_patch_spine_band_rejects_reversed_range(client):
    r = client.post("/api/spine-bands", json={"minLb": "70", "maxLb": "75"})
    band_id = r.json()["id"]
    r = client.patch(f"/api/spine-bands/{band_id}", json={"minLb": "80"})
    assert r.status_code == 400


def test_patch_spine_band_toggles_active(client):
    r = client.post("/api/spine-bands", json={"minLb": "70", "maxLb": "75"})
    band_id = r.json()["id"]
    r = client.patch(f"/api/spine-bands/{band_id}", json={"isActive": False})
    assert r.status_code == 200
    assert r.json()["isActive"] is False


def test_reorder_spine_bands_rewrites_sort_order(client):
    before = client.get("/api/spine-bands").json()
    reversed_ids = [b["id"] for b in reversed(before)]

    r = client.put("/api/spine-bands/order", json={"ids": reversed_ids})
    assert r.status_code == 200
    after = [b["id"] for b in r.json()]
    assert after == reversed_ids


def test_delete_spine_band_removes_an_unused_band(client):
    band_id = client.post("/api/spine-bands", json={"minLb": "70", "maxLb": "75"}).json()["id"]
    r = client.delete(f"/api/spine-bands/{band_id}")
    assert r.status_code == 200
    labels = [b["label"] for b in client.get("/api/spine-bands").json()]
    assert "70-75" not in labels


def test_delete_spine_band_404_for_an_unknown_band(client):
    r = client.delete("/api/spine-bands/999999")
    assert r.status_code == 404


def test_delete_spine_band_refuses_a_band_still_assigned_to_a_batch(client):
    band_id = client.post("/api/spine-bands", json={"minLb": "70", "maxLb": "75"}).json()["id"]
    client.post("/api/batches", json={"batchNo": 5002, "expectedCount": 1, "spineBandId": band_id})
    r = client.delete(f"/api/spine-bands/{band_id}")
    assert r.status_code == 409
    labels = [b["label"] for b in client.get("/api/spine-bands").json()]
    assert "70-75" in labels
