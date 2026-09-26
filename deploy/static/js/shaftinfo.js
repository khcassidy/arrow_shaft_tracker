// One column definition for every table that lists individual shafts with
// their full measured detail: the Sets tab's candidate picker and its
// built-set member list, and the Analysis tab's group tables. A column
// added here is added everywhere at once, instead of drifting between
// three hand-copied column lists. Each column also carries a `sortValue`
// -- the raw comparable value, not the formatted display string -- so
// tablesort.js's shared click-to-sort can order rows numerically instead
// of alphabetizing "9.00" ahead of "10.00".

import {
  computeGpi,
  deriveWeightDisplay,
  formatFlag,
  formatGpi,
  formatLengthIn,
  formatSpineCp,
  formatSpineMlb,
  formatQuality,
} from "./fmt.js";

// true/false/null -> a 3-way ordering (worse, better, unknown) instead of
// comparing "OK"/"off"/"-" as text, which would sort neither sensibly nor
// consistently with what the flag actually means.
function flagSortValue(value) {
  if (value === null || value === undefined) return -1;
  return value ? 1 : 0;
}

// `key` becomes a `col-<key>` class on every cell of that column, which is
// how app.css gives the column its width. A class, not an nth-child rule,
// because the three tables that use this list don't agree on position:
// the candidate picker prepends a checkbox column and the built-set member
// list appends a Remove one, so column 2 here is column 3 there. Keyed by
// identity, one width rule holds all three tables to the same widths.
const COLUMNS = [
  // seq, not label: label is text ("19-100" < "19-20" as a string) and
  // batchNo,seq is the only order that's actually meaningful across
  // batches -- see core/labels.py.
  { key: "label", header: "#", get: (s) => s.label, sortValue: (s) => [s.batchNo, s.seq] },
  {
    key: "spine-a",
    header: "Spine A",
    get: (s) => s.spineAText || "",
    sortValue: (s) => s.spineACp,
    num: true,
  },
  {
    key: "spine-b",
    header: "Spine B",
    get: (s) => s.spineBText || "",
    sortValue: (s) => s.spineBCp,
    num: true,
  },
  {
    key: "avg",
    header: "Avg",
    get: (s) => formatSpineMlb(s.avgSpineMlb),
    sortValue: (s) => s.avgSpineMlb,
    num: true,
  },
  {
    key: "ab",
    header: "A-B",
    get: (s) => formatSpineCp(s.spineSpreadCp),
    sortValue: (s) => s.spineSpreadCp,
    num: true,
  },
  {
    key: "weight-g",
    header: "Weight (g)",
    get: (s) => deriveWeightDisplay(s).weightG,
    sortValue: (s) => s.weightCg,
    num: true,
  },
  {
    key: "weight-gr",
    header: "Weight (gr)",
    get: (s) => deriveWeightDisplay(s).weightGr,
    sortValue: (s) => s.weightCg,
    num: true,
  },
  {
    key: "length",
    header: "Length (in)",
    get: (s) => (s.effectiveLengthCIn != null ? formatLengthIn(s.effectiveLengthCIn) : ""),
    sortValue: (s) => s.effectiveLengthCIn,
    num: true,
  },
  {
    key: "gpi",
    header: "GPI",
    get: (s) => formatGpi(s.weightCg, s.effectiveLengthCIn),
    sortValue: (s) => computeGpi(s.weightCg, s.effectiveLengthCIn),
    num: true,
  },
  {
    key: "quality",
    header: "Quality",
    get: (s) => formatQuality(s.quality),
    sortValue: (s) => s.quality || "",
  },
  {
    key: "notes",
    header: "Notes",
    get: (s) => s.notes || "",
    sortValue: (s) => s.notes || "",
    notes: true,
  },
  {
    key: "ab-ok",
    header: "A-B OK",
    get: (s) => formatFlag(s.abConsistent, "OK", "off"),
    sortValue: (s) => flagSortValue(s.abConsistent),
  },
  {
    key: "in-spec",
    header: "In spec",
    get: (s) => formatFlag(s.inSpec, "yes", "no"),
    sortValue: (s) => flagSortValue(s.inSpec),
  },
];

export function shaftInfoColumns() {
  return COLUMNS;
}

export function shaftInfoHeaderCells() {
  return COLUMNS.map((col) => {
    const th = document.createElement("th");
    th.textContent = col.header;
    th.classList.add(`col-${col.key}`);
    if (col.num) th.classList.add("num-cell");
    if (col.notes) th.classList.add("notes-cell");
    return th;
  });
}

export function shaftInfoRowCells(shaft) {
  return COLUMNS.map((col) => {
    const td = document.createElement("td");
    td.textContent = col.get(shaft);
    td.classList.add(`col-${col.key}`);
    if (col.num) td.classList.add("num-cell");
    if (col.notes) td.classList.add("notes-cell");
    return td;
  });
}
