"""Decimal-string parsing and integer minor-unit conversions.

Spine is stored as centipounds (cp), weight as centigrams (cg), and the
two-reading average spine as millipounds (mlb). Nothing here ever produces
or consumes a Python float: every conversion goes string -> Decimal ->
int, with ROUND_HALF_UP made explicit at each quantisation.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENTI = Decimal(100)
MILLI = Decimal(1000)
GRAINS_PER_GRAM = Decimal("15.4324")

_DECIMAL_SHAPE_RE = re.compile(r"^[+-]?(?:\d+\.\d+|\.\d+|\d+)$")


class UnitError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def normalize_decimal_string(raw: str, *, max_dp: int = 2) -> Decimal:
    text = raw.strip()
    if not text:
        raise UnitError("EMPTY", "value is empty")
    text = text.replace(",", ".")
    if not _DECIMAL_SHAPE_RE.match(text):
        raise UnitError("NOT_A_NUMBER", f"{raw!r} is not a valid decimal number")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise UnitError("NOT_A_NUMBER", f"{raw!r} is not a valid decimal number") from exc
    exponent = value.as_tuple().exponent
    dp = -exponent if exponent < 0 else 0
    if dp > max_dp:
        raise UnitError("TOO_MANY_DP", f"{raw!r} has more than {max_dp} decimal places")
    return value


def _to_minor(value: Decimal, scale: Decimal) -> int:
    return int((value * scale).to_integral_value(rounding=ROUND_HALF_UP))


def mean_minor(values: list[int]) -> int:
    """Rounds the mean of already-minor-unit integers (e.g. several
    shafts' avg_spine_mlb) back to an integer minor-unit value, via
    Decimal + ROUND_HALF_UP -- plain `sum(values) / len(values)` would
    silently hand back a float, the one thing nothing in this module ever
    produces."""
    return int(
        (Decimal(sum(values)) / Decimal(len(values))).to_integral_value(rounding=ROUND_HALF_UP)
    )


def parse_spine_lb(raw: str) -> int:
    """Parse a spine reading in pounds to centipounds. Raises UnitError."""
    value = normalize_decimal_string(raw, max_dp=2)
    cp = _to_minor(value, CENTI)
    if cp <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive spine value")
    return cp


def parse_weight_g(raw: str) -> int:
    """Parse a weight in grams to centigrams. Raises UnitError."""
    value = normalize_decimal_string(raw, max_dp=2)
    cg = _to_minor(value, CENTI)
    if cg <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive weight value")
    return cg


def parse_spine_band_lb(raw: str) -> int:
    """Parse a spine-band boundary in pounds to millipounds -- the same
    unit avg_spine_mlb is stored in, so a band's bounds compare directly
    against it with no scaling at the call site."""
    value = normalize_decimal_string(raw, max_dp=2)
    mlb = _to_minor(value, MILLI)
    if mlb <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive spine value")
    return mlb


def parse_length_in(raw: str) -> int:
    """Parse a shaft length in inches to centi-inches. Raises UnitError."""
    value = normalize_decimal_string(raw, max_dp=2)
    c_in = _to_minor(value, CENTI)
    if c_in <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive length value")
    return c_in


def grains_to_weight_cg(raw: str) -> int:
    """Parse a weight in grains to centigrams. Lossy: 1 g = 15.4324 gr exactly,
    but 1 gr does not divide evenly back into whole centigrams."""
    value = normalize_decimal_string(raw, max_dp=2)
    if value <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive weight value")
    grams = value / GRAINS_PER_GRAM
    cg = int((grams * CENTI).to_integral_value(rounding=ROUND_HALF_UP))
    if cg <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive weight value")
    return cg


def parse_weight(raw: str, unit: str) -> int:
    """Dispatch on the entered unit. Always returns centigrams."""
    if unit == "g":
        return parse_weight_g(raw)
    if unit == "gr":
        return grains_to_weight_cg(raw)
    raise UnitError("BAD_UNIT", f"unknown weight unit {unit!r}")


def parse_weight_gr(raw: str) -> int:
    """Parse a weight in grains to centigrains (1 gr = 100). Raises UnitError.

    Centigrains are the one arrow-component-catalogue weight unit; a
    shaft's own weight stays centigrams, see parse_weight above. A whole
    grain value (a field point's "100 gr") needs its own minor unit
    because grains_to_weight_cg's own gram conversion is lossy -- see its
    docstring -- and a catalogue value should round-trip exactly."""
    value = normalize_decimal_string(raw, max_dp=2)
    cgr = _to_minor(value, CENTI)
    if cgr <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive weight value")
    return cgr


def grams_to_weight_cgr(raw: str) -> int:
    """Parse a weight in grams to centigrains -- a catalogue's default
    weight may still be typed in grams even though the stored unit is
    grains."""
    value = normalize_decimal_string(raw, max_dp=2)
    if value <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive weight value")
    cgr = int((value * GRAINS_PER_GRAM * CENTI).to_integral_value(rounding=ROUND_HALF_UP))
    if cgr <= 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must be a positive weight value")
    return cgr


def parse_arrow_weight(raw: str, unit: str) -> int:
    """Dispatch on the entered unit. Always returns centigrains."""
    if unit == "gr":
        return parse_weight_gr(raw)
    if unit == "g":
        return grams_to_weight_cgr(raw)
    raise UnitError("BAD_UNIT", f"unknown weight unit {unit!r}")


def parse_signed_weight_gr(raw: str) -> int:
    """Parse a signed weight in grains to centigrains. Unlike every other
    weight parser in this module, negative is valid here (zero is still
    refused) -- a self-nocked shaft has wood cut away, not a component
    added, so a nock catalogue entry's weight is the one place a real
    removal of mass needs to be typeable, not just a component whose
    mass happens to be small."""
    value = normalize_decimal_string(raw, max_dp=2)
    cgr = _to_minor(value, CENTI)
    if cgr == 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must not be zero")
    return cgr


def signed_grams_to_weight_cgr(raw: str) -> int:
    """Parse a signed weight in grams to centigrains."""
    value = normalize_decimal_string(raw, max_dp=2)
    if value == 0:
        raise UnitError("NOT_POSITIVE", f"{raw!r} must not be zero")
    return int((value * GRAINS_PER_GRAM * CENTI).to_integral_value(rounding=ROUND_HALF_UP))


def parse_signed_arrow_weight(raw: str, unit: str) -> int:
    """Dispatch on the entered unit, allowing negative -- used only for
    nock_option's own default weight (repo_lookups.create_weighted_option/
    update_option), since a nock is the one component catalogue where a
    cut-away self nock is a meaningful, negative-mass entry. Fletching
    and point stay through parse_arrow_weight, its positive-only sibling."""
    if unit == "gr":
        return parse_signed_weight_gr(raw)
    if unit == "g":
        return signed_grams_to_weight_cgr(raw)
    raise UnitError("BAD_UNIT", f"unknown weight unit {unit!r}")


def weight_cg_to_grains(cg: int) -> Decimal:
    return (Decimal(cg) / CENTI) * GRAINS_PER_GRAM


def format_spine_cp(cp: int) -> str:
    return str((Decimal(cp) / CENTI).quantize(Decimal("0.01")))


def format_weight_cg(cg: int) -> str:
    return str((Decimal(cg) / CENTI).quantize(Decimal("0.01")))


def format_length_in(c_in: int) -> str:
    return str((Decimal(c_in) / CENTI).quantize(Decimal("0.01")))


def format_avg_spine_mlb(mlb: int) -> str:
    return str((Decimal(mlb) / MILLI).quantize(Decimal("0.001")))


def format_grains(cg: int) -> str:
    return str(weight_cg_to_grains(cg).quantize(Decimal("0.01")))
