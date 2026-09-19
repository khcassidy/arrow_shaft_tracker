// buildRing() decides field traversal order for the two entry modes. Mode
// 2's second pass is literally a different ring over the same DOM -- no
// re-render, no refetch, no data loss when the archer switches.

// weightGr is deliberately not a ring stop: grams and grains are two
// live-linked views onto one value (see entrygrid.js's buildWeightCells),
// and an archer who always types grams never needs to tab through the
// grains cell to get to the next row. The grains cell stays fully present
// and editable by clicking into it directly -- it's just skipped by
// Enter/Tab traversal, not removed.
export function buildRing(rows, mode, pass) {
  if (mode === "per_shaft") {
    return rows.flatMap((r) => [
      { seq: r.seq, field: "spineA" },
      { seq: r.seq, field: "spineB" },
      { seq: r.seq, field: "weightG" },
    ]);
  }
  if (pass === "spine") {
    return rows.flatMap((r) => [
      { seq: r.seq, field: "spineA" },
      { seq: r.seq, field: "spineB" },
    ]);
  }
  if (pass === "weight") {
    return rows.map((r) => ({ seq: r.seq, field: "weightG" }));
  }
  // quality pass
  return rows.map((r) => ({ seq: r.seq, field: "quality" }));
}

export class FocusRing {
  constructor(container) {
    this.container = container;
    this.ring = [];
  }

  setRing(ring) {
    this.ring = ring;
  }

  cellFor(seq, field) {
    return this.container.querySelector(`[data-seq="${seq}"][data-field="${field}"]`);
  }

  indexOf(seq, field) {
    return this.ring.findIndex((r) => r.seq === seq && r.field === field);
  }

  focus(seq, field) {
    const el = this.cellFor(seq, field);
    if (!el) return false;
    el.focus();
    if (typeof el.select === "function") el.select();
    return true;
  }

  // delta is +1 (Enter/Tab) or -1 (Shift+Enter/Shift+Tab). Returns false
  // at either end of the ring, so the caller can simply do nothing rather
  // than wrap -- there is no "next batch" to fall into.
  advance(fromSeq, fromField, delta) {
    const idx = this.indexOf(fromSeq, fromField);
    if (idx === -1) return false;
    const next = idx + delta;
    if (next < 0 || next >= this.ring.length) return false;
    const target = this.ring[next];
    return this.focus(target.seq, target.field);
  }

  first() {
    if (this.ring.length === 0) return false;
    return this.focus(this.ring[0].seq, this.ring[0].field);
  }
}
