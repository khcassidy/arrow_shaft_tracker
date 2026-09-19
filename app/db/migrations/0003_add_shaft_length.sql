-- Shaft length, in centi-inches (1 in = 100), the same integer-minor-unit
-- convention as spine (cp) and weight (cg). batch.length_c_in is the
-- batch's default; shaft.length_c_in is a per-shaft override that stays
-- NULL until someone types one -- effective length is COALESCE'd in
-- shaft_entry_v below, so editing the batch default live-updates every
-- shaft that has never been overridden, with nothing to seed or cascade.
-- param_set.length_tol_c_in stays NULL on every existing row: it is an
-- optional third box-constraint dimension the solver only adds when a
-- param set actually sets it, so no existing analysis result changes.

ALTER TABLE batch ADD COLUMN length_c_in INTEGER
  CHECK (length_c_in IS NULL OR length_c_in > 0);

ALTER TABLE shaft ADD COLUMN length_c_in INTEGER
  CHECK (length_c_in IS NULL OR length_c_in > 0);

ALTER TABLE param_set ADD COLUMN length_tol_c_in INTEGER
  CHECK (length_tol_c_in IS NULL OR length_tol_c_in >= 0);

DROP VIEW shaft_entry_v;

CREATE VIEW shaft_entry_v AS
SELECT s.id, s.batch_id, b.batch_no, s.seq, s.label, s.diameter_id, s.wood_id,
       ra.value_cp AS spine_a_cp, ra.entered_text AS spine_a_text,
       rb.value_cp AS spine_b_cp, rb.entered_text AS spine_b_text,
       s.spine_count, s.spine_sum_cp, s.spine_min_cp, s.spine_max_cp,
       s.avg_spine_mlb, s.spine_spread_cp,
       s.weight_cg, s.weight_text, s.weight_unit,
       s.length_c_in, COALESCE(s.length_c_in, b.length_c_in) AS effective_length_c_in,
       s.straightness, s.notes, s.consumed_set_id, s.consumed_at, s.updated_at
FROM shaft s
JOIN batch b ON b.id = s.batch_id
LEFT JOIN shaft_spine_reading ra ON ra.shaft_id = s.id AND ra.ordinal = 1
LEFT JOIN shaft_spine_reading rb ON rb.shaft_id = s.id AND rb.ordinal = 2;
