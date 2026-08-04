"""Deterministic JSON serialization, byte-identical to the TypeScript
implementation's ``canonicalize()`` (see ``src/canonical.ts`` in the repo root).

Two ComputeLedger implementations (the TS build, this Python port) must
produce byte-identical output for the same logical payload, since that
output is what gets hashed and signed. A signature created by one language
must verify in the other, so this module's behavior is a cross-language
interop contract, not an implementation detail.

Rules (mirroring ``canonicalize()`` in canonical.ts):
  * Object keys are sorted lexicographically, recursively.
  * No whitespace anywhere in the output.
  * Arrays preserve their original order.
  * ``None`` serializes to ``null``.
  * A key mapped to the ``UNDEFINED`` sentinel is dropped from the object
    entirely (mirrors JS ``undefined`` being omitted by ``JSON.stringify``
    semantics, which is what the TS ``canonicalize()`` implements by
    filtering out keys whose value is ``undefined``). Python has no
    ``undefined``, so callers that need "this key may be absent" behavior
    should use this sentinel rather than ``None``.
  * Numbers must render exactly as JavaScript's ``JSON.stringify`` would
    render the equivalent ``Number`` value. This is the important
    divergence trap: Python's ``json.dumps(1.0)`` produces ``"1.0"`` but
    JS's ``JSON.stringify(1.0)`` produces ``"1"`` (JS has one numeric
    type; there is no float/int distinction at the JSON level). This
    module implements the ECMA-262 ``Number::toString`` formatting
    algorithm on top of Python's own shortest-round-trip ``repr()`` (which
    is guaranteed, like JS engines' dtoa/Ryu implementations, to produce
    the unique shortest decimal digit sequence that round-trips to the
    same IEEE-754 double) so both languages agree digit-for-digit, not
    just value-for-value.
  * Non-ASCII characters in strings are NOT escaped (``ensure_ascii=False``),
    matching ``JSON.stringify``'s default behavior of emitting UTF-8/UTF-16
    text as-is rather than ``\\uXXXX``-escaping it.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

#: Sentinel marking "this field is absent", mirroring JS ``undefined``.
#: A dict value equal to this sentinel (by identity) has its key dropped
#: entirely from the canonicalized output, exactly like the TS
#: implementation drops keys whose value is ``undefined``.
UNDEFINED = object()

_EXP_RE = re.compile(r"[eE]")


def _shortest_digits(x: float) -> tuple[str, int]:
    """Return (digits, e) such that x == 0.<digits> * 10**e, digits has no
    leading or trailing zeros (unless x rounds to exactly the single digit
    "0", which never happens here since callers exclude x == 0).

    Derived by parsing Python's ``repr(x)`` — which, like JS engines,
    computes the shortest decimal digit sequence that round-trips to the
    same IEEE-754 double — regardless of whether Python chose to print it
    in fixed or scientific notation.
    """
    s = repr(x)
    if _EXP_RE.search(s):
        mantissa, exp_str = _EXP_RE.split(s)
        exp = int(exp_str)
    else:
        mantissa = s
        exp = 0

    if "." in mantissa:
        int_part, frac_part = mantissa.split(".")
    else:
        int_part, frac_part = mantissa, ""

    full = int_part + frac_part
    point_pos = len(int_part) + exp

    stripped_leading = full.lstrip("0")
    leading_zero_count = len(full) - len(stripped_leading)

    digits = stripped_leading.rstrip("0")
    if digits == "":
        # x was exactly zero-valued after all digits stripped; callers
        # guard against this, but fall back safely.
        digits = "0"
        point_pos = 1
        leading_zero_count = 0

    e = point_pos - leading_zero_count
    return digits, e


def format_js_number(value: int | float) -> str:
    """Render a number exactly as JavaScript's ``JSON.stringify`` / ``Number.
    prototype.toString`` would, implementing the ECMA-262 ``Number::toString``
    formatting algorithm (see https://tc39.es/ecma262/#sec-numeric-types-number-tostring).

    Raises ``ValueError`` for non-finite values (NaN, +/-Infinity), matching
    canonical.ts's rejection of non-finite numbers.
    """
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("Cannot canonicalize non-finite number")
    if x == 0:
        # JS: JSON.stringify(-0) === "0" too (JSON has no signed zero).
        return "0"

    sign = "-" if x < 0 else ""
    digits, e = _shortest_digits(abs(x))
    k = len(digits)

    if k <= e <= 21:
        body = digits + "0" * (e - k)
    elif 0 < e <= 21:
        body = digits[:e] + "." + digits[e:]
    elif -6 < e <= 0:
        body = "0." + "0" * (-e) + digits
    else:
        exp_val = e - 1
        exp_sign = "+" if exp_val >= 0 else "-"
        exp_digits = str(abs(exp_val))
        mantissa = digits if k == 1 else f"{digits[0]}.{digits[1:]}"
        body = f"{mantissa}e{exp_sign}{exp_digits}"

    return sign + body


def _serialize(value: Any) -> str:
    if value is None or value is UNDEFINED:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return format_js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_serialize(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        entries = [
            f"{json.dumps(str(k), ensure_ascii=False)}:{_serialize(value[k])}"
            for k in keys
            if value[k] is not UNDEFINED
        ]
        return "{" + ",".join(entries) + "}"
    raise TypeError(f"Cannot canonicalize value of type {type(value).__name__}")


def canonicalize(value: Any) -> str:
    """Deterministic JSON serialization: object keys sorted recursively, no
    whitespace. Byte-identical to the TypeScript ``canonicalize()``."""
    return _serialize(value)


def canonicalize_to_bytes(value: Any) -> bytes:
    return canonicalize(value).encode("utf-8")
