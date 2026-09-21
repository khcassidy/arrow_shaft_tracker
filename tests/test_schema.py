import sqlite3

import pytest

from app.db.migrate import migrate


def _insert_batch(db, batch_no=19, seq_width=2, expected_count=1):
    db.execute(
        "INSERT INTO batch(batch_no, seq_width, expected_count) VALUES (?, ?, ?)",
        (batch_no, seq_width, expected_count),
    )
    db.commit()
    return db.execute(
        "SELECT id FROM batch WHERE batch_no = ?", (batch_no,)
    ).fetchone()["id"]


def test_migrate_sets_user_version(db):
    assert db.execute("PRAGMA user_version").fetchone()[0] == 7


def test_migrate_is_idempotent(db):
    assert migrate(db) == 7
    assert migrate(db) == 7


def test_diameter_option_seed_includes_unknown_sentinel(db):
    row = db.execute("SELECT * FROM diameter_option WHERE id = 0").fetchone()
    assert row["is_unknown"] == 1
    assert row["sixty_fourths"] is None


def test_wood_option_seed_includes_unknown_sentinel(db):
    row = db.execute("SELECT * FROM wood_option WHERE id = 0").fetchone()
    assert row["is_unknown"] == 1


def test_unknown_sentinel_is_unique_per_lookup(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO diameter_option(id,label,sort_order,is_unknown) "
            "VALUES (99,'Also unknown',998,1)"
        )


def test_default_param_set_matches_workbook(db):
    row = db.execute("SELECT * FROM param_set WHERE is_default = 1").fetchone()
    assert row["spine_tol_mlb"] == 3000
    assert row["weight_tol_cg"] == 50
    assert row["spec_min_mlb"] == 54000
    assert row["spec_max_mlb"] == 60000
    assert row["ab_tol_cp"] == 100
    assert row["min_group_size"] == 3


def test_spine_band_seed_has_eight_bands_in_order(db):
    rows = db.execute("SELECT label, min_mlb, max_mlb FROM spine_band ORDER BY sort_order").fetchall()
    assert [r["label"] for r in rows] == [
        "30-35", "35-40", "40-45", "45-50", "50-55", "55-60", "60-65", "65-70",
    ]
    assert rows[5]["min_mlb"] == 55000
    assert rows[5]["max_mlb"] == 60000


def test_spine_band_rejects_reversed_range(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO spine_band(label, min_mlb, max_mlb, sort_order) VALUES (?, ?, ?, ?)",
            ("50-45", 50000, 45000, 9),
        )


def test_spine_band_rejects_equal_bounds(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO spine_band(label, min_mlb, max_mlb, sort_order) VALUES (?, ?, ?, ?)",
            ("45-45", 45000, 45000, 9),
        )


def test_only_one_default_param_set_allowed(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO param_set
               (name, is_default, spine_tol_mlb, weight_tol_cg,
                spec_min_mlb, spec_max_mlb, ab_tol_cp)
               VALUES ('Second default', 1, 3000, 50, 54000, 60000, 100)"""
        )


def test_shaft_requires_a_batch(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO shaft(batch_id, seq, label) VALUES (999, 1, '999-01')"
        )


def test_avg_spine_mlb_check_rejects_wrong_value(db):
    batch_id = _insert_batch(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO shaft
               (batch_id, seq, label, spine_count, spine_sum_cp,
                spine_min_cp, spine_max_cp, avg_spine_mlb, spine_spread_cp)
               VALUES (?, 1, '19-01', 2, 11100, 5500, 5600, 55501, 100)""",
            (batch_id,),
        )


def test_avg_spine_mlb_check_accepts_correct_value(db):
    batch_id = _insert_batch(db)
    db.execute(
        """INSERT INTO shaft
           (batch_id, seq, label, spine_count, spine_sum_cp,
            spine_min_cp, spine_max_cp, avg_spine_mlb, spine_spread_cp)
           VALUES (?, 1, '19-01', 2, 11100, 5500, 5600, 55500, 100)""",
        (batch_id,),
    )
    db.commit()
    row = db.execute(
        "SELECT avg_spine_mlb FROM shaft WHERE label = '19-01'"
    ).fetchone()
    assert row["avg_spine_mlb"] == 55500


