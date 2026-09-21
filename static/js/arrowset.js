// The Arrow Set page: reached only from a built Set's own "Build arrows" /
// "Open Arrow Set" link (sets.js), never a standalone top-level tab -- the
// confirmed flow is Batches > Analysis > Sets > Arrow Set, one path in.
//
// One flat table, one row per arrow, every field directly editable
// (commitOnBlur) -- no stage picker, no per-arrow panel, no matrix. The
// "Build defaults" header works exactly like a batch's diameter/wood:
// set it once, every arrow that still matches the *old* default takes
// the new one, and an arrow already edited away from the default is left
// alone (see repo_arrows.update_defaults for the exact rule this mirrors,
// repo_batches.update_batch).

import { api } from "./api.js";
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
  backLink.href = "#/sets";
  backLink.textContent = "← Back to Sets";
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
    gridSection.appendChild(buildArrowGrid(arrows, catalogues, errorBox));
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

const GRID_COLUMNS = [
  ["#", "col-arw-label"],
  ["Nock", "col-arw-nock"],
  ["Fletching", "col-arw-fletching"],
  ["Cnt", "col-arw-fletchcount"],
  ["Point", "col-arw-point"],
  ["Finish", "col-arw-finish"],
  ["Cut length (in)", "col-arw-cutlength"],
  ["After-finish wt (g)", "col-arw-afterfinish"],
  ["Finished wt (g)", "col-arw-finished"],
  ["Notes", "col-arw-notes"],
];

function buildArrowGrid(arrows, catalogues, errorBox) {
  const table = document.createElement("table");
  table.className = "config-list arrowset-grid";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const [label, cls] of GRID_COLUMNS) {
    const th = document.createElement("th");
    th.className = cls;
    th.textContent = label;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const arrow of arrows) tbody.appendChild(buildRow(arrow, catalogues, errorBox));
  table.appendChild(tbody);

  attachHoverTooltip(table, "input[type=text]", (el) => el.value);
  return table;
}

async function commitArrowField(arrowId, body, errorBox) {
  errorBox.textContent = "";
  try {
    return await api.patch(`api/arrows/${arrowId}`, body);
  } catch (e) {
    errorBox.textContent = e.message || "Could not save";
    throw e;
  }
}

function buildRow(arrow, catalogues, errorBox) {
  const tr = document.createElement("tr");

  const labelTd = document.createElement("td");
  labelTd.className = "col-arw-label";
  labelTd.textContent = `${arrow.batchNo}-${String(arrow.seq).padStart(2, "0")}`;
  tr.appendChild(labelTd);

  function catalogueCell(cls, options, currentId, key) {
    const td = document.createElement("td");
    td.className = cls;
    const select = document.createElement("select");
    for (const o of pickableOptions(options, currentId)) {
      select.appendChild(optionEl(o.id, optionLabel(o)));
    }
    select.value = String(currentId);
    commitOnChange(select, {
      onCommit: (value) => commitArrowField(arrow.id, { [key]: Number(value) }, errorBox),
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
  for (const n of FLETCH_COUNTS) countSelect.appendChild(optionEl(n, String(n)));
  countSelect.value = String(arrow.fletchCount);
  commitOnChange(countSelect, {
    onCommit: (value) => commitArrowField(arrow.id, { fletchCount: Number(value) }, errorBox),
  });
  countTd.appendChild(countSelect);
  tr.appendChild(countTd);

  tr.appendChild(catalogueCell("col-arw-point", catalogues.points, arrow.pointOptionId, "pointOptionId"));
  tr.appendChild(
    catalogueCell("col-arw-finish", catalogues.finishes, arrow.finishProductId, "finishProductId")
  );

  function textCell(cls, value, key) {
    const td = document.createElement("td");
    td.className = cls;
    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.value = value ?? "";
    commitOnBlur(input, {
      onCommit: (v) => commitArrowField(arrow.id, { [key]: v || null }, errorBox),
    });
    td.appendChild(input);
    return td;
  }

  tr.appendChild(textCell("col-arw-cutlength", arrow.cutLength, "cutLength"));
  tr.appendChild(textCell("col-arw-afterfinish", arrow.afterFinishWeight, "afterFinishWeight"));
  tr.appendChild(textCell("col-arw-finished", arrow.finishedWeight, "finishedWeight"));

  const notesTd = document.createElement("td");
  notesTd.className = "col-arw-notes";
  const notesInput = document.createElement("input");
  notesInput.type = "text";
  notesInput.value = arrow.notes ?? "";
  commitOnBlur(notesInput, {
    onCommit: (v) => commitArrowField(arrow.id, { notes: v || null }, errorBox),
  });
  notesTd.appendChild(notesInput);
  tr.appendChild(notesTd);

  return tr;
}
