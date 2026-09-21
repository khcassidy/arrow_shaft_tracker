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

// Filters a lookup list down to what a <select> should actually offer:
// every active option, plus whichever one (if any) the record currently
// holds -- even when that one has since been deactivated. Dropping an
// inactive option outright would leave select.value with nothing to
// match once it's set, and the browser silently falls back to the
// select's first entry; the next unrelated save then rewrites that
// record's own reference to a completely different option. currentId
// left undefined (a fresh, not-yet-saved record) filters to active-only.
export function pickableOptions(options, currentId) {
  return options.filter((o) => o.isActive !== false || o.id === currentId);
}

// A picker's own label for one option, marking a kept-but-inactive entry
// so it doesn't look like an ordinary live choice.
export function optionLabel(option) {
  return option.isActive === false ? `${option.label} (inactive)` : option.label;
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

// Commits a text/number/select input's value on blur, and on Enter (which
// just blurs -- blur is the one place that actually commits, so there is
// no double-commit to guard against the way entrygrid.js's own focus-ring
// interaction needs). A no-op if the value hasn't actually changed since
// the last commit, so tabbing through an untouched field sends nothing.
// On failure, onCommit's own rejection reverts the input to its last
// committed value -- the caller is responsible for showing the error
// (e.g. into its own errorBox) before rejecting.
export function commitOnBlur(input, { onCommit }) {
  let lastValue = input.value;
  async function commit() {
    if (input.value === lastValue) return;
    const prevValue = lastValue;
    lastValue = input.value;
    try {
      await onCommit(input.value);
    } catch {
      input.value = prevValue;
      lastValue = prevValue;
    }
  }
  input.addEventListener("blur", commit);
  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      input.blur(); // triggers the blur listener above
    }
  });
}

// The <select> equivalent of commitOnBlur, triggered by "change" instead
// of "blur": a <select> has no in-progress typed state to wait out, and
// calling .blur() from a change handler to route through commitOnBlur is
// NOT a safe substitute -- blur() is a no-op unless the element already
// has focus, which a programmatic value change (Playwright's
// select_option, or any future keyboard-driven picker) does not
// guarantee the way a real mouse click does. Same revert-on-failure
// behaviour as commitOnBlur otherwise.
export function commitOnChange(select, { onCommit }) {
  let lastValue = select.value;
  select.addEventListener("change", async () => {
    if (select.value === lastValue) return;
    const prevValue = lastValue;
    lastValue = select.value;
    try {
      await onCommit(select.value);
    } catch {
      select.value = prevValue;
      lastValue = prevValue;
    }
  });
}

const STATUS_LEVELS = ["saving", "ok", "warn", "error", "queued"];

export function statusClass(node, level) {
  for (const l of STATUS_LEVELS) node.classList.remove(`status-${l}`);
  node.classList.add(`status-${level}`);
}
