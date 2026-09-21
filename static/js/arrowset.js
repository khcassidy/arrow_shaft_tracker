// The Arrow Set page for one set's build. Reached two ways: the top-level
// Arrows tab's index (arrows.js) lists every set's build, and a built
// Set's own card (sets.js) carries the same "Build arrows" / "Open Arrow
// Set" link -- both land here, at #/sets/{id}/arrows.
//
// One flat table, one row per arrow, every field directly editable
// (commitOnBlur) -- no stage picker, no per-arrow panel, no matrix. The
// "Build defaults" header works exactly like a batch's diameter/wood:
// set it once, every arrow that still matches the *old* default takes
// the new one, and an arrow already edited away from the default is left
// alone (see repo_arrows.update_defaults for the exact rule this mirrors,
// repo_batches.update_batch).

import { api } from "./api.js";
import { formatWeightCg } from "./fmt.js";
import { FocusRing } from "./focusring.js";
import { attachColumnSort } from "./tablesort.js";
import { attachHoverTooltip } from "./tooltip.js";
import { commitOnBlur, commitOnChange, labeledInline, optionEl, optionLabel, pickableOptions } from "./ui.js";

const FLETCH_COUNTS = [2, 3, 4];

export async function renderArrowSet(root, setId) {
  const wrap = document.createElement("div");
  wrap.className = "view view-arrowset";

  const [set, catalogues] = await Promise.all([
    api.get(`api/sets/${setId}`),
    Promise.all(
      ["nock", "fletching", "point", "finish"].map((kind) => api.get(`api/lookups/${kind}`))
    ).then(([nocks, fletchings, points, finishes]) => ({ nocks, fletchings, points, finishes })),
  ]);

  const heading = document.createElement("h1");
  heading.textContent = `Arrow Set -- ${set.name}`;
  wrap.appendChild(heading);

  const meta = document.createElement("p");
  meta.className = "form-hint";
  meta.textContent = `${set.diameterLabel} / ${set.woodLabel} -- ${set.memberCount} shafts`;
  wrap.appendChild(meta);

  const backLink = document.createElement("a");
  backLink.href = "#/arrows";
  backLink.textContent = "← Back to Arrows";
  backLink.className = "arrowset-back-link";
  wrap.appendChild(backLink);

  const errorBox = document.createElement("div");
  errorBox.className = "form-error";
  wrap.appendChild(errorBox);

  const defaultsSection = buildDefaultsSection(set, catalogues, errorBox, (updated) => {
    renderGrid(updated.arrows);
  });
  wrap.appendChild(defaultsSection);

  const gridSection = document.createElement("div");
  gridSection.className = "config-section arrowset-grid-section";
  wrap.appendChild(gridSection);

  function renderGrid(arrows) {
    gridSection.innerHTML = "";
    if (arrows.length === 0) {
      gridSection.appendChild(buildStartBuildPrompt(setId, errorBox, (started) => renderGrid(started)));
      return;
    }
    // The stats panel and the grid's own per-row delta cells both read
    // the SAME `arrows` array, which commitArrowField keeps live in
    // place (see its own comment) -- so refreshing stats after a weight
    // commit is just re-reading numbers that are already current, no
    // extra fetch needed.
    const stats = buildStatsSection(arrows);
    gridSection.appendChild(buildArrowGrid(arrows, catalogues, errorBox, () => stats.refresh(arrows)));
    gridSection.appendChild(stats.section);
    gridSection.appendChild(buildCancelBuildControl(setId, arrows, errorBox, () => renderGrid([])));
  }

  const arrows = await api.get(`api/sets/${setId}/arrows`);
  renderGrid(arrows);

  root.appendChild(wrap);
}

// ---- build defaults header ----

