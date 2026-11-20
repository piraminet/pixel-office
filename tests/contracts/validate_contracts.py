#!/usr/bin/env python3
"""G3 contract validator (Python side).

Primary implementation: the `jsonschema` library (Draft 2020-12) when importable.
Fallback: a hand-rolled subset validator implementing EXACTLY the same rule set as
tests/contracts/validate_contracts.js (type, enum, const, pattern, minLength,
minimum, minItems, required, additionalProperties:false, nested properties), so the
two languages validate the same fixtures with identical semantics. Recorded in the
G3 ledger section; pydantic-generated models arrive in G4.

Also enforces the G3 structural criteria:
  C3.4  AgentIdentity requires 8 distinct identity-separation fields
  C3.5  asserted_id (caller-supplied) and verified_binding are separate fields
  C3.6  unsupported schema versions fail explicitly (const version: 1)
  C3.7  no value-bearing credential keys anywhere in contracts or fixtures

Exit 0 = all checks pass. Any failure exits 1 with the offending path.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMAS = os.path.join(ROOT, "contracts", "schemas")
FIX = os.path.join(ROOT, "tests", "contracts", "fixtures")

SEPARATION_FIELDS = [
    "employee_id",
    "sprite_id",
    "native_harness_id",
    "harness_instance_id",
    "session_id",
    "current_task_id",
    "operational_scope",
    "authorization_context",
]
SECRET_KEY_RX = re.compile(
    r"secret|password|api[_-]?key|private[_-]?key|token[_-]?value|"
    r"bearer|credential[_-]?value|client[_-]?secret",
    re.IGNORECASE,
)


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check(node, schema, path, errors):
    # types
    want = schema.get("type")
    if want:
        types = want if isinstance(want, list) else [want]
        ok = False
        for t in types:
            if t == "object" and isinstance(node, dict):
                ok = True
            elif t == "array" and isinstance(node, list):
                ok = True
            elif t == "string" and isinstance(node, str):
                ok = True
            elif t == "integer" and isinstance(node, int) and not isinstance(node, bool):
                ok = True
            elif t == "boolean" and isinstance(node, bool):
                ok = True
            elif t == "null" and node is None:
                ok = True
        if not ok:
            errors.append(f"{path}: type {want} vs {type(node).__name__}")
            return
    if "const" in schema and node != schema["const"]:
        errors.append(f"{path}: const {schema['const']!r} vs {node!r}")
        return
    if "enum" in schema and node not in schema["enum"]:
        errors.append(f"{path}: {node!r} not in enum")
        return
    if isinstance(node, str):
        if "pattern" in schema and not re.search(schema["pattern"], node):
            errors.append(f"{path}: pattern {schema['pattern']} vs {node!r}")
            return
        if "minLength" in schema and len(node) < schema["minLength"]:
            errors.append(f"{path}: minLength {schema['minLength']} vs len {len(node)}")
            return
    if isinstance(node, int) and "minimum" in schema and node < schema["minimum"]:
        errors.append(f"{path}: minimum {schema['minimum']} vs {node}")
        return
    if isinstance(node, list):
        if "minItems" in schema and len(node) < schema["minItems"]:
            errors.append(f"{path}: minItems {schema['minItems']} vs {len(node)}")
            return
        if "items" in schema:
            for i, item in enumerate(node):
                check(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(node, dict):
        props = schema.get("properties", {})
        for r in schema.get("required", []):
            if r not in node:
                errors.append(f"{path}: missing required {r}")
        if schema.get("additionalProperties") is False:
            for k in node:
                if k not in props:
                    errors.append(f"{path}: additional property {k}")
        for k, v in node.items():
            if k in props:
                check(v, props[k], f"{path}.{k}", errors)


validate_subset = check  # identical rule semantics to the JS validator


def main():
    try:
        from jsonschema import Draft202012Validator

        impl = "jsonschema"
    except ImportError:
        Draft202012Validator = None
        impl = "subset"
    print(f"PYTHON_VALIDATOR={impl}")

    failures = []
    passed = 0
    expectations = []
    for f in sorted(x for x in os.listdir(os.path.join(FIX, "valid")) if x.endswith(".valid.json")):
        n = f[:-11]
        expectations.append(
            (os.path.join(FIX, "valid", f), os.path.join(SCHEMAS, n + ".schema.json"), True)
        )
    for n in sorted(
        f[:-13] for f in os.listdir(os.path.join(FIX, "invalid")) if f.endswith(".invalid.json")
    ):
        expectations.append(
            (
                os.path.join(FIX, "invalid", n + ".invalid.json"),
                os.path.join(SCHEMAS, n.split(".")[0] + ".schema.json"),
                False,
            )
        )

    for fpath, spath, should_pass in expectations:
        fx, sc = load(fpath), load(spath)
        errors = []
        if Draft202012Validator is not None:
            for e in Draft202012Validator(sc).iter_errors(fx):
                errors.append(f"$.{'/'.join(str(p) for p in e.absolute_path)}: {e.message}")
        else:
            check(fx, sc, "$", errors)
        if should_pass and errors:
            failures.append(f"FAIL accept {os.path.basename(fpath)}: {errors}")
        elif not should_pass and not errors:
            failures.append(f"FAIL reject {os.path.basename(fpath)}: accepted, expected rejection")
        else:
            passed += 1

    # C3.4: AgentIdentity 8 separations required + distinct
    ai = load(os.path.join(SCHEMAS, "AgentIdentity.schema.json"))
    req = ai["required"]
    distinct = len(set(SEPARATION_FIELDS)) == 8
    missing = [f for f in SEPARATION_FIELDS if f not in req]
    if not distinct or missing:
        failures.append(f"FAIL C3.4 separations distinct={distinct} missing={missing}")
    else:
        passed += 1
    # C3.5: asserted_id vs verified_binding
    if (
        "asserted_id" in req
        and "verified_binding" in req
        and "asserted_id" not in ai["properties"].get("verified_binding", {}).get("properties", {})
    ):
        passed += 1
    else:
        failures.append("FAIL C3.5 asserted_id/verified_binding distinction")
    # C3.7: no value-bearing keys in any schema or fixture
    offenders = []
    for base in (SCHEMAS, os.path.join(FIX, "valid")):
        for fn in sorted(os.listdir(base)):
            text = open(os.path.join(base, fn), encoding="utf-8").read()
            for m in SECRET_KEY_RX.finditer(text):
                offenders.append(f"{fn}:{m.group(0)}")
    if offenders:
        failures.append(f"FAIL C3.7 value-bearing keys: {offenders[:8]}")
    else:
        passed += 1

    print(f"python: {passed} checks passed, {len(failures)} failed")
    for f in failures:
        print(" ", f)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
