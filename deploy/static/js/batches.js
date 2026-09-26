// Batches tab: list (sortable by every column), and the create-batch form.
// Diameter and wood pull-downs are rendered in the order the server
// returns them (sort_order, not alphabetical) -- see repo_lookups.py.

import { api } from "./api.js";
import { formatLengthIn } from "./fmt.js";
import { buildExportLinks, buildImportForm } from "./importexport.js";
import { attachColumnSort } from "./tablesort.js";
import { field, optionEl } from "./ui.js";

export async function loadLookup(kind) {
  return api.get(`api/lookups/${kind}`);
}

export async function loadSpineBands() {
  return api.get("api/spine-bands");
}

// Resolves a batch's spine-range display text: the assigned band's label
// when spineBandId is set, else the legacy free-text nominalSpineLabel
// (older/imported batches never got a band assigned) -- same fallback
// entrygrid.js's updateTitle() uses.
export function spineRangeLabel(batch, spineBands) {
  const band = spineBands.find((b) => b.id === batch.spineBandId);
  return band ? band.label : batch.nominalSpineLabel || "";
}

export async function renderBatchList(root) {
  const [batches, diameters, woods, shops, spineBands] = await Promise.all([
    api.get("api/batches"),
    loadLookup("diameter"),
    loadLookup("wood"),
    loadLookup("shop"),
    loadSpineBands(),
  ]);

  const wrap = document.createElement("div");
  wrap.className = "view view-batches";

  const heading = document.createElement("h1");
  heading.textContent = "Batches";
  wrap.appendChild(heading);

  wrap.appendChild(buildBatchTable(batches, diameters, woods, shops, spineBands));
  wrap.appendChild(buildCreateForm(diameters, woods));
  wrap.appendChild(buildExportLinks());
  wrap.appendChild(buildImportForm());

  root.appendChild(wrap);
}

// Each column knows how to read a comparable value off a batch row --
// the same function serves as both the cell's display text and its sort
// key here, since a batch row's raw values (numbers, short labels) are
// already exactly what should be compared, unlike shaftinfo.js's tables
// where a formatted display string and its sort value can differ.
function batchColumns(diameters, woods, shops, spineBands) {
  const diameterLabel = (b) => diameters.find((d) => d.id === b.diameterId)?.label || "Unknown";
  const woodLabel = (b) => woods.find((w) => w.id === b.woodId)?.label || "Unknown";
  const shopLabel = (b) => shops.find((s) => s.id === b.shopId)?.label || "";

  return [
    { label: "Batch", get: (b) => b.batchNo },
    { label: "Spine range", get: (b) => spineRangeLabel(b, spineBands) },
    { label: "Diameter", get: diameterLabel },
    { label: "Wood", get: woodLabel },
    {
      label: "Length (in)",
      get: (b) => (b.lengthCIn != null ? formatLengthIn(b.lengthCIn) : ""),
      sortValue: (b) => b.lengthCIn,
    },
    { label: "Shaft Source", get: shopLabel },
    { label: "Purchased", get: (b) => b.purchaseDate || "" },
    { label: "Shafts", get: (b) => b.expectedCount },
  ];
}

function buildBatchTable(batches, diameters, woods, shops, spineBands) {
  const columns = batchColumns(diameters, woods, shops, spineBands);
  const table = document.createElement("table");
  table.className = "batch-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const headerCells = [];
  for (const column of columns) {
    const th = document.createElement("th");
    th.textContent = column.label;
    headRow.appendChild(th);
    headerCells.push(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  table.appendChild(tbody);

  const emptyState = document.createElement("p");
  emptyState.className = "empty-state";
  emptyState.textContent = "No batches yet. Create one below.";
  emptyState.hidden = batches.length > 0;

  function renderRows() {
    tbody.innerHTML = "";
    for (const b of sorter.sortRows(batches)) {
      const tr = document.createElement("tr");
      tr.className = "batch-row";
      for (const col of columns) {
        const td = document.createElement("td");
        td.textContent = String(col.get(b));
        tr.appendChild(td);
      }
      tr.addEventListener("click", () => {
        location.hash = `#/batches/${b.id}`;
      });
      tbody.appendChild(tr);
    }
  }

  const sorter = attachColumnSort(
    headerCells,
    columns.map((c) => ({ sortValue: c.sortValue || c.get })),
    renderRows
  );

  renderRows();
  table.after(emptyState);
  return table;
}

function buildCreateForm(diameters, woods) {
  const form = document.createElement("form");
  form.className = "batch-create-form";

  const h2 = document.createElement("h2");
  h2.textContent = "New batch";
  form.appendChild(h2);

  const hint = document.createElement("p");
  hint.className = "form-hint";
  hint.textContent =
    "Set diameter and wood now: each shaft is created with these values, and " +
    "editing them later on the batch's own page changes the batch record only, " +
    "not its existing shafts. Spine range, shaft source, purchase date, and " +
    "comments are set on the batch's own page after it's created.";
  form.appendChild(hint);

  const batchNo = document.createElement("input");
  batchNo.type = "number";
  batchNo.required = true;
  field(form, "Batch #", batchNo);

  const expectedCount = document.createElement("input");
  expectedCount.type = "number";
  expectedCount.min = "1";
  expectedCount.required = true;
  field(form, "Number of shafts", expectedCount);

  const diameterSelect = document.createElement("select");
  for (const d of diameters) diameterSelect.appendChild(optionEl(d.id, d.label));
  field(form, "Diameter", diameterSelect);

  const woodSelect = document.createElement("select");
  for (const w of woods) woodSelect.appendChild(optionEl(w.id, w.label));
  field(form, "Wood sort", woodSelect);

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Create batch";
  form.appendChild(submit);

  const errorBox = document.createElement("div");
  errorBox.className = "form-error";
  form.appendChild(errorBox);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    errorBox.textContent = "";
    try {
      const batch = await api.post("api/batches", {
        batchNo: Number(batchNo.value),
        expectedCount: Number(expectedCount.value),
        diameterId: Number(diameterSelect.value),
        woodId: Number(woodSelect.value),
      });
      location.hash = `#/batches/${batch.id}`;
    } catch (e) {
      errorBox.textContent = e.message || "Could not create batch";
    }
  });

  return form;
}
