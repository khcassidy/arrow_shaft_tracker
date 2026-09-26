import { test, assertEqual } from "./testkit.js";
import {
  displayFromMinor,
  formatFlag,
  formatLengthIn,
  formatQuality,
  formatSpineCp,
  formatSpineMlb,
  formatWeightCg,
  minorFromInput,
} from "./fmt.js";

test("formatSpineMlb formats a positive value", () => {
  assertEqual(formatSpineMlb(54000), "54.000");
});

test("formatSpineMlb formats zero", () => {
  assertEqual(formatSpineMlb(0), "0.000");
});

test("formatSpineMlb formats a negative value", () => {
  assertEqual(formatSpineMlb(-1500), "-1.500");
});

test("formatSpineMlb formats null as an empty string", () => {
  assertEqual(formatSpineMlb(null), "");
});

test("formatWeightCg formats a positive value", () => {
  assertEqual(formatWeightCg(45012), "450.12");
});

test("formatWeightCg formats zero", () => {
  assertEqual(formatWeightCg(0), "0.00");
});

test("formatWeightCg formats undefined as an empty string", () => {
  assertEqual(formatWeightCg(undefined), "");
});

test("formatSpineCp formats a positive value", () => {
  assertEqual(formatSpineCp(150), "1.50");
});

test("formatLengthIn formats a positive value", () => {
  assertEqual(formatLengthIn(3225), "32.25");
});

test("formatQuality title-cases a value", () => {
  assertEqual(formatQuality("USABLE"), "Usable");
});

test("formatQuality returns a dash for a falsy value", () => {
  assertEqual(formatQuality(null), "–");
});

test("formatFlag renders the true and false text", () => {
  assertEqual(formatFlag(true, "yes", "no"), "yes");
  assertEqual(formatFlag(false, "yes", "no"), "no");
});

test("formatFlag renders a dash for null", () => {
  assertEqual(formatFlag(null, "yes", "no"), "–");
});

test("minorFromInput scales a typed decimal to minor units", () => {
  assertEqual(minorFromInput("3.000", 3), 3000);
});

test("minorFromInput scales a two-decimal value", () => {
  assertEqual(minorFromInput("32.25", 2), 3225);
});

test("displayFromMinor is the inverse of minorFromInput", () => {
  assertEqual(displayFromMinor(3225, 2), 32.25);
});
