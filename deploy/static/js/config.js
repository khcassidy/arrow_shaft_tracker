// Configuration tab: the ordered lookup lists (diameter, wood, shop, and
// the four arrow-component catalogues), the spine bands, and the entry-
// validation rules. Every list mutation re-renders from the server's
// response rather than re-fetching, since create/rename/toggle/reorder/
// delete each already return the current list or row. Analysis parameter
// sets moved to analysis.js's own "Edit parameters" panel, so they can be
// tweaked and re-run without leaving that page.

import { api } from "./api.js";
import { displayFromMinor, minorFromInput } from "./fmt.js";
import { attachHoverTooltip } from "./tooltip.js";
import { commitOnBlur, field, numberInput, optionEl } from "./ui.js";

// A "select" extraField renders a <select> instead of an <input>, its
// options given as [{value, label}]. The three weighted catalogues share
// one field list -- nock, fletching and point are column-for-column
// identical server-side too, see repo_lookups.py.
const _WEIGHTED_CATALOGUE_FIELDS = [
  { key: "weightText", label: "Default weight", type: "text" },
  {
    key: "weightUnit",
    label: "Unit",
    type: "select",
    options: [
      { value: "", label: "–" },
      { value: "g", label: "g" },
      { value: "gr", label: "gr" },
    ],
  },
  { key: "notes", label: "Notes", type: "text" },
];

const LOOKUP_KINDS = {
  diameter: {
    title: "Diameter options",
    extraFields: [{ key: "sixtyFourths", label: "64ths", type: "number" }],
  },
  wood: { title: "Wood sorts", extraFields: [] },
  shop: {
    title: "Shaft Sources",
    extraFields: [
      { key: "url", label: "URL", type: "text" },
      { key: "notes", label: "Notes", type: "text" },
    ],
  },
  nock: { title: "Nocks", extraFields: _WEIGHTED_CATALOGUE_FIELDS },
  fletching: { title: "Fletchings", extraFields: _WEIGHTED_CATALOGUE_FIELDS },
  point: { title: "Points", extraFields: _WEIGHTED_CATALOGUE_FIELDS },
  finish: {
    title: "Finish products",
    extraFields: [
      { key: "brand", label: "Brand", type: "text" },
      { key: "url", label: "URL", type: "text" },
      { key: "notes", label: "Notes", type: "text" },
    ],
  },
};

export async function renderConfig(root) {
  const wrap = document.createElement("div");
  wrap.className = "view view-config";

  const heading = document.createElement("h1");
  heading.textContent = "Configuration";
  wrap.appendChild(heading);

  const hint = document.createElement("p");
  hint.className = "form-hint";
  hint.textContent =
    "Pull-downs elsewhere in the app follow this order, top to bottom -- " +
    "put what you use most at the top with ↑/↓.";
  wrap.appendChild(hint);

  for (const kind of Object.keys(LOOKUP_KINDS)) {
    wrap.appendChild(await buildLookupSection(kind));
  }

  wrap.appendChild(await buildSpineBandSection());
  wrap.appendChild(await buildEntryRulesSection());

  root.appendChild(wrap);
}

// A "select" extraField needs an actual <select>; every other type is a
// plain <input type={type}>. Shared by a lookup's own row and its add
// form, so the two never build the field two different ways.
function buildExtraFieldInput(field) {
  if (field.type === "select") {
    const select = document.createElement("select");
    for (const opt of field.options) select.appendChild(optionEl(opt.value, opt.label));
    return select;
  }
  const input = document.createElement("input");
  input.type = field.type;
  return input;
}

// ---- ordered lookup lists ----