function buildDefaultsSection(set, catalogues, errorBox, onDefaultsSaved) {
  const section = document.createElement("div");
  section.className = "config-section arrowset-defaults-section";

  const h2 = document.createElement("h2");
  h2.textContent = "Build defaults";
  section.appendChild(h2);

  const hint = document.createElement("p");
  hint.className = "form-hint";
  hint.textContent =
    "Applies to every arrow below that still matches the old default -- the same rule " +
    "a batch's own diameter/wood uses for its shafts. An arrow already edited on its own " +
    "row keeps its own value.";
  section.appendChild(hint);

  const row = document.createElement("div");
  row.className = "sets-picker-row";

  async function commitDefault(body) {
    errorBox.textContent = "";
    try {
      const updated = await api.patch(`api/sets/${set.id}/defaults`, body);
      onDefaultsSaved(updated);
    } catch (e) {
      errorBox.textContent = e.message || "Could not save default";
      throw e;
    }
  }

  function catalogueSelect(options, currentId, onCommit) {
    const select = document.createElement("select");
    for (const o of pickableOptions(options, currentId)) {
      select.appendChild(optionEl(o.id, optionLabel(o)));
    }
    select.value = String(currentId ?? 0);
    commitOnChange(select, { onCommit });
    return select;
  }

  const nockSelect = catalogueSelect(catalogues.nocks, set.defaultNockOptionId ?? 0, (value) =>
    commitDefault({ nockOptionId: Number(value) })
  );
  row.appendChild(labeledInline("Nock", nockSelect));

  const fletchingSelect = catalogueSelect(
    catalogues.fletchings,
    set.defaultFletchingOptionId ?? 0,
    (value) => commitDefault({ fletchingOptionId: Number(value) })
  );
  row.appendChild(labeledInline("Fletching", fletchingSelect));

  const fletchCountSelect = document.createElement("select");
  for (const n of FLETCH_COUNTS) fletchCountSelect.appendChild(optionEl(n, String(n)));
  fletchCountSelect.value = String(set.defaultFletchCount ?? 3);
  commitOnChange(fletchCountSelect, {
    onCommit: (value) => commitDefault({ fletchCount: Number(value) }),
  });
  row.appendChild(labeledInline("Fletch count", fletchCountSelect));

  const pointSelect = catalogueSelect(catalogues.points, set.defaultPointOptionId ?? 0, (value) =>
    commitDefault({ pointOptionId: Number(value) })
  );
  row.appendChild(labeledInline("Point", pointSelect));

  const finishSelect = catalogueSelect(catalogues.finishes, set.defaultFinishProductId ?? 0, (value) =>
    commitDefault({ finishProductId: Number(value) })
  );
  row.appendChild(labeledInline("Finish", finishSelect));

  const cutLengthInput = document.createElement("input");
  cutLengthInput.type = "text";
  cutLengthInput.inputMode = "decimal";
  cutLengthInput.placeholder = "in";
  cutLengthInput.value = set.defaultCutLength ?? "";
  commitOnBlur(cutLengthInput, {
    onCommit: (value) => commitDefault({ cutLength: value || null }),
  });
  row.appendChild(labeledInline("Cut length (in)", cutLengthInput));

  section.appendChild(row);
  return section;
}

// ---- start / cancel build ----

function buildStartBuildPrompt(setId, errorBox, onStarted) {
  const wrap = document.createElement("div");
  const p = document.createElement("p");
  p.className = "form-hint";
  p.textContent = "No arrows started yet for this set.";
  wrap.appendChild(p);

  const startBtn = document.createElement("button");
  startBtn.type = "button";
  startBtn.textContent = "Start build";
  startBtn.addEventListener("click", async () => {
    errorBox.textContent = "";
    try {
      const arrows = await api.post(`api/sets/${setId}/arrows:start`);
      onStarted(arrows);
    } catch (e) {
      errorBox.textContent = e.message || "Could not start build";
    }
  });
  wrap.appendChild(startBtn);
  return wrap;
}

