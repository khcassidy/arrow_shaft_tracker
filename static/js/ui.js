// Pure DOM builders shared by every view module. This file builds DOM and
// nothing else -- no fetch, no app state, no import except fmt.js -- so it
// stays testable against a bare DOM with no server.
//
// Each export here retired a real duplication that existed across the view
// modules before this file: field() was copied verbatim in four files,
// optionEl() in three (with entrygrid.js importing its copy from
// batches.js -- a grid depending on a list view, exactly the coupling this
// file exists to prevent), labeledInline() in two, numberInput() in two,
// and decimalInput()'s four-line "type=text; inputMode=decimal;
// autocomplete=off; spellcheck=false" incantation appeared five times
// inside entrygrid.js alone.

export function field(form, labelText, inputEl, { span2 = false } = {}) {
  const label = document.createElement("label");
  if (span2) label.className = "span-2";
  label.appendChild(document.createTextNode(labelText));
  label.appendChild(inputEl);
  form.appendChild(label);
  return inputEl;
}

export function optionEl(value, label) {
  const opt = document.createElement("option");
  opt.value = String(value);
  opt.textContent = label;
  return opt;
}

export function labeledInline(labelText, inputEl) {
  const label = document.createElement("label");
  label.className = "sets-inline-label";
  label.appendChild(document.createTextNode(labelText));
  label.appendChild(inputEl);
  return label;
}

export function numberInput(value, { step = "any", min, max } = {}) {
  const input = document.createElement("input");
  input.type = "number";
  input.step = step;
  if (min !== undefined) input.min = min;
  if (max !== undefined) input.max = max;
  input.value = value;
  return input;
}

// Every numeric bench input must set inputMode="decimal" for the mobile
// keyboard to show a decimal pad -- this helper is what guarantees it
// instead of hoping every call site remembers all four attributes.
export function decimalInput(value, { placeholder } = {}) {
  const input = document.createElement("input");
  input.type = "text";
  input.inputMode = "decimal";
  input.autocomplete = "off";
  input.spellcheck = false;
  input.value = value;
  if (placeholder !== undefined) input.placeholder = placeholder;
  return input;
}

// onFirstOpen fires once, on the first time the block is expanded -- for a
// panel whose content is worth fetching only if someone actually looks.
export function detailsBlock(summaryText, { open = false, onFirstOpen } = {}) {
  const details = document.createElement("details");
  details.open = open;
  const summary = document.createElement("summary");
  summary.textContent = summaryText;
  details.appendChild(summary);
  if (onFirstOpen) {
    let loaded = false;
    details.addEventListener("toggle", async () => {
      if (!details.open || loaded) return;
      loaded = true;
      await onFirstOpen();
    });
  }
  return details;
}

const STATUS_LEVELS = ["saving", "ok", "warn", "error", "queued"];

export function statusClass(node, level) {
  for (const l of STATUS_LEVELS) node.classList.remove(`status-${l}`);
  node.classList.add(`status-${level}`);
}
