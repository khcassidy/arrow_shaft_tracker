def test_list_diameter_options_orders_by_sort_order_not_label(client):
    r = client.get("/api/lookups/diameter")
    labels = [o["label"] for o in r.json()]
    # Seeded sort_order: 11/32"=1, 5/16"=2, 23/64"=3, Unknown=999 -- last.
    assert labels == ['11/32"', '5/16"', '23/64"', "Unknown"]


def test_create_wood_option_appends_at_end(client):
    r = client.post("/api/lookups/wood", json={"label": "Birch"})
    assert r.status_code == 201
    created = r.json()

    r = client.get("/api/lookups/wood")
    labels = [o["label"] for o in r.json()]
    assert labels[-2] == "Birch"  # last real entry, before the Unknown sentinel
    assert created["sortOrder"] == max(o["sortOrder"] for o in r.json() if o["label"] != "Unknown")


def test_reorder_rewrites_sort_order(client):
    before = client.get("/api/lookups/wood").json()
    real = [o for o in before if o["label"] != "Unknown"]
    reversed_ids = [o["id"] for o in reversed(real)]

    r = client.put("/api/lookups/wood/order", json={"ids": reversed_ids})
    assert r.status_code == 200
    after = [o["id"] for o in r.json() if o["label"] != "Unknown"]
    assert after == reversed_ids


def test_patch_lookup_renames_and_toggles_active(client):
    r = client.post("/api/lookups/shop", json={"label": "Old Name"})
    option_id = r.json()["id"]

    r = client.patch(f"/api/lookups/shop/{option_id}", json={"label": "New Name", "isActive": False})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "New Name"
    assert body["isActive"] is False


def test_unknown_lookup_kind_returns_404(client):
    r = client.get("/api/lookups/bogus")
    assert r.status_code == 404


def test_create_diameter_option_stores_sixty_fourths(client):
    r = client.post("/api/lookups/diameter", json={"label": '9/32"', "sixtyFourths": 18})
    assert r.status_code == 201
    assert r.json()["sixtyFourths"] == 18


def test_patch_diameter_option_updates_sixty_fourths(client):
    r = client.post("/api/lookups/diameter", json={"label": '9/32"', "sixtyFourths": 18})
    option_id = r.json()["id"]
    r = client.patch(f"/api/lookups/diameter/{option_id}", json={"sixtyFourths": 19})
    assert r.status_code == 200
    assert r.json()["sixtyFourths"] == 19
    assert r.json()["label"] == '9/32"'  # untouched


def test_patch_shop_updates_url_and_notes(client):
    r = client.post("/api/lookups/shop", json={"label": "Bearpaw"})
    option_id = r.json()["id"]
    r = client.patch(
        f"/api/lookups/shop/{option_id}",
        json={"url": "https://example.com", "notes": "good service"},
    )
    assert r.status_code == 200
    assert r.json()["url"] == "https://example.com"
    assert r.json()["notes"] == "good service"


def test_patch_wood_rejects_sixty_fourths_field(client):
    r = client.post("/api/lookups/wood", json={"label": "Maple"})
    option_id = r.json()["id"]
    r = client.patch(f"/api/lookups/wood/{option_id}", json={"sixtyFourths": 20})
    assert r.status_code == 400


def test_create_nock_option_without_weight_leaves_it_null(client):
    r = client.post("/api/lookups/nock", json={"label": "Test Nock"})
    assert r.status_code == 201
    body = r.json()
    assert body["weightText"] is None
    assert body["weightUnit"] is None
    assert body["unitWeightCgr"] is None


def test_create_nock_option_stores_default_weight_in_centigrains(client):
    r = client.post(
        "/api/lookups/nock", json={"label": "Test Nock", "weightText": "8", "weightUnit": "gr"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["weightText"] == "8"
    assert body["weightUnit"] == "gr"
    assert body["unitWeightCgr"] == 800


def test_patch_nock_option_recomputes_weight_from_new_text(client):
    r = client.post(
        "/api/lookups/nock", json={"label": "Test Nock", "weightText": "8", "weightUnit": "gr"}
    )
    option_id = r.json()["id"]
    r = client.patch(f"/api/lookups/nock/{option_id}", json={"weightText": "9"})
    assert r.status_code == 200
    body = r.json()
    assert body["weightText"] == "9"
    assert body["weightUnit"] == "gr"  # unchanged
    assert body["unitWeightCgr"] == 900


def test_patch_nock_option_clearing_weight_text_clears_unit_and_cgr(client):
    r = client.post(
        "/api/lookups/nock", json={"label": "Test Nock", "weightText": "8", "weightUnit": "gr"}
    )
    option_id = r.json()["id"]
    r = client.patch(f"/api/lookups/nock/{option_id}", json={"weightText": None})
    assert r.status_code == 200
    body = r.json()
    assert body["weightText"] is None
    assert body["weightUnit"] is None
    assert body["unitWeightCgr"] is None


def test_create_point_option_orders_after_seeded_points(client):
    r = client.post(
        "/api/lookups/point", json={"label": "Test Point", "weightText": "175", "weightUnit": "gr"}
    )
    assert r.status_code == 201
    assert r.json()["sortOrder"] == 6  # after the five seeded points


def test_create_finish_product_stores_brand_and_url(client):
    r = client.post(
        "/api/lookups/finish",
        json={"label": "Test Varnish", "brand": "Minwax", "url": "https://example.com"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["brand"] == "Minwax"
    assert body["url"] == "https://example.com"


def test_seeded_point_options_carry_default_weights(client):
    r = client.get("/api/lookups/point")
    by_label = {o["label"]: o for o in r.json()}
    assert by_label["Field point 125 gr"]["unitWeightCgr"] == 12500


def test_seeded_nock_options_have_no_default_weight(client):
    r = client.get("/api/lookups/nock")
    by_label = {o["label"]: o for o in r.json()}
    assert by_label['Bohning Classic 5/16"']["unitWeightCgr"] is None


def test_delete_lookup_removes_an_unused_option(client):
    option_id = client.post("/api/lookups/wood", json={"label": "Throwaway"}).json()["id"]
    r = client.delete(f"/api/lookups/wood/{option_id}")
    assert r.status_code == 200
    labels = [o["label"] for o in client.get("/api/lookups/wood").json()]
    assert "Throwaway" not in labels


def test_delete_lookup_404_for_an_unknown_option(client):
    r = client.delete("/api/lookups/wood/999999")
    assert r.status_code == 404


def test_delete_lookup_refuses_the_unknown_sentinel(client):
    r = client.delete("/api/lookups/wood/0")
    assert r.status_code == 400
    assert "Unknown" in client.get("/api/lookups/wood").json()[-1]["label"]


def test_delete_lookup_refuses_an_option_still_in_use(client):
    wood_id = client.post("/api/lookups/wood", json={"label": "In Use Wood"}).json()["id"]
    client.post("/api/batches", json={"batchNo": 5001, "expectedCount": 1, "woodId": wood_id})
    r = client.delete(f"/api/lookups/wood/{wood_id}")
    assert r.status_code == 409
    labels = [o["label"] for o in client.get("/api/lookups/wood").json()]
    assert "In Use Wood" in labels
