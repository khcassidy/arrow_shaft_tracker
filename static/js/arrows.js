// The Arrows tab: an index over every set's arrow build, so there's a
// single place to see which builds exist without going through Sets
// first. Each row still opens the same #/sets/{id}/arrows page sets.js
// links to -- this tab adds a second way in, not a second page.

import { api } from "./api.js";

export async function renderArrowsList(root) {
  const wrap = document.createElement("div");
  wrap.className = "view view-arrows";

  const heading = document.createElement("h1");
  heading.textContent = "Arrows";
  wrap.appendChild(heading);

  const hint = document.createElement("p");
  hint.className = "form-hint";
  hint.textContent = "Every built set, and whether an arrow build has started for it.";
  wrap.appendChild(hint);

  const sets = await api.get("api/sets");
  const active = sets.filter((s) => !s.disbandedAt);

  if (active.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No sets built yet -- build one on the Sets tab first.";
    wrap.appendChild(empty);
    root.appendChild(wrap);
    return;
  }

  // [label, class] pairs, shared between the header row and each body
  // row -- app.css's global `table { table-layout: fixed }` takes column
  // widths from the table's FIRST row only, so a header cell and a body
  // cell in the same column must carry the same class or the column
  // collapses to zero width (see .config-list's own convention).
  const COLUMNS = [
    ["Set", "col-awi-name"],
    ["Diameter / Wood", "col-awi-partition"],
    ["Shafts", "col-awi-count"],
    ["Arrows", "col-awi-count"],
    ["", "col-awi-action"],
  ];

  const table = document.createElement("table");
  table.className = "config-list arrows-index-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const [label, cls] of COLUMNS) {
    const th = document.createElement("th");
    th.className = cls;
    th.textContent = label;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const set of active) {
    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.className = "col-awi-name";
    nameTd.textContent = set.name;
    tr.appendChild(nameTd);

    const partitionTd = document.createElement("td");
    partitionTd.className = "col-awi-partition";
    partitionTd.textContent = `${set.diameterLabel} / ${set.woodLabel}`;
    tr.appendChild(partitionTd);

    const membersTd = document.createElement("td");
    membersTd.className = "col-awi-count";
    membersTd.textContent = String(set.memberCount);
    tr.appendChild(membersTd);

    const arrowsTd = document.createElement("td");
    arrowsTd.className = "col-awi-count";
    arrowsTd.textContent = String(set.arrowCount);
    tr.appendChild(arrowsTd);

    const actionTd = document.createElement("td");
    actionTd.className = "col-awi-action";
    if (set.memberCount > 0) {
      const link = document.createElement("a");
      link.href = `#/sets/${set.id}/arrows`;
      link.textContent = set.arrowCount > 0 ? "Open Arrow Set" : "Build arrows";
      actionTd.appendChild(link);
    }
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);

  root.appendChild(wrap);
}