async function buildLookupSection(kind) {
  const { title, extraFields } = LOOKUP_KINDS[kind];
  const section = document.createElement("div");
  section.className = "config-section";

  const h2 = document.createElement("h2");
  h2.textContent = title;
  section.appendChild(h2);

  const table = document.createElement("table");
  table.className = "config-list";
  const tbody = document.createElement("tbody");
  table.appendChild(tbody);
  section.appendChild(table);
  // A truncated value (see .col-cfg-label etc.'s text-overflow: ellipsis
  // in app.css) still needs some way to read the rest -- getText reads
  // the input's live, untruncated .value, same as entrygrid.js's own
  // notes-field tooltip.
  attachHoverTooltip(table, "input[type=text]", (el) => el.value);

  const errorBox = document.createElement("div");
  errorBox.className = "form-error";
  section.appendChild(errorBox);

  function renderRows(options) {
    const visible = options.filter((o) => !o.isUnknown);
    tbody.innerHTML = "";
    visible.forEach((option, index) => {
      tbody.appendChild(buildRow(option, index, visible));
    });
  }

  // Commits ONE field of one row, nothing else. Server-side PATCH already
  // treats an omitted key as untouched (exclude_unset), so sending just
  // {label: ...} here can never revert a value someone else set on
  // another field from another tab in the meantime.
  async function commitOneField(optionId, body) {
    errorBox.textContent = "";
    try {
      await api.patch(`api/lookups/${kind}/${optionId}`, body);
    } catch (e) {
      errorBox.textContent = e.message || "Could not save";
      throw e;
    }
  }

  function buildRow(option, index, visible) {
    const tr = document.createElement("tr");

    const moveTd = document.createElement("td");
    moveTd.className = "col-move";
    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.textContent = "↑";
    upBtn.disabled = index === 0;
    upBtn.addEventListener("click", () => reorder(visible, index, index - 1));
    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.textContent = "↓";
    downBtn.disabled = index === visible.length - 1;
    downBtn.addEventListener("click", () => reorder(visible, index, index + 1));
    moveTd.appendChild(upBtn);
    moveTd.appendChild(downBtn);
    tr.appendChild(moveTd);

    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.value = option.label;
    commitOnBlur(labelInput, { onCommit: (value) => commitOneField(option.id, { label: value }) });
    const labelTd = document.createElement("td");
    labelTd.className = "col-cfg-label";
    labelTd.appendChild(labelInput);
    tr.appendChild(labelTd);

    for (const extraField of extraFields) {
      const input = buildExtraFieldInput(extraField);
      input.value = option[extraField.key] ?? "";
      commitOnBlur(input, {
        onCommit: (value) => {
          const body = {
            [extraField.key]:
              extraField.type === "number" ? (value ? Number(value) : null) : value || null,
          };
          return commitOneField(option.id, body);
        },
      });
      const td = document.createElement("td");
      td.className = `col-cfg-${extraField.key}`;
      td.appendChild(input);
      tr.appendChild(td);
    }

    const activeTd = document.createElement("td");
    activeTd.className = "col-cfg-active";
    const activeCheckbox = document.createElement("input");
    activeCheckbox.type = "checkbox";
    activeCheckbox.checked = option.isActive;
    activeCheckbox.addEventListener("change", async () => {
      try {
        await commitOneField(option.id, { isActive: activeCheckbox.checked });
      } catch {
        activeCheckbox.checked = !activeCheckbox.checked;
      }
    });
    activeTd.appendChild(activeCheckbox);
    tr.appendChild(activeTd);

    const deleteTd = document.createElement("td");
    deleteTd.className = "col-cfg-delete";
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete "${option.label}"? This cannot be undone.`)) return;
      errorBox.textContent = "";
      try {
        await api.del(`api/lookups/${kind}/${option.id}`);
        renderRows(await api.get(`api/lookups/${kind}`));
      } catch (e) {
        errorBox.textContent = e.message || "Could not delete";
      }
    });
    deleteTd.appendChild(deleteBtn);
    tr.appendChild(deleteTd);

    return tr;
  }

  async function reorder(visible, fromIndex, toIndex) {
    const ids = visible.map((o) => o.id);
    [ids[fromIndex], ids[toIndex]] = [ids[toIndex], ids[fromIndex]];
    errorBox.textContent = "";
    try {
      const updated = await api.put(`api/lookups/${kind}/order`, { ids });
      renderRows(updated);
    } catch (e) {
      errorBox.textContent = e.message || "Could not reorder";
    }
  }

  const initial = await api.get(`api/lookups/${kind}`);
  renderRows(initial);

  section.appendChild(buildAddForm(kind, extraFields, errorBox, renderRows));
  return section;
}

function buildAddForm(kind, extraFields, errorBox, renderRows) {
  const form = document.createElement("form");
  form.className = "config-add-form";

  const labelInput = document.createElement("input");
  labelInput.type = "text";
  labelInput.placeholder = "New label";
  labelInput.required = true;
  form.appendChild(labelInput);

  const extraInputs = {};
  for (const field of extraFields) {
    const input = buildExtraFieldInput(field);
    if (field.type !== "select") input.placeholder = field.label;
    extraInputs[field.key] = input;
    form.appendChild(input);
  }

  const addBtn = document.createElement("button");
  addBtn.type = "submit";
  addBtn.textContent = "Add";
  form.appendChild(addBtn);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    errorBox.textContent = "";
    const body = { label: labelInput.value };
    for (const field of extraFields) {
      const raw = extraInputs[field.key].value;
      body[field.key] = field.type === "number" ? (raw ? Number(raw) : null) : raw || null;
    }
    try {
      await api.post(`api/lookups/${kind}`, body);
      const updated = await api.get(`api/lookups/${kind}`);
      renderRows(updated);
      form.reset();
    } catch (e) {
      errorBox.textContent = e.message || "Could not add";
    }
  });

  return form;
}

// ---- spine bands ----
// A separate section, not a fourth LOOKUP_KINDS entry: a band's real
// fields are a numeric (min, max) pair, not a typed label, so it doesn't
// fit buildLookupSection's single-label-input row shape.

async function buildSpineBandSection() {
  const section = document.createElement("div");
  section.className = "config-section";

  const h2 = document.createElement("h2");
  h2.textContent = "Spine bands";
  section.appendChild(h2);

  const hint = document.createElement("p");
  hint.className = "form-hint";
  hint.textContent =
    "The bands a batch's own target spine can be assigned to, on that batch's page.";
  section.appendChild(hint);

  const table = document.createElement("table");
  table.className = "config-list";
  const tbody = document.createElement("tbody");
  table.appendChild(tbody);
  section.appendChild(table);

  const errorBox = document.createElement("div");
  errorBox.className = "form-error";
  section.appendChild(errorBox);

  async function commitOneField(bandId, body) {
    errorBox.textContent = "";
    try {
      return await api.patch(`api/spine-bands/${bandId}`, body);
    } catch (e) {
      errorBox.textContent = e.message || "Could not save";
      throw e;
    }
  }

  function renderRows(bands) {
    tbody.innerHTML = "";
    bands.forEach((band, index) => tbody.appendChild(buildRow(band, index, bands)));
  }

  function buildRow(band, index, bands) {
    const tr = document.createElement("tr");

    const moveTd = document.createElement("td");
    moveTd.className = "col-move";
    const upBtn = document.createElement("button");
    upBtn.type = "button";
    upBtn.textContent = "↑";
    upBtn.disabled = index === 0;
    upBtn.addEventListener("click", () => reorder(bands, index, index - 1));
    const downBtn = document.createElement("button");
    downBtn.type = "button";
    downBtn.textContent = "↓";
    downBtn.disabled = index === bands.length - 1;
    downBtn.addEventListener("click", () => reorder(bands, index, index + 1));
    moveTd.appendChild(upBtn);
    moveTd.appendChild(downBtn);
    tr.appendChild(moveTd);

    // A relabel from either bound comes back on the SAME response --
    // refreshing just this one row's other input (not a full renderRows)
    // keeps that bound's own in-progress edit, if any, from being
    // clobbered by a re-render mid-commit.
    const minInput = document.createElement("input");
    minInput.type = "number";
    minInput.step = "any";
    minInput.value = band.minMlb / 1000;
    commitOnBlur(minInput, {
      onCommit: async (value) => {
        const updated = await commitOneField(band.id, { minLb: value });
        maxInput.value = updated.maxMlb / 1000;
      },
    });
    const minTd = document.createElement("td");
    minTd.className = "col-cfg-band";
    minTd.appendChild(minInput);
    tr.appendChild(minTd);

    const maxInput = document.createElement("input");
    maxInput.type = "number";
    maxInput.step = "any";
    maxInput.value = band.maxMlb / 1000;
    commitOnBlur(maxInput, {
      onCommit: async (value) => {
        const updated = await commitOneField(band.id, { maxLb: value });
        minInput.value = updated.minMlb / 1000;
      },
    });
    const maxTd = document.createElement("td");
    maxTd.className = "col-cfg-band";
    maxTd.appendChild(maxInput);
    tr.appendChild(maxTd);

    const activeTd = document.createElement("td");
    activeTd.className = "col-cfg-active";
    const activeCheckbox = document.createElement("input");
    activeCheckbox.type = "checkbox";
    activeCheckbox.checked = band.isActive;
    activeCheckbox.addEventListener("change", async () => {
      try {
        await commitOneField(band.id, { isActive: activeCheckbox.checked });
      } catch {
        activeCheckbox.checked = !activeCheckbox.checked;
      }
    });
    activeTd.appendChild(activeCheckbox);
    tr.appendChild(activeTd);

    const deleteTd = document.createElement("td");
    deleteTd.className = "col-cfg-delete";
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete the "${band.label}" band?`)) return;
      errorBox.textContent = "";
      try {
        await api.del(`api/spine-bands/${band.id}`);
        renderRows(await api.get("api/spine-bands"));
      } catch (e) {
        errorBox.textContent = e.message || "Could not delete";
      }
    });
    deleteTd.appendChild(deleteBtn);
    tr.appendChild(deleteTd);

    return tr;
  }

  async function reorder(bands, fromIndex, toIndex) {
    const ids = bands.map((b) => b.id);
    [ids[fromIndex], ids[toIndex]] = [ids[toIndex], ids[fromIndex]];
    errorBox.textContent = "";
    try {
      const updated = await api.put("api/spine-bands/order", { ids });
      renderRows(updated);
    } catch (e) {
      errorBox.textContent = e.message || "Could not reorder";
    }
  }

  const initial = await api.get("api/spine-bands");
  renderRows(initial);

  const form = document.createElement("form");
  form.className = "config-add-form";

  const minInput = document.createElement("input");
  minInput.type = "number";
  minInput.step = "any";
  minInput.placeholder = "Min (lb)";
  minInput.required = true;
  form.appendChild(minInput);

  const maxInput = document.createElement("input");
  maxInput.type = "number";
  maxInput.step = "any";
  maxInput.placeholder = "Max (lb)";
  maxInput.required = true;
  form.appendChild(maxInput);

  const addBtn = document.createElement("button");
  addBtn.type = "submit";
  addBtn.textContent = "Add";
  form.appendChild(addBtn);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    errorBox.textContent = "";
    try {
      await api.post("api/spine-bands", { minLb: minInput.value, maxLb: maxInput.value });
      const updated = await api.get("api/spine-bands");
      renderRows(updated);
      form.reset();
    } catch (e) {
      errorBox.textContent = e.message || "Could not add";
    }
  });

  section.appendChild(form);
  return section;
}