def test_consumed_set_id_and_consumed_at_travel_together(db):
    batch_id = _insert_batch(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO shaft(batch_id, seq, label, consumed_set_id) "
            "VALUES (?, 1, '19-01', 1)",
            (batch_id,),
        )


def test_pool_version_bumps_on_shaft_insert(db):
    before = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    batch_id = _insert_batch(db)
    db.execute(
        "INSERT INTO shaft(batch_id, seq, label) VALUES (?, 1, '19-01')",
        (batch_id,),
    )
    after = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    assert after == before + 1


def test_pool_version_bumps_on_shaft_update(db):
    batch_id = _insert_batch(db)
    db.execute(
        "INSERT INTO shaft(batch_id, seq, label) VALUES (?, 1, '19-01')",
        (batch_id,),
    )
    before = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    db.execute("UPDATE shaft SET notes = 'x' WHERE label = '19-01'")
    after = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    assert after == before + 1


def test_pool_version_bumps_on_shaft_delete(db):
    batch_id = _insert_batch(db)
    db.execute(
        "INSERT INTO shaft(batch_id, seq, label) VALUES (?, 1, '19-01')",
        (batch_id,),
    )
    before = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    db.execute("DELETE FROM shaft WHERE label = '19-01'")
    after = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    assert after == before + 1


def test_pool_version_bumps_on_spine_reading_insert(db):
    batch_id = _insert_batch(db)
    db.execute(
        "INSERT INTO shaft(batch_id, seq, label) VALUES (?, 1, '19-01')",
        (batch_id,),
    )
    shaft_id = db.execute(
        "SELECT id FROM shaft WHERE label='19-01'"
    ).fetchone()["id"]
    before = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    db.execute(
        "INSERT INTO shaft_spine_reading(shaft_id, ordinal, value_cp, entered_text) "
        "VALUES (?, 1, 5600, '56')",
        (shaft_id,),
    )
    after = db.execute(
        "SELECT int_value FROM app_meta WHERE key='pool_version'"
    ).fetchone()[0]
    assert after == before + 1


def test_shaft_entry_v_pivots_readings_to_columns(db):
    batch_id = _insert_batch(db)
    db.execute(
        """INSERT INTO shaft
           (batch_id, seq, label, spine_count, spine_sum_cp,
            spine_min_cp, spine_max_cp, avg_spine_mlb, spine_spread_cp)
           VALUES (?, 1, '19-01', 2, 11100, 5500, 5600, 55500, 100)""",
        (batch_id,),
    )
    shaft_id = db.execute(
        "SELECT id FROM shaft WHERE label='19-01'"
    ).fetchone()["id"]
    db.execute(
        "INSERT INTO shaft_spine_reading(shaft_id, ordinal, value_cp, entered_text) "
        "VALUES (?, 1, 5600, '56')",
        (shaft_id,),
    )
    db.execute(
        "INSERT INTO shaft_spine_reading(shaft_id, ordinal, value_cp, entered_text) "
        "VALUES (?, 2, 5500, '55')",
        (shaft_id,),
    )
    row = db.execute("SELECT * FROM shaft_entry_v WHERE label = '19-01'").fetchone()
    assert row["spine_a_cp"] == 5600
    assert row["spine_b_cp"] == 5500
    assert row["avg_spine_mlb"] == 55500


def test_batch_length_check_rejects_non_positive(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO batch(batch_no, seq_width, expected_count, length_c_in) "
            "VALUES (19, 2, 1, 0)"
        )


def test_batch_length_check_accepts_positive(db):
    db.execute(
        "INSERT INTO batch(batch_no, seq_width, expected_count, length_c_in) "
        "VALUES (19, 2, 1, 3225)"
    )
    db.commit()
    row = db.execute("SELECT length_c_in FROM batch WHERE batch_no = 19").fetchone()
    assert row["length_c_in"] == 3225


