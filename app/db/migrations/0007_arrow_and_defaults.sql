-- The arrow itself: one row per shaft of a matched set, once that set's
-- build has started. Purely additive -- shaft, batch and arrow_set's
-- existing columns are untouched.

-- shaft_id is a REAL foreign key, UNIQUE, with ON DELETE RESTRICT. That
-- single column replaces a separate frozen snapshot: the shaft stays the
-- one source of truth for spine, weight, wood, diameter and label, so an
-- arrow can never quietly disagree with the shaft it is. UNIQUE means one
-- shaft becomes at most one arrow, ever; RESTRICT means the shaft can't
-- be deleted while the arrow exists.
--
-- There is NO position column and NO arrow label -- the arrow IS the
-- shaft, so it uses shaft.label ('21-04'), already unique and indexed.
--
-- Every component reference (nock/fletching/point/finish) is NOT NULL
-- DEFAULT 0, the Unknown sentinel -- same convention diameter_id/wood_id
-- already use on shaft, so "not chosen yet" is a real, groupable value,
-- never NULL. ON DELETE RESTRICT on each one means a catalogue row still
-- referenced by an arrow can't be deleted -- surfaced as a 409 by the
-- existing generic FOREIGN KEY handler in app/api/errors.py, no extra
-- code needed on the delete side.
--
-- cut_length_c_in, after_finish_weight_cg and finished_weight_cg are
-- plain, directly-editable measurements -- typed into the one flat grid
-- once cut, once after finish is applied, and once fletching and the
-- point are on. cut_length_c_in is the arrow's OWN column and does not
-- write shaft.length_c_in: cutting an arrow to length is true of the
-- shaft, but shaft length is an input to the analysis engine, so writing
-- it from the arrow side could silently change a future grouping result.
-- The two weights are centigrams, the same minor unit shaft.weight_cg
-- already uses -- both come off the same gram scale, so there is no
-- reason to introduce a second weight unit for a measured value the way
-- default_unit_weight_cgr's CATALOGUED value needed one.
CREATE TABLE arrow (
  id                 INTEGER PRIMARY KEY,
  set_id             INTEGER NOT NULL REFERENCES arrow_set(id) ON DELETE RESTRICT,
  shaft_id           INTEGER NOT NULL UNIQUE REFERENCES shaft(id) ON DELETE RESTRICT,

  nock_option_id     INTEGER NOT NULL DEFAULT 0 REFERENCES nock_option(id) ON DELETE RESTRICT,
  fletching_option_id INTEGER NOT NULL DEFAULT 0 REFERENCES fletching_option(id) ON DELETE RESTRICT,
  fletch_count       INTEGER NOT NULL DEFAULT 3 CHECK (fletch_count IN (2,3,4)),
  point_option_id    INTEGER NOT NULL DEFAULT 0 REFERENCES point_option(id) ON DELETE RESTRICT,
  finish_product_id  INTEGER NOT NULL DEFAULT 0 REFERENCES finish_product(id) ON DELETE RESTRICT,

  cut_length_c_in         INTEGER CHECK (cut_length_c_in IS NULL OR cut_length_c_in > 0),
  after_finish_weight_cg  INTEGER CHECK (after_finish_weight_cg IS NULL OR after_finish_weight_cg > 0),
  finished_weight_cg      INTEGER CHECK (finished_weight_cg IS NULL OR finished_weight_cg > 0),
  notes                   TEXT,

  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX ix_arrow_set ON arrow(set_id, id);

-- A matched set's own defaults for the four catalogue choices plus cut
-- length -- "arrows work like batches": editing one of these cascades to
-- every arrow in the set still carrying the *old* default (see
-- repo_sets.update_defaults), the exact rule repo_batches.update_batch
-- already applies to a batch's diameter_id/wood_id cascading to its
-- shafts. NULL here means "no default chosen yet", a real, distinct
-- state from choosing the Unknown catalogue entry outright -- SQLite's
-- ALTER TABLE ADD COLUMN refuses a REFERENCES column with any non-NULL
-- default, so NULL is also the only default these columns could have
-- taken as an addition to an existing table.
ALTER TABLE arrow_set ADD COLUMN default_nock_option_id INTEGER
  REFERENCES nock_option(id) ON DELETE RESTRICT;
ALTER TABLE arrow_set ADD COLUMN default_fletching_option_id INTEGER
  REFERENCES fletching_option(id) ON DELETE RESTRICT;
ALTER TABLE arrow_set ADD COLUMN default_fletch_count INTEGER
  CHECK (default_fletch_count IS NULL OR default_fletch_count IN (2,3,4));
ALTER TABLE arrow_set ADD COLUMN default_point_option_id INTEGER
  REFERENCES point_option(id) ON DELETE RESTRICT;
ALTER TABLE arrow_set ADD COLUMN default_finish_product_id INTEGER
  REFERENCES finish_product(id) ON DELETE RESTRICT;
ALTER TABLE arrow_set ADD COLUMN default_cut_length_c_in INTEGER
  CHECK (default_cut_length_c_in IS NULL OR default_cut_length_c_in > 0);