// ---- entry validation rules ----

async function buildEntryRulesSection() {
  const section = document.createElement("div");
  section.className = "config-section";
  const h2 = document.createElement("h2");
  h2.textContent = "Entry validation rules";
  section.appendChild(h2);

  const hint = document.createElement("p");
  hint.className = "form-hint";
  hint.textContent =
    "The bands the entry grid uses for step warnings and plausible-range checks.";
  section.appendChild(hint);

  const rules = await api.get("api/config/entry-rules");

  const form = document.createElement("form");
  form.className = "config-params-form";

  const spineStep = numberInput(displayFromMinor(rules.spineStepCp, 2));
  field(form, "Spine step (lb)", spineStep);
  const weightStep = numberInput(displayFromMinor(rules.weightStepCg, 2));
  field(form, "Weight step (g)", weightStep);

  const spineHardMin = numberInput(displayFromMinor(rules.spineHardMinCp, 2));
  field(form, "Spine hard minimum (lb)", spineHardMin);
  const spineHardMax = numberInput(displayFromMinor(rules.spineHardMaxCp, 2));
  field(form, "Spine hard maximum (lb)", spineHardMax);
  const spineWarnMin = numberInput(displayFromMinor(rules.spineWarnMinCp, 2));
  field(form, "Spine warn below (lb)", spineWarnMin);
  const spineWarnMax = numberInput(displayFromMinor(rules.spineWarnMaxCp, 2));
  field(form, "Spine warn above (lb)", spineWarnMax);

  const weightHardMin = numberInput(displayFromMinor(rules.weightHardMinCg, 2));
  field(form, "Weight hard minimum (g)", weightHardMin);
  const weightHardMax = numberInput(displayFromMinor(rules.weightHardMaxCg, 2));
  field(form, "Weight hard maximum (g)", weightHardMax);
  const weightWarnMin = numberInput(displayFromMinor(rules.weightWarnMinCg, 2));
  field(form, "Weight warn below (g)", weightWarnMin);
  const weightWarnMax = numberInput(displayFromMinor(rules.weightWarnMaxCg, 2));
  field(form, "Weight warn above (g)", weightWarnMax);

  const batchOutlierSpine = numberInput(displayFromMinor(rules.batchOutlierSpineCp, 2));
  field(form, "Batch outlier: spine distance from median (lb)", batchOutlierSpine);
  const batchOutlierWeight = numberInput(displayFromMinor(rules.batchOutlierWeightCg, 2));
  field(form, "Batch outlier: weight distance from median (g)", batchOutlierWeight);

  const grainsPerGram = document.createElement("input");
  grainsPerGram.type = "text";
  grainsPerGram.value = rules.grainsPerGram;
  field(form, "Grains per gram", grainsPerGram);

  const saveBtn = document.createElement("button");
  saveBtn.type = "submit";
  saveBtn.textContent = "Save";
  form.appendChild(saveBtn);

  const errorBox = document.createElement("div");
  errorBox.className = "form-error";
  form.appendChild(errorBox);

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    errorBox.textContent = "";
    try {
      await api.patch("api/config/entry-rules", {
        spineStepCp: minorFromInput(spineStep.value, 2),
        weightStepCg: minorFromInput(weightStep.value, 2),
        spineHardMinCp: minorFromInput(spineHardMin.value, 2),
        spineHardMaxCp: minorFromInput(spineHardMax.value, 2),
        spineWarnMinCp: minorFromInput(spineWarnMin.value, 2),
        spineWarnMaxCp: minorFromInput(spineWarnMax.value, 2),
        weightHardMinCg: minorFromInput(weightHardMin.value, 2),
        weightHardMaxCg: minorFromInput(weightHardMax.value, 2),
        weightWarnMinCg: minorFromInput(weightWarnMin.value, 2),
        weightWarnMaxCg: minorFromInput(weightWarnMax.value, 2),
        batchOutlierSpineCp: minorFromInput(batchOutlierSpine.value, 2),
        batchOutlierWeightCg: minorFromInput(batchOutlierWeight.value, 2),
        grainsPerGram: grainsPerGram.value,
      });
    } catch (e) {
      errorBox.textContent = e.message || "Could not save";
    }
  });

  section.appendChild(form);
  return section;
}
