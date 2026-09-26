import { test, assertEqual } from "./testkit.js";
import { optionLabel, pickableOptions } from "./ui.js";

const OPTIONS = [
  { id: 1, label: "Alpha", isActive: true },
  { id: 2, label: "Beta", isActive: false },
  { id: 3, label: "Gamma", isActive: true },
];

test("pickableOptions keeps only active options with no current id", () => {
  const ids = pickableOptions(OPTIONS).map((o) => o.id);
  assertEqual(JSON.stringify(ids), JSON.stringify([1, 3]));
});

test("pickableOptions keeps an inactive option that matches the current id", () => {
  const ids = pickableOptions(OPTIONS, 2).map((o) => o.id);
  assertEqual(JSON.stringify(ids), JSON.stringify([1, 2, 3]));
});

test("pickableOptions drops an inactive option that is not the current id", () => {
  const ids = pickableOptions(OPTIONS, 3).map((o) => o.id);
  assertEqual(JSON.stringify(ids), JSON.stringify([1, 3]));
});

test("optionLabel marks an inactive option", () => {
  assertEqual(optionLabel({ label: "Beta", isActive: false }), "Beta (inactive)");
});

test("optionLabel leaves an active option's label untouched", () => {
  assertEqual(optionLabel({ label: "Alpha", isActive: true }), "Alpha");
});
