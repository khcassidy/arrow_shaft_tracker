-- A fourth arrow weight reading, taken once fletching is on but before
-- the point and nock go on -- between after_finish_weight_cg (finish
-- applied, nothing else yet) and finished_weight_cg (point and nock also
-- on). Same centigram minor unit, same "plain, directly-editable
-- measurement, NULL until typed" shape as the other two -- see
-- 0007_arrow_and_defaults.sql's own comment for why centigrams and why a
-- plain column rather than a stage-event log.
ALTER TABLE arrow ADD COLUMN after_fletching_weight_cg INTEGER
  CHECK (after_fletching_weight_cg IS NULL OR after_fletching_weight_cg > 0);
