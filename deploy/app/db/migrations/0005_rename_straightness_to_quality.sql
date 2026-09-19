-- "Straightness" becomes "Quality" everywhere, and the rating set shrinks
-- from EXCELLENT/OK/BAD/JUNK to Usable/Bad/Junk. Every shaft that isn't
-- already Bad or Junk -- including EXCELLENT, OK, and a blank/unrated
-- shaft -- becomes Usable (confirmed product decision), and the column
-- stops allowing blank going forward: every shaft has a rating from the
-- moment it is created, defaulting to Usable.
--
-- SQLite has no ALTER COLUMN for changing a CHECK constraint or adding
-- NOT NULL to an existing column, so this is the standard table-rebuild
-- procedure for both shaft (the column itself) and batch (entry_pass's
-- own CHECK also lists 'straightness' as one of its three pass values,
-- and leaving that one internal string unrenamed while everything else
-- says "quality" would be exactly the stray old terminology this project
-- avoided in 0002's grain->step rename). PRAGMA foreign_keys is turned
-- off for the duration -- SQLite's own documented guidance for this exact
-- scenario -- and restored before this script ends, since the connection
-- that runs migrations is reused afterward (tests reuse it directly;
-- production's own per-request connections each set foreign_keys back ON
-- independently in app/db/connection.py).

PRAGMA foreign_keys = OFF;

-- Dropped first, not last: shaft_entry_v's stored SQL text names "shaft"
-- literally, and SQLite re-validates every view's definition against the
-- live schema during a table rebuild, so leaving the view in place across
-- the DROP TABLE shaft below fails with "no such table: main.shaft" even
-- though shaft is about to exist again a few statements later.
DROP VIEW shaft_entry_v;

-- ---- shaft ----

CREATE TABLE shaft_new (
  id              INTEGER PRIMARY KEY,
  batch_id        INTEGER NOT NULL REFERENCES batch(id) ON DELETE RESTRICT,
  seq             INTEGER NOT NULL CHECK (seq >= 1),
  label           TEXT    NOT NULL UNIQUE,

  diameter_id     INTEGER NOT NULL DEFAULT 0 REFERENCES diameter_option(id),
  wood_id         INTEGER NOT NULL DEFAULT 0 REFERENCES wood_option(id),

  spine_count     INTEGER NOT NULL DEFAULT 0 CHECK (spine_count  >= 0),
  spine_sum_cp    INTEGER NOT NULL DEFAULT 0 CHECK (spine_sum_cp >= 0),
  spine_min_cp    INTEGER,
  spine_max_cp    INTEGER,
  avg_spine_mlb   INTEGER,
  spine_spread_cp INTEGER,

  weight_cg       INTEGER CHECK (weight_cg IS NULL OR weight_cg > 0),
  weight_text     TEXT,
  weight_unit     TEXT CHECK (weight_unit IS NULL OR weight_unit IN ('g','gr')),

  length_c_in     INTEGER CHECK (length_c_in IS NULL OR length_c_in > 0),

  quality         TEXT NOT NULL DEFAULT 'USABLE' CHECK (quality IN ('USABLE','BAD','JUNK')),
  notes           TEXT,

  consumed_set_id INTEGER REFERENCES arrow_set(id) ON DELETE SET NULL,
  consumed_at     TEXT,

  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  UNIQUE (batch_id, seq),
  CHECK (spine_count = 0 OR (avg_spine_mlb   IS NOT NULL
                         AND spine_min_cp    IS NOT NULL
                         AND spine_max_cp    IS NOT NULL
                         AND spine_spread_cp IS NOT NULL)),
  CHECK (spine_count = 0 OR spine_spread_cp = spine_max_cp - spine_min_cp),
  CHECK (spine_count <> 2 OR avg_spine_mlb = spine_sum_cp * 5),
  CHECK ((consumed_set_id IS NULL) = (consumed_at IS NULL)),
  CHECK (weight_cg IS NULL OR (weight_text IS NOT NULL AND weight_unit IS NOT NULL))
);

INSERT INTO shaft_new
SELECT id, batch_id, seq, label, diameter_id, wood_id,
       spine_count, spine_sum_cp, spine_min_cp, spine_max_cp, avg_spine_mlb, spine_spread_cp,
       weight_cg, weight_text, weight_unit,
       length_c_in,
       CASE WHEN straightness IN ('BAD','JUNK') THEN straightness ELSE 'USABLE' END,
       notes, consumed_set_id, consumed_at, created_at, updated_at
FROM shaft;

DROP TABLE shaft;
ALTER TABLE shaft_new RENAME TO shaft;

CREATE INDEX ix_shaft_batch_seq ON shaft(batch_id, seq);
CREATE INDEX ix_shaft_label     ON shaft(label);
CREATE INDEX ix_shaft_set       ON shaft(consumed_set_id);
CREATE INDEX ix_shaft_partition ON shaft(diameter_id, wood_id);

CREATE INDEX ix_shaft_analysis ON shaft(diameter_id, wood_id, avg_spine_mlb, weight_cg, id)
  WHERE consumed_set_id IS NULL
    AND avg_spine_mlb IS NOT NULL
    AND weight_cg     IS NOT NULL
    AND quality <> 'JUNK';

CREATE INDEX ix_shaft_weight   ON shaft(weight_cg);
CREATE INDEX ix_shaft_avgspine ON shaft(avg_spine_mlb);

CREATE TRIGGER trg_shaft_ai AFTER INSERT ON shaft
  BEGIN UPDATE app_meta SET int_value = int_value + 1 WHERE key = 'pool_version'; END;
CREATE TRIGGER trg_shaft_au AFTER UPDATE ON shaft
  BEGIN UPDATE app_meta SET int_value = int_value + 1 WHERE key = 'pool_version'; END;
CREATE TRIGGER trg_shaft_ad AFTER DELETE ON shaft
  BEGIN UPDATE app_meta SET int_value = int_value + 1 WHERE key = 'pool_version'; END;

-- ---- batch: entry_pass's 'straightness' value -> 'quality' ----

CREATE TABLE batch_new (
  id                  INTEGER PRIMARY KEY,
  batch_no            INTEGER NOT NULL UNIQUE,
  seq_width           INTEGER NOT NULL DEFAULT 2 CHECK (seq_width BETWEEN 2 AND 5),
  nominal_spine_label TEXT,
  nominal_min_lb      INTEGER,
  nominal_max_lb      INTEGER,
  diameter_id         INTEGER NOT NULL DEFAULT 0 REFERENCES diameter_option(id),
  wood_id             INTEGER NOT NULL DEFAULT 0 REFERENCES wood_option(id),
  shop_id             INTEGER REFERENCES shop(id),
  purchase_date       TEXT CHECK (purchase_date IS NULL
                        OR purchase_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  expected_count      INTEGER NOT NULL DEFAULT 0 CHECK (expected_count >= 0),
  description         TEXT,
  entry_mode          TEXT NOT NULL DEFAULT 'per_shaft'
                        CHECK (entry_mode IN ('per_shaft','per_field')),
  entry_pass          TEXT CHECK (entry_pass IS NULL OR entry_pass IN ('spine','weight','quality')),
  length_c_in         INTEGER CHECK (length_c_in IS NULL OR length_c_in > 0),
  spine_band_id       INTEGER REFERENCES spine_band(id),
  created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

INSERT INTO batch_new
SELECT id, batch_no, seq_width, nominal_spine_label, nominal_min_lb, nominal_max_lb,
       diameter_id, wood_id, shop_id, purchase_date, expected_count, description,
       entry_mode,
       CASE WHEN entry_pass = 'straightness' THEN 'quality' ELSE entry_pass END,
       length_c_in, spine_band_id, created_at, updated_at
FROM batch;

DROP TABLE batch;
ALTER TABLE batch_new RENAME TO batch;

-- ---- shaft_entry_v: straightness -> quality ----

CREATE VIEW shaft_entry_v AS
SELECT s.id, s.batch_id, b.batch_no, s.seq, s.label, s.diameter_id, s.wood_id,
       ra.value_cp AS spine_a_cp, ra.entered_text AS spine_a_text,
       rb.value_cp AS spine_b_cp, rb.entered_text AS spine_b_text,
       s.spine_count, s.spine_sum_cp, s.spine_min_cp, s.spine_max_cp,
       s.avg_spine_mlb, s.spine_spread_cp,
       s.weight_cg, s.weight_text, s.weight_unit,
       s.length_c_in, COALESCE(s.length_c_in, b.length_c_in) AS effective_length_c_in,
       s.quality, s.notes, s.consumed_set_id, s.consumed_at, s.updated_at
FROM shaft s
JOIN batch b ON b.id = s.batch_id
LEFT JOIN shaft_spine_reading ra ON ra.shaft_id = s.id AND ra.ordinal = 1
LEFT JOIN shaft_spine_reading rb ON rb.shaft_id = s.id AND rb.ordinal = 2;

PRAGMA foreign_keys = ON;