function buildCancelBuildControl(setId, arrows, errorBox, onCancelled) {
  const wrap = document.createElement("div");
  const untouched = arrows.every(
    (a) => a.cutLength === null && a.afterFinishWeight === null && a.finishedWeight === null
  );
  if (!untouched) return wrap;

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "arrowset-cancel-btn";
  cancelBtn.textContent = "Cancel this build";
  cancelBtn.addEventListener("click", async () => {
    if (!confirm("Remove every arrow started for this set? The shafts stay in the set.")) return;
    errorBox.textContent = "";
    try {
      await api.del(`api/sets/${setId}/arrows`);
      onCancelled();
    } catch (e) {
      errorBox.textContent = e.message || "Could not cancel build";
    }
  });
  wrap.appendChild(cancelBtn);
  return wrap;
}

// ---- the flat grid ----

// [label, class, sortValue] -- sortValue is omitted for the two columns
// tablesort.js's attachColumnSort treats as unsortable position markers;
// every other column is click-to-sort, same as the Batches list. "#"
// sorts by [batchNo, seq], never the label string ("19-100" < "19-20" as
// text) -- the same rule shaftinfo.js's own "#" column follows.
const numOrNull = (s) => (s == null ? null : Number(s));

// A display string like "312.40" round-trips exactly through *100 -- it's
// always the server's own format_weight_cg output (2 dp), never raw
// archer input -- so this is safe where core/units.py's own float-vs-
// Decimal discipline would not be.
const cgFromDisplay = (s) => Math.round(Number(s) * 100);

// The one delta this page computes: how much weight the finish added.
// null unless both readings exist -- one blank operand makes a
// difference meaningless, not zero. Shared by the per-row cell and its
// own column's sortValue below, so display and sort order can never
// disagree about what a row's delta actually is.
function computeDeltaCg(arrow) {
  if (arrow.weightCg == null || arrow.afterFinishWeight == null) return null;
  return cgFromDisplay(arrow.afterFinishWeight) - arrow.weightCg;
}

// The whole build's own delta: bare shaft to finished arrow, so finish,
// fletching, point and nock all together -- as opposed to computeDeltaCg
// above, which stops at the finish coat alone. Used only by the Weight
// summary panel's own "Total Δ" row, not a grid column: with two
// per-arrow deltas already on screen (this one and the grid's own), a
// third column would invite reading them as three independent
// measurements rather than the same weight gain seen at two points along
// the build.
function computeTotalDeltaCg(arrow) {
  if (arrow.weightCg == null || arrow.finishedWeight == null) return null;
  return cgFromDisplay(arrow.finishedWeight) - arrow.weightCg;
}

const GRID_COLUMNS = [
  ["#", "col-arw-label", (a) => [a.batchNo, a.seq]],
  ["Nock", "col-arw-nock", (a) => a.nockLabel],
  ["Fletching", "col-arw-fletching", (a) => a.fletchingLabel],
  ["Cnt", "col-arw-fletchcount", (a) => a.fletchCount],
  ["Point", "col-arw-point", (a) => a.pointLabel],
  ["Finish", "col-arw-finish", (a) => a.finishLabel],
  ["Cut length (in)", "col-arw-cutlength", (a) => numOrNull(a.cutLength)],
  ["Bare wt (g)", "col-arw-bareweight", (a) => a.weightCg],
  ["After-finish wt (g)", "col-arw-afterfinish", (a) => numOrNull(a.afterFinishWeight)],
  ["Δ (g)", "col-arw-delta", (a) => computeDeltaCg(a)],
  ["Finished wt (g)", "col-arw-finished", (a) => numOrNull(a.finishedWeight)],
  ["Notes", "col-arw-notes", (a) => a.notes],
];