def test_shaft_length_check_rejects_non_positive(db):
    batch_id = _insert_batch(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO shaft(batch_id, seq, label, length_c_in) VALUES (?, 1, '19-01', -1)",
            (batch_id,),
        )


def test_param_set_length_tol_check_rejects_negative(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO param_set
               (name, spine_tol_mlb, weight_tol_cg,
                spec_min_mlb, spec_max_mlb, ab_tol_cp, length_tol_c_in)
               VALUES ('Bad length tol', 3000, 50, 54000, 60000, 100, -1)"""
        )


def test_param_set_length_tol_defaults_to_null(db):
    row = db.execute("SELECT * FROM param_set WHERE is_default = 1").fetchone()
    assert row["length_tol_c_in"] is None


def test_shaft_entry_v_effective_length_falls_back_to_batch_default(db):
    batch_id = _insert_batch(db, expected_count=2)
    db.execute("UPDATE batch SET length_c_in = 3200 WHERE id = ?", (batch_id,))
    db.execute("INSERT INTO shaft(batch_id, seq, label) VALUES (?, 1, '19-01')", (batch_id,))
    db.execute(
        "INSERT INTO shaft(batch_id, seq, label, length_c_in) VALUES (?, 2, '19-02', 3300)",
        (batch_id,),
    )
    rows = {
        r["label"]: r
        for r in db.execute("SELECT * FROM shaft_entry_v WHERE batch_id = ?", (batch_id,))
    }
    assert rows["19-01"]["length_c_in"] is None
    assert rows["19-01"]["effective_length_c_in"] == 3200
    assert rows["19-02"]["length_c_in"] == 3300
    assert rows["19-02"]["effective_length_c_in"] == 3300


def test_analysable_pool_predicate_excludes_junk_and_unmeasured(db):
    batch_id = _insert_batch(db, expected_count=2)
    db.execute(
        """INSERT INTO shaft
           (batch_id, seq, label, spine_count, spine_sum_cp,
            spine_min_cp, spine_max_cp, avg_spine_mlb, spine_spread_cp,
            weight_cg, weight_text, weight_unit, quality)
           VALUES (?, 1, '19-01', 2, 11100, 5500, 5600, 55500, 100,
                   2323, '23.23', 'g', 'JUNK')""",
        (batch_id,),
    )
    db.execute(
        """INSERT INTO shaft
           (batch_id, seq, label, spine_count, spine_sum_cp,
            spine_min_cp, spine_max_cp, avg_spine_mlb, spine_spread_cp,
            weight_cg, weight_text, weight_unit, quality)
           VALUES (?, 2, '19-02', 2, 11600, 5800, 5800, 58000, 0,
                   2470, '24.70', 'g', 'USABLE')""",
        (batch_id,),
    )
    rows = db.execute(
        """SELECT label FROM shaft
           WHERE consumed_set_id IS NULL
             AND avg_spine_mlb IS NOT NULL
             AND weight_cg IS NOT NULL
             AND quality <> 'JUNK'"""
    ).fetchall()
    assert [r["label"] for r in rows] == ["19-02"]


def test_shaft_quality_defaults_to_usable(db):
    batch_id = _insert_batch(db)
    db.execute("INSERT INTO shaft(batch_id, seq, label) VALUES (?, 1, '19-01')", (batch_id,))
    row = db.execute("SELECT quality FROM shaft WHERE batch_id = ?", (batch_id,)).fetchone()
    assert row["quality"] == "USABLE"


def test_shaft_quality_rejects_old_ratings_and_null(db):
    batch_id = _insert_batch(db)
    for bad_value in ("EXCELLENT", "OK"):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO shaft(batch_id, seq, label, quality) VALUES (?, 1, '19-01', ?)",
                (batch_id, bad_value),
            )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO shaft(batch_id, seq, label, quality) VALUES (?, 1, '19-01', NULL)",
            (batch_id,),
        )


def test_entry_pass_accepts_quality_rejects_old_straightness_value(db):
    batch_id = _insert_batch(db)
    db.execute("UPDATE batch SET entry_pass = 'quality' WHERE id = ?", (batch_id,))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE batch SET entry_pass = 'straightness' WHERE id = ?", (batch_id,))
