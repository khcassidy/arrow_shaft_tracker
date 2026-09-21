from tests.test_api_sets import _make_batch_with_measured_shafts


def _make_set(client, count=3):
    _, shaft_ids = _make_batch_with_measured_shafts(client, 19, count)
    r = client.post(
        "/api/sets",
        json={"name": "Set A", "diameterId": 1, "woodId": 1, "shaftIds": shaft_ids},
    )
    return r.json()["id"]


def test_start_build_creates_one_arrow_per_member(client):
    set_id = _make_set(client, 3)
    r = client.post(f"/api/sets/{set_id}/arrows:start")
    assert r.status_code == 200
    arrows = r.json()
    assert len(arrows) == 3
    assert all(a["setId"] == set_id for a in arrows)
    assert all(a["nockLabel"] == "Unknown" for a in arrows)  # no default chosen yet
    assert all(a["fletchCount"] == 3 for a in arrows)


def test_start_build_is_idempotent(client):
    set_id = _make_set(client, 2)
    first = client.post(f"/api/sets/{set_id}/arrows:start").json()
    second = client.post(f"/api/sets/{set_id}/arrows:start").json()
    assert [a["id"] for a in first] == [a["id"] for a in second]


def test_start_build_404_for_an_unknown_set(client):
    r = client.post("/api/sets/999999/arrows:start")
    assert r.status_code == 404


def test_start_build_refuses_a_disbanded_set(client):
    set_id = _make_set(client, 1)
    client.delete(f"/api/sets/{set_id}")
    r = client.post(f"/api/sets/{set_id}/arrows:start")
    assert r.status_code == 400


def test_list_set_arrows_orders_by_batch_and_seq(client):
    set_id = _make_set(client, 3)
    client.post(f"/api/sets/{set_id}/arrows:start")
    r = client.get(f"/api/sets/{set_id}/arrows")
    assert r.status_code == 200
    seqs = [a["seq"] for a in r.json()]
    assert seqs == sorted(seqs)


def test_patch_arrow_updates_one_field_and_leaves_others(client):
    set_id = _make_set(client, 1)
    arrow_id = client.post(f"/api/sets/{set_id}/arrows:start").json()[0]["id"]

    r = client.patch(f"/api/arrows/{arrow_id}", json={"pointOptionId": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["pointOptionId"] == 2
    assert body["fletchCount"] == 3  # untouched


def test_patch_arrow_parses_cut_length_and_weights(client):
    set_id = _make_set(client, 1)
    arrow_id = client.post(f"/api/sets/{set_id}/arrows:start").json()[0]["id"]

    r = client.patch(
        f"/api/arrows/{arrow_id}",
        json={"cutLength": "28.50", "afterFinishWeight": "312.40", "finishedWeight": "345.10"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cutLength"] == "28.50"
    assert body["afterFinishWeight"] == "312.40"
    assert body["finishedWeight"] == "345.10"


def test_patch_arrow_clearing_a_weight_sets_it_back_to_none(client):
    set_id = _make_set(client, 1)
    arrow_id = client.post(f"/api/sets/{set_id}/arrows:start").json()[0]["id"]
    client.patch(f"/api/arrows/{arrow_id}", json={"finishedWeight": "345.10"})

    r = client.patch(f"/api/arrows/{arrow_id}", json={"finishedWeight": None})
    assert r.status_code == 200
    assert r.json()["finishedWeight"] is None


def test_patch_arrow_404_for_an_unknown_arrow(client):
    r = client.patch("/api/arrows/999999", json={"notes": "x"})
    assert r.status_code == 404


def test_patch_defaults_seeds_arrows_not_yet_built(client):
    set_id = _make_set(client, 2)
    r = client.patch(f"/api/sets/{set_id}/defaults", json={"pointOptionId": 3, "fletchCount": 4})
    assert r.status_code == 200
    body = r.json()
    assert body["defaultPointOptionId"] == 3
    assert body["defaultFletchCount"] == 4

    arrows = client.post(f"/api/sets/{set_id}/arrows:start").json()
    assert all(a["pointOptionId"] == 3 for a in arrows)
    assert all(a["fletchCount"] == 4 for a in arrows)


def test_patch_defaults_cascades_to_arrows_still_matching_the_old_default(client):
    set_id = _make_set(client, 3)
    arrows = client.post(f"/api/sets/{set_id}/arrows:start").json()

    # One arrow diverges deliberately.
    client.patch(f"/api/arrows/{arrows[0]['id']}", json={"pointOptionId": 5})

    r = client.patch(f"/api/sets/{set_id}/defaults", json={"pointOptionId": 2})
    assert r.status_code == 200

    updated = {a["id"]: a for a in r.json()["arrows"]}
    assert updated[arrows[0]["id"]]["pointOptionId"] == 5  # left alone, already diverged
    assert updated[arrows[1]["id"]]["pointOptionId"] == 2  # cascaded
    assert updated[arrows[2]["id"]]["pointOptionId"] == 2  # cascaded


def test_patch_defaults_cut_length_cascades_the_same_way(client):
    set_id = _make_set(client, 2)
    arrows = client.post(f"/api/sets/{set_id}/arrows:start").json()

    client.patch(f"/api/sets/{set_id}/defaults", json={"cutLength": "28.50"})
    client.patch(f"/api/arrows/{arrows[0]['id']}", json={"cutLength": "27.00"})

    r = client.patch(f"/api/sets/{set_id}/defaults", json={"cutLength": "29.00"})
    updated = {a["id"]: a for a in r.json()["arrows"]}
    assert updated[arrows[0]["id"]]["cutLength"] == "27.00"  # already diverged
    assert updated[arrows[1]["id"]]["cutLength"] == "29.00"  # cascaded


def test_cancel_build_deletes_untouched_arrows(client):
    set_id = _make_set(client, 2)
    client.post(f"/api/sets/{set_id}/arrows:start")
    r = client.delete(f"/api/sets/{set_id}/arrows")
    assert r.status_code == 200
    assert client.get(f"/api/sets/{set_id}/arrows").json() == []


def test_cancel_build_refuses_once_an_arrow_has_a_measurement(client):
    set_id = _make_set(client, 1)
    arrow_id = client.post(f"/api/sets/{set_id}/arrows:start").json()[0]["id"]
    client.patch(f"/api/arrows/{arrow_id}", json={"cutLength": "28.50"})

    r = client.delete(f"/api/sets/{set_id}/arrows")
    assert r.status_code == 400
    assert len(client.get(f"/api/sets/{set_id}/arrows").json()) == 1
