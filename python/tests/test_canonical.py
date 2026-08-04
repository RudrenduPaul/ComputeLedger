"""Mirrors src/canonical.test.ts, plus additional JS-number-formatting
edge cases specific to the cross-language interop contract."""

import math

import pytest

from computeledger.canonical import UNDEFINED, canonicalize, format_js_number


def test_sorts_object_keys_regardless_of_insertion_order():
    a = canonicalize({"b": 1, "a": 2})
    b = canonicalize({"a": 2, "b": 1})
    assert a == b
    assert a == '{"a":2,"b":1}'


def test_sorts_nested_object_keys_recursively():
    out = canonicalize({"z": {"d": 1, "c": 2}, "a": 1})
    assert out == '{"a":1,"z":{"c":2,"d":1}}'


def test_preserves_array_order():
    assert canonicalize([3, 1, 2]) == "[3,1,2]"


def test_drops_keys_with_undefined_values():
    assert canonicalize({"a": 1, "b": UNDEFINED}) == '{"a":1}'


def test_renders_null_explicitly():
    assert canonicalize({"a": None}) == '{"a":null}'


def test_rejects_non_finite_numbers():
    with pytest.raises(ValueError):
        canonicalize({"a": math.nan})
    with pytest.raises(ValueError):
        canonicalize({"a": math.inf})
    with pytest.raises(ValueError):
        canonicalize({"a": -math.inf})


def test_identical_output_for_structurally_identical_differently_ordered_objects():
    p1 = {"usage": {"durationSeconds": 10, "workloadType": "training"}, "provider": "aws"}
    p2 = {"provider": "aws", "usage": {"workloadType": "training", "durationSeconds": 10}}
    assert canonicalize(p1) == canonicalize(p2)


# --- JS-number-formatting divergence traps -----------------------------


def test_integer_valued_float_has_no_trailing_decimal():
    # Python's json.dumps(1.0) -> "1.0"; JS JSON.stringify(1.0) -> "1".
    assert canonicalize(1.0) == "1"
    assert canonicalize(100.0) == "100"
    assert canonicalize(3600.0) == "3600"


def test_fractional_numbers_render_like_js():
    assert canonicalize(0.1) == "0.1"
    assert canonicalize(1.5) == "1.5"
    assert canonicalize(123.456) == "123.456"


def test_negative_zero_renders_as_zero():
    assert canonicalize(-0.0) == "0"


def test_small_numbers_switch_to_scientific_notation_at_js_threshold():
    # JS stays decimal down to 1e-6, switches to scientific at 1e-7.
    assert canonicalize(0.000001) == "0.000001"
    assert canonicalize(0.0000001) == "1e-7"


def test_large_integers_switch_to_scientific_notation_at_js_threshold():
    # JS stays decimal up to 1e20, switches to scientific at 1e21.
    assert canonicalize(1e20) == "100000000000000000000"
    assert canonicalize(1e21) == "1e+21"


def test_non_ascii_strings_are_not_escaped():
    # Python's json.dumps defaults to ensure_ascii=True; JS's JSON.stringify
    # does not escape non-ASCII by default. canonicalize() must match JS.
    assert canonicalize("café") == '"café"'
    assert canonicalize("中文") == '"中文"'


def test_format_js_number_matches_node_reference_values():
    # A broad set of values cross-checked directly against `node -e
    # 'console.log(JSON.stringify(x))'` output during development.
    cases = {
        0.0: "0",
        -0.0: "0",
        1.0: "1",
        -1.0: "-1",
        120.0: "120",
        0.5: "0.5",
        -0.5: "-0.5",
        0.0001: "0.0001",
        0.00001: "0.00001",
        1e-8: "1e-8",
        1e22: "1e+22",
        1.5e21: "1.5e+21",
        9999999999999998.0: "9999999999999998",
        123456789012345.67: "123456789012345.67",
        5e-7: "5e-7",
        -1e21: "-1e+21",
        1e300: "1e+300",
        1e-300: "1e-300",
    }
    for value, expected in cases.items():
        assert format_js_number(value) == expected, f"mismatch for {value!r}"
