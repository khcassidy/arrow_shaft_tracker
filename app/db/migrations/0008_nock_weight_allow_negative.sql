-- Confirmed decision: a self nock is just another nock choice -- one
-- with a negative weight, since cutting it removes wood rather than
-- adding a component -- so it belongs in this catalogue like every
-- other nock, addressed the same way (arrow.nock_option_id), with no
-- separate flag and no second source of truth for "is this arrow
-- self-nocked".
--
-- Only nock_option changes -- fletching_option and point_option keep
-- their existing "> 0" floor. A fletching or a point is always a real,
-- separately-added piece of positive mass; a nock is the one component
-- that can instead be integral to the shaft, with wood cut AWAY to make
-- it, which is exactly what a negative weight represents. Zero is still
-- refused: a nock that adds or removes no mass at all isn't a
-- meaningful catalogue value to record.
--
-- SQLite has no ALTER COLUMN to relax a CHECK constraint in place, so
-- this is the same table-rebuild procedure 0005 (straightness -> quality)
-- already uses: PRAGMA foreign_keys is turned off for the duration
-- (arrow.nock_option_id and arrow_set.default_nock_option_id both
-- reference this table) and restored at the end.

PRAGMA foreign_keys = OFF;

CREATE TABLE nock_option_new (
  id                      INTEGER PRIMARY KEY,
  label                   TEXT    NOT NULL UNIQUE,
  default_unit_weight_cgr INTEGER CHECK (default_unit_weight_cgr IS NULL
                                         OR default_unit_weight_cgr <> 0),
  default_weight_text     TEXT,
  default_weight_unit     TEXT    CHECK (default_weight_unit IS NULL
                                         OR default_weight_unit IN ('g','gr')),
  notes                   TEXT,
  sort_order              INTEGER NOT NULL,
  is_active               INTEGER NOT NULL DEFAULT 1 CHECK (is_active  IN (0,1)),
  is_unknown              INTEGER NOT NULL DEFAULT 0 CHECK (is_unknown IN (0,1)),
  created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CONSTRAINT ck_nock_sentinel_id     CHECK (id <> 0 OR is_unknown = 1),
  CONSTRAINT ck_nock_sentinel_weight CHECK (is_unknown = 0 OR default_unit_weight_cgr IS NULL),
  CONSTRAINT ck_nock_weight_audit    CHECK (default_unit_weight_cgr IS NULL
                                       OR (default_weight_text IS NOT NULL
                                       AND default_weight_unit IS NOT NULL))
);

INSERT INTO nock_option_new
SELECT id, label, default_unit_weight_cgr, default_weight_text, default_weight_unit,
       notes, sort_order, is_active, is_unknown, created_at
FROM nock_option;

DROP TABLE nock_option;
ALTER TABLE nock_option_new RENAME TO nock_option;

CREATE INDEX        ix_nock_sort    ON nock_option(sort_order);
CREATE UNIQUE INDEX ux_nock_unknown ON nock_option(is_unknown) WHERE is_unknown = 1;

PRAGMA foreign_keys = ON;
