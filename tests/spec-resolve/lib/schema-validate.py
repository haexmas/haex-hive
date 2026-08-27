#!/usr/bin/env python3
"""Minimal JSON-Schema (Draft-07 subset) validator for spec-resolve tests.

Only implements the constructs used by
`.specify/schemas/haex-hive.schema.json`:

    type, const, enum, required, properties, additionalProperties,
    items, minLength, minItems, pattern, oneOf, allOf, if/then, not

Definitely not a general-purpose Draft-07 implementation — but that is the
point. The task (T030) requires an independent second implementation that
mirrors the schema's semantics so schema-vs-tool disagreement is caught.

Usage:

    python3 schema-validate.py <schema.json> <instance.json>

Exit codes:
    0 — instance validates against schema
    1 — instance fails validation (reason on stderr)
    2 — schema construct not supported (safety net for schema drift)
"""

from __future__ import annotations

import json
import re
import sys


class SchemaError(Exception):
    pass


class ValidationError(Exception):
    pass


def _get(schema: dict, key: str, default=None):
    return schema.get(key, default)


def _resolve_ref(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise SchemaError(f"only local refs supported: {ref}")
    parts = ref[2:].split("/")
    node = root
    for part in parts:
        node = node[part]
    return node


def _validate(schema: dict, instance, root: dict, path: str = "$") -> None:
    if "$ref" in schema:
        _validate(_resolve_ref(root, schema["$ref"]), instance, root, path)
        return

    known_keys = {
        "type", "const", "enum", "required", "properties",
        "additionalProperties", "items", "minLength", "minItems",
        "pattern", "oneOf", "anyOf", "allOf", "if", "then", "not",
        "description", "title", "$id", "$schema", "definitions",
    }
    unknown = set(schema.keys()) - known_keys
    if unknown:
        raise SchemaError(f"unsupported schema keyword(s): {sorted(unknown)}")

    if "type" in schema:
        expected = schema["type"]
        types = [expected] if isinstance(expected, str) else list(expected)
        matches = False
        for t in types:
            if t == "object" and isinstance(instance, dict):
                matches = True
            elif t == "array" and isinstance(instance, list):
                matches = True
            elif t == "string" and isinstance(instance, str):
                matches = True
            elif t == "null" and instance is None:
                matches = True
            elif t == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
                matches = True
            elif t == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
                matches = True
            elif t == "boolean" and isinstance(instance, bool):
                matches = True
        if not matches:
            raise ValidationError(f"{path}: type {expected} expected")

    if "const" in schema:
        if instance != schema["const"]:
            raise ValidationError(
                f"{path}: expected const {schema['const']!r}, got {instance!r}"
            )

    if "enum" in schema:
        if instance not in schema["enum"]:
            raise ValidationError(
                f"{path}: value {instance!r} not in enum {schema['enum']!r}"
            )

    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            raise ValidationError(
                f"{path}: value {instance!r} does not match pattern {schema['pattern']!r}"
            )

    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            raise ValidationError(f"{path}: string shorter than minLength")

    if "minItems" in schema and isinstance(instance, list):
        if len(instance) < schema["minItems"]:
            raise ValidationError(f"{path}: array shorter than minItems")

    if isinstance(instance, dict):
        if "required" in schema:
            missing = [k for k in schema["required"] if k not in instance]
            if missing:
                raise ValidationError(
                    f"{path}: missing required field(s) {missing}"
                )
        if "properties" in schema:
            for key, subschema in schema["properties"].items():
                if key in instance:
                    _validate(subschema, instance[key], root, f"{path}.{key}")
        if schema.get("additionalProperties") is False:
            known = set(schema.get("properties", {}).keys())
            extra = [k for k in instance if k not in known]
            if extra:
                raise ValidationError(
                    f"{path}: additionalProperties disallowed, got {extra}"
                )

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            _validate(schema["items"], item, root, f"{path}[{i}]")

    if "allOf" in schema:
        for i, sub in enumerate(schema["allOf"]):
            _validate(sub, instance, root, path)

    if "oneOf" in schema:
        matches = 0
        for sub in schema["oneOf"]:
            try:
                _validate(sub, instance, root, path)
                matches += 1
            except ValidationError:
                pass
        if matches != 1:
            raise ValidationError(
                f"{path}: oneOf expects exactly 1 match, got {matches}"
            )

    if "anyOf" in schema:
        for sub in schema["anyOf"]:
            try:
                _validate(sub, instance, root, path)
                break
            except ValidationError:
                continue
        else:
            raise ValidationError(f"{path}: no anyOf branch matched")

    if "if" in schema:
        try:
            _validate(schema["if"], instance, root, path)
            if_ok = True
        except ValidationError:
            if_ok = False
        if if_ok and "then" in schema:
            _validate(schema["then"], instance, root, path)

    if "not" in schema:
        try:
            _validate(schema["not"], instance, root, path)
            passed = True
        except ValidationError:
            passed = False
        if passed:
            raise ValidationError(f"{path}: negated schema unexpectedly matched")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: schema-validate.py <schema.json> <instance.json>", file=sys.stderr)
        return 2
    schema_path, inst_path = sys.argv[1], sys.argv[2]
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    with open(inst_path, encoding="utf-8") as f:
        instance = json.load(f)
    try:
        _validate(schema, instance, schema)
    except ValidationError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1
    except SchemaError as exc:
        print(f"schema-error: {exc}", file=sys.stderr)
        return 2
    print("valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
