-- Arrow component catalogues: nocks, fletchings, points, finish products.
-- Purely additive -- nothing here touches shaft, batch, or arrow_set.

-- Four ordered lookup tables. Three carry a default weight; the fourth
-- does not. Kept as four tables, dispatched by the existing {kind}
-- router, exactly as diameter_option, wood_option and shop are. One
-- polymorphic table would let a "Danish oil" row be chosen as an arrow's
-- point, because a CHECK cannot reach across to the referencing column.
--
-- default_unit_weight_cgr is NULLABLE and that nullability is load-
-- bearing. NULL means "not catalogued yet", exactly as shaft.weight_cg
-- means "not measured yet". It does NOT mean zero.
--
-- "unit" weight, not "total": a point's unit weight is its weight
-- (count 1), but a fletching's unit weight is ONE feather, multiplied by
-- an arrow's fletch count later. The column name is the only defence
-- against a three-feather total typed in here.
CREATE TABLE nock_option (
  id                      INTEGER PRIMARY KEY,
  label                   TEXT    NOT NULL UNIQUE,
  default_unit_weight_cgr INTEGER CHECK (default_unit_weight_cgr IS NULL
                                         OR default_unit_weight_cgr > 0),
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
CREATE INDEX        ix_nock_sort    ON nock_option(sort_order);
CREATE UNIQUE INDEX ux_nock_unknown ON nock_option(is_unknown) WHERE is_unknown = 1;

CREATE TABLE fletching_option (
  id                      INTEGER PRIMARY KEY,
  label                   TEXT    NOT NULL UNIQUE,
  default_unit_weight_cgr INTEGER CHECK (default_unit_weight_cgr IS NULL
                                         OR default_unit_weight_cgr > 0),
  default_weight_text     TEXT,
  default_weight_unit     TEXT    CHECK (default_weight_unit IS NULL
                                         OR default_weight_unit IN ('g','gr')),
  notes                   TEXT,
  sort_order              INTEGER NOT NULL,
  is_active               INTEGER NOT NULL DEFAULT 1 CHECK (is_active  IN (0,1)),
  is_unknown              INTEGER NOT NULL DEFAULT 0 CHECK (is_unknown IN (0,1)),
  created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CONSTRAINT ck_fletching_sentinel_id     CHECK (id <> 0 OR is_unknown = 1),
  CONSTRAINT ck_fletching_sentinel_weight CHECK (is_unknown = 0 OR default_unit_weight_cgr IS NULL),
  CONSTRAINT ck_fletching_weight_audit    CHECK (default_unit_weight_cgr IS NULL
                                           OR (default_weight_text IS NOT NULL
                                           AND default_weight_unit IS NOT NULL))
);
CREATE INDEX        ix_fletching_sort    ON fletching_option(sort_order);
CREATE UNIQUE INDEX ux_fletching_unknown ON fletching_option(is_unknown) WHERE is_unknown = 1;

CREATE TABLE point_option (
  id                      INTEGER PRIMARY KEY,
  label                   TEXT    NOT NULL UNIQUE,
  default_unit_weight_cgr INTEGER CHECK (default_unit_weight_cgr IS NULL
                                         OR default_unit_weight_cgr > 0),
  default_weight_text     TEXT,
  default_weight_unit     TEXT    CHECK (default_weight_unit IS NULL
                                         OR default_weight_unit IN ('g','gr')),
  notes                   TEXT,
  sort_order              INTEGER NOT NULL,
  is_active               INTEGER NOT NULL DEFAULT 1 CHECK (is_active  IN (0,1)),
  is_unknown              INTEGER NOT NULL DEFAULT 0 CHECK (is_unknown IN (0,1)),
  created_at              TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CONSTRAINT ck_point_sentinel_id     CHECK (id <> 0 OR is_unknown = 1),
  CONSTRAINT ck_point_sentinel_weight CHECK (is_unknown = 0 OR default_unit_weight_cgr IS NULL),
  CONSTRAINT ck_point_weight_audit    CHECK (default_unit_weight_cgr IS NULL
                                       OR (default_weight_text IS NOT NULL
                                       AND default_weight_unit IS NOT NULL))
);
CREATE INDEX        ix_point_sort    ON point_option(sort_order);
CREATE UNIQUE INDEX ux_point_unknown ON point_option(is_unknown) WHERE is_unknown = 1;

-- finish_product carries NO weight columns, and that asymmetry is the
-- point. A coat of oil adds real weight, but not a cataloguable per-unit
-- weight: it depends on the coat, the wood and the wipe. A finish's
-- weight is only ever observable in the arrow's own measured after-
-- finish weight.
CREATE TABLE finish_product (
  id         INTEGER PRIMARY KEY,
  label      TEXT    NOT NULL UNIQUE,
  brand      TEXT,
  url        TEXT,
  notes      TEXT,
  sort_order INTEGER NOT NULL,
  is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active  IN (0,1)),
  is_unknown INTEGER NOT NULL DEFAULT 0 CHECK (is_unknown IN (0,1)),
  created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  CONSTRAINT ck_finish_sentinel_id CHECK (id <> 0 OR is_unknown = 1)
);
CREATE INDEX        ix_finish_sort    ON finish_product(sort_order);
CREATE UNIQUE INDEX ux_finish_unknown ON finish_product(is_unknown) WHERE is_unknown = 1;

-- Seeds. Nocks and fletchings ship with labels only and NULL weights,
-- because you have not weighed yours yet. Points ship with weights,
-- because for a point the weight IS the identity.
INSERT INTO nock_option(id,label,sort_order,is_unknown) VALUES
  (0,'Unknown',999,1),
  (1,'Bohning Classic 5/16"',1,0), (2,'Bohning Classic 11/32"',2,0),
  (3,'Bearpaw Bullet 5/16"',3,0),  (4,'Bearpaw Bullet 11/32"',4,0);

INSERT INTO fletching_option(id,label,sort_order,is_unknown) VALUES
  (0,'Unknown',999,1),
  (1,'4" Shield feather',1,0),    (2,'5" Shield feather',2,0),
  (3,'5" Parabolic feather',3,0), (4,'3" Parabolic feather',4,0),
  (5,'4" Plastic vane',5,0);

-- Centigrains are exact for a grain value: 100 gr = 10000 cgr.
INSERT INTO point_option(id,label,default_unit_weight_cgr,default_weight_text,
                         default_weight_unit,sort_order,is_unknown) VALUES
  (0,'Unknown',NULL,NULL,NULL,999,1),
  (1,'Field point 100 gr',10000,'100','gr',1,0),
  (2,'Field point 125 gr',12500,'125','gr',2,0),
  (3,'Field point 145 gr',14500,'145','gr',3,0),
  (4,'Field point 160 gr',16000,'160','gr',4,0),
  (5,'Bodkin 125 gr',     12500,'125','gr',5,0);

INSERT INTO finish_product(id,label,sort_order,is_unknown) VALUES
  (0,'Unknown',999,1),
  (1,'Danish oil',1,0), (2,'Tung oil',2,0), (3,'Spar varnish',3,0),
  (4,'Gasket lacquer',4,0), (5,'Wipe-on polyurethane',5,0);