// The fields Tab/Enter visit, in column order (left to right) -- "#" and
// Bare wt are read-only, so they're not ring stops. Data entry moves DOWN
// one column through every arrow before moving on to the next column,
// the opposite of a plain HTML tab order (which goes across a row first)
// and the same shape entrygrid.js's own per-field mode uses.
const RING_FIELDS = [
  "nockOptionId",
  "fletchingOptionId",
  "fletchCount",
  "pointOptionId",
  "finishProductId",
  "cutLength",
  "afterFinishWeight",
  "finishedWeight",
  "notes",
];

// Built from arrows in their NATURAL (batchNo, seq) order, never the
// table's current sort order -- so clicking a column header to sort
// never changes what Enter/Tab does, the same guarantee entrygrid.js's
// own buildRing() gives against the entry grid's own sort.
function buildColumnRing(naturalOrderArrows) {
  return RING_FIELDS.flatMap((field) => naturalOrderArrows.map((a) => ({ seq: a.id, field })));
}

// ---- weight summary ----
// Min/max/delta/average across whichever arrows actually carry that
// reading -- a build is normally read part-way through, so "3 of 12
// weighed" is as important to show as the numbers themselves; a silent
// average over only the measured few, with no count shown, would read
// as if every arrow had been weighed.

const STATS_ROWS = [
  ["Bare wt (g)", (a) => a.weightCg],
  ["After-finish wt (g)", (a) => (a.afterFinishWeight == null ? null : cgFromDisplay(a.afterFinishWeight))],
  ["Finished wt (g)", (a) => (a.finishedWeight == null ? null : cgFromDisplay(a.finishedWeight))],
  // Bare -> finished, the whole build's own weight gain per arrow (see
  // computeTotalDeltaCg). This row's own Min/Max/Delta/Avg then say how
  // much that total gain itself varies across the set -- the same shape
  // every other row already has, just applied to a derived quantity
  // instead of a raw reading.
  ["Total Δ (g)", (a) => computeTotalDeltaCg(a)],
];

