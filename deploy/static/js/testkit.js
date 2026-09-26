// Minimal test harness for static/tests.html. No tooling, no build step,
// no package.json -- just two functions and a results list rendered into
// the page. A real JS test runner needs npm install and a config file,
// which destroys the defining property of this stack.

const results = [];

export function test(name, fn) {
  try {
    fn();
    results.push({ name, ok: true });
  } catch (e) {
    results.push({ name, ok: false, error: e.message || String(e) });
  }
}

export function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(
      `${message ? message + ": " : ""}expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`
    );
  }
}

export function report(root) {
  const passed = results.filter((r) => r.ok).length;
  const summary = document.createElement("h2");
  summary.textContent = `${passed}/${results.length} passed`;
  summary.style.color = passed === results.length ? "green" : "crimson";
  root.appendChild(summary);

  const list = document.createElement("ul");
  for (const r of results) {
    const li = document.createElement("li");
    li.textContent = r.ok ? `✓ ${r.name}` : `✗ ${r.name} -- ${r.error}`;
    li.style.color = r.ok ? "green" : "crimson";
    list.appendChild(li);
  }
  root.appendChild(list);
}
