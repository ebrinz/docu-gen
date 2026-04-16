"""Schema validator tests."""
import pytest
from docugen.themes.primitives._base import validate_schema


SCHEMA_NUMERIC = {
    "required": ["title", "value"],
    "types": {"title": str, "value": (int, float)},
}


def test_accepts_valid():
    errs = validate_schema({"title": "X", "value": 3.14}, SCHEMA_NUMERIC, "data")
    assert errs == []


def test_rejects_missing_required():
    errs = validate_schema({"title": "X"}, SCHEMA_NUMERIC, "data")
    assert any("value" in e for e in errs)


def test_rejects_wrong_type():
    errs = validate_schema({"title": 42, "value": 3.14}, SCHEMA_NUMERIC, "data")
    assert any("title" in e and "str" in e for e in errs)


def test_enum_violation():
    schema = {"required": ["mode"], "enums": {"mode": {"a", "b", "c"}}}
    errs = validate_schema({"mode": "z"}, schema, "data")
    assert any("mode" in e for e in errs)


def test_nested_list():
    schema = {
        "required": ["series"],
        "types": {"series": list},
        "children": {
            "series": {
                "required": ["label", "value"],
                "types": {"label": str, "value": (int, float)},
            }
        },
    }
    data = {"series": [{"label": "A", "value": 1}, {"label": "B"}]}
    errs = validate_schema(data, schema, "data")
    assert any("series[1]" in e and "value" in e for e in errs)