// delta here is this row's own spread (max - min) -- how consistent the
// set's shafts are for that one reading -- not computeDeltaCg's
// after-finish-minus-bare (that's the grid's own per-arrow Delta column,
// a different comparison: one arrow against itself, not the set's range).
function weightStat(arrows, getCg) {
  const values = arrows.map(getCg).filter((v) => v != null);
  if (values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const avg = Math.round(values.reduce((sum, v) => sum + v, 0) / values.length);
  return { count: values.length, min, max, delta: max - min, avg };
}

const STATS_COLUMNS = [
  ["", "col-stat-label"],
  ["Measured", "col-stat-n"],
  ["Min (g)", "col-stat-val"],
  ["Max (g)", "col-stat-val"],
  ["Delta (g)", "col-stat-val"],
  ["Avg (g)", "col-stat-val"],
];

function buildStatsSection(arrows) {
  const section = document.createElement("div");
  section.className = "config-section arrowset-stats-section";

  const h2 = document.createElement("h2");
  h2.textContent = "Weight summary";
  section.appendChild(h2);

  const table = document.createElement("table");
  table.className = "config-list arrowset-stats";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const [label, cls] of STATS_COLUMNS) {
    const th = document.createElement("th");
    th.className = cls;
    th.textContent = label;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  table.appendChild(tbody);
  section.appendChild(table);

  function refresh(currentArrows) {
    tbody.innerHTML = "";
    for (const [label, getCg] of STATS_ROWS) {
      const stat = weightStat(currentArrows, getCg);
      const tr = document.createElement("tr");

      const labelTd = document.createElement("td");
      labelTd.className = "col-stat-label";
      labelTd.textContent = label;
      tr.appendChild(labelTd);

      const nTd = document.createElement("td");
      nTd.className = "col-stat-n";
      nTd.textContent = `${stat ? stat.count : 0} / ${currentArrows.length}`;
      tr.appendChild(nTd);

      for (const value of stat ? [stat.min, stat.max, stat.delta, stat.avg] : [null, null, null, null]) {
        const td = document.createElement("td");
        td.className = "col-stat-val";
        td.textContent = value != null ? formatWeightCg(value) : "—";
        tr.appendChild(td);
      }

      tbody.appendChild(tr);
    }
  }

  refresh(arrows);
  return { section, refresh };
}

function buildArrowGrid(arrows, catalogues, errorBox, onWeightChanged) {
  const table = document.createElement("table");
  table.className = "config-list arrowset-grid";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const headerCells = [];
  for (const [label, cls] of GRID_COLUMNS) {
    const th = document.createElement("th");
    th.className = cls;
    th.textContent = label;
    headRow.appendChild(th);
    headerCells.push(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  table.appendChild(tbody);

  // Sorting REORDERS these existing <tr> elements (tbody.appendChild on
  // an attached node moves it) rather than rebuilding cells from
  // scratch, the same reason sets.js's candidate picker does the same
  // thing: every cell here is a live, already-committed input, and the
  // `arrows` array captured below is only ever the snapshot this grid
  // was first built from -- rebuilding from it after an edit would
  // silently revert that edit back to its pre-edit value on screen (the
  // server keeps the real value; only the display would be wrong).
  const rowsByArrowId = new Map();
  for (const arrow of arrows) {
    rowsByArrowId.set(arrow.id, buildRow(arrow, catalogues, errorBox, onWeightChanged));
  }

  function applySort() {
    for (const arrow of sorter.sortRows(arrows)) {
      tbody.appendChild(rowsByArrowId.get(arrow.id));
    }
  }

  const sorter = attachColumnSort(
    headerCells,
    GRID_COLUMNS.map(([, , sortValue]) => (sortValue ? { sortValue } : {})),
    applySort
  );
  applySort();

  attachHoverTooltip(table, "input[type=text]", (el) => el.value);

  // Enter/Tab move down the current column to the next arrow, wrapping
  // into the top of the next column once the last row is reached --
  // Shift+Enter/Shift+Tab reverse. At either end of the ring there is
  // nowhere left to go, so the field is blurred instead, which still
  // commits whatever was typed (the same reason entrygrid.js's own last
  // ring cell needs an explicit commit: it has nothing to advance to, so
  // it would otherwise never naturally blur).
  const ring = new FocusRing(table);
  ring.setRing(buildColumnRing(arrows));
  table.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" && ev.key !== "Tab") return;
    const cell = ev.target.closest("[data-seq]");
    if (!cell) return;
    ev.preventDefault();
    const seq = Number(cell.dataset.seq);
    const field = cell.dataset.field;
    const moved = ring.advance(seq, field, ev.shiftKey ? -1 : 1);
    if (!moved) cell.blur();
  });

  return table;
}

// Merges the server's response back into the row's own `arrow` object --
// not just the field that was actually sent. A row is built once and its
// cells' commit handlers, and the sort's own sortValue, all read this
// same object afterward (see buildArrowGrid's applySort), so it must
// stay the live source of truth for the row rather than a frozen
// snapshot from whenever the grid first loaded.
async function commitArrowField(arrow, body, errorBox) {
  errorBox.textContent = "";
  try {
    const updated = await api.patch(`api/arrows/${arrow.id}`, body);
    Object.assign(arrow, updated);
    return updated;
  } catch (e) {
    errorBox.textContent = e.message || "Could not save";
    throw e;
  }
}

function buildRow(arrow, catalogues, errorBox, onWeightChanged) {
  const tr = document.createElement("tr");

  const labelTd = document.createElement("td");
  labelTd.className = "col-arw-label";
  labelTd.textContent = `${arrow.batchNo}-${String(arrow.seq).padStart(2, "0")}`;
  tr.appendChild(labelTd);

  function catalogueCell(cls, options, currentId, key) {
    const td = document.createElement("td");
    td.className = cls;
    const select = document.createElement("select");
    select.dataset.seq = String(arrow.id);
    select.dataset.field = key;
    for (const o of pickableOptions(options, currentId)) {
      select.appendChild(optionEl(o.id, optionLabel(o)));
    }
    select.value = String(currentId);
    commitOnChange(select, {
      onCommit: (value) => commitArrowField(arrow, { [key]: Number(value) }, errorBox),
    });
    td.appendChild(select);
    return td;
  }

  tr.appendChild(catalogueCell("col-arw-nock", catalogues.nocks, arrow.nockOptionId, "nockOptionId"));
  tr.appendChild(
    catalogueCell("col-arw-fletching", catalogues.fletchings, arrow.fletchingOptionId, "fletchingOptionId")
  );

  const countTd = document.createElement("td");
  countTd.className = "col-arw-fletchcount";
  const countSelect = document.createElement("select");
  countSelect.dataset.seq = String(arrow.id);
  countSelect.dataset.field = "fletchCount";
  for (const n of FLETCH_COUNTS) countSelect.appendChild(optionEl(n, String(n)));
  countSelect.value = String(arrow.fletchCount);
  commitOnChange(countSelect, {
    onCommit: (value) => commitArrowField(arrow, { fletchCount: Number(value) }, errorBox),
  });
  countTd.appendChild(countSelect);
  tr.appendChild(countTd);

  tr.appendChild(catalogueCell("col-arw-point", catalogues.points, arrow.pointOptionId, "pointOptionId"));
  tr.appendChild(
    catalogueCell("col-arw-finish", catalogues.finishes, arrow.finishProductId, "finishProductId")
  );

  function textCell(cls, value, key, onCommitted) {
    const td = document.createElement("td");
    td.className = cls;
    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.value = value ?? "";
    input.dataset.seq = String(arrow.id);
    input.dataset.field = key;
    commitOnBlur(input, {
      onCommit: async (v) => {
        await commitArrowField(arrow, { [key]: v || null }, errorBox);
        onCommitted?.();
      },
    });
    td.appendChild(input);
    return td;
  }

  tr.appendChild(textCell("col-arw-cutlength", arrow.cutLength, "cutLength"));

  // Read-only: the shaft's own weight, measured on the Batches entry
  // grid before this shaft was ever part of an arrow build. Editing it
  // belongs there, not here -- this column exists so the two measured
  // weights that follow (after finish, finished) can be read against
  // it without a second tab open.
  const bareWeightTd = document.createElement("td");
  bareWeightTd.className = "col-arw-bareweight";
  bareWeightTd.textContent = arrow.weightCg != null ? formatWeightCg(arrow.weightCg) : "";
  tr.appendChild(bareWeightTd);

  // Also read-only: how much weight the finish added, recomputed (not
  // just re-read) every time After-finish weight is saved, from the
  // same computeDeltaCg its own column's sortValue uses.
  const deltaTd = document.createElement("td");
  deltaTd.className = "col-arw-delta";
  function refreshDelta() {
    const delta = computeDeltaCg(arrow);
    deltaTd.textContent = delta != null ? formatWeightCg(delta) : "";
  }
  refreshDelta();

  tr.appendChild(
    textCell("col-arw-afterfinish", arrow.afterFinishWeight, "afterFinishWeight", () => {
      refreshDelta();
      onWeightChanged?.();
    })
  );
  tr.appendChild(deltaTd);
  tr.appendChild(textCell("col-arw-finished", arrow.finishedWeight, "finishedWeight", onWeightChanged));

  const notesTd = document.createElement("td");
  notesTd.className = "col-arw-notes";
  const notesInput = document.createElement("input");
  notesInput.type = "text";
  notesInput.value = arrow.notes ?? "";
  notesInput.dataset.seq = String(arrow.id);
  notesInput.dataset.field = "notes";
  commitOnBlur(notesInput, {
    onCommit: (v) => commitArrowField(arrow, { notes: v || null }, errorBox),
  });
  notesTd.appendChild(notesInput);
  tr.appendChild(notesTd);

  return tr;
}
