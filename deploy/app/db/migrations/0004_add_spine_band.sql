-- Configurable spine bands (30-35, 35-40, ... lb) and a batch's own
-- assigned target band. Purely additive: nominal_spine_label/min_lb/
-- max_lb stay exactly as they are -- CSV/JSON import and export still
-- read and write those directly. spine_band_id is a separate, new
-- concept: the single band a batch's shafts are expected to fall
-- within, used only by the new per-batch spine-check panel, never by
-- core/grouping.py's solver.

CREATE TABLE spine_band (
  id         INTEGER PRIMARY KEY,
  label      TEXT    NOT NULL UNIQUE,
  min_mlb    INTEGER NOT NULL,
  max_mlb    INTEGER NOT NULL,
  sort_order INTEGER NOT NULL,
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CHECK (min_mlb < max_mlb)
);
CREATE INDEX ix_spine_band_sort ON spine_band(sort_order);

INSERT INTO spine_band(label, min_mlb, max_mlb, sort_order) VALUES
  ('30-35', 30000, 35000, 1), ('35-40', 35000, 40000, 2),
  ('40-45', 40000, 45000, 3), ('45-50', 45000, 50000, 4),
  ('50-55', 50000, 55000, 5), ('55-60', 55000, 60000, 6),
  ('60-65', 60000, 65000, 7), ('65-70', 65000, 70000, 8);

ALTER TABLE batch ADD COLUMN spine_band_id INTEGER REFERENCES spine_band(id);

-- Backfill: existing batches whose free-text nominal range matches a
-- seeded band exactly (e.g. '55-60#' -> 55000-60000) start assigned,
-- rather than every batch starting unassigned.
UPDATE batch SET spine_band_id = (
  SELECT id FROM spine_band
   WHERE spine_band.min_mlb = batch.nominal_min_lb * 1000
     AND spine_band.max_mlb = batch.nominal_max_lb * 1000
)
WHERE nominal_min_lb IS NOT NULL AND nominal_max_lb IS NOT NULL;
