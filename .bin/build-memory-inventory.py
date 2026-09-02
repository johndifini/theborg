#!/usr/bin/env python3
"""Deterministic tooling for The Borg's long-term memory inventory.

Implements migration steps 1, 2, and 3 of
`c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md`: the registry schema and its
validator, read-only discovery of the complete artifact set, and the mechanical
bootstrap that gives every discovered artifact a record.

    build-memory-inventory.py validate [options]
    build-memory-inventory.py discover [options]
    build-memory-inventory.py bootstrap [options]

Design constraints this file exists to satisfy:

  * No third-party dependencies. This workspace has no PyYAML, no jsonschema,
    and network access is restricted, so a scheduled job cannot rely on
    `pip install` succeeding. Both the YAML reader and the schema validator are
    strict subsets implemented here. They fail loudly on any construct they do
    not implement, so an unsupported construct can never be silently
    mis-parsed into a passing validation.

  * Private stays private (design principle 5). Overlay records are read from
    gitignored `.private/` files, are required to be private or redacted, and
    are reported as counts only unless `--show-private` is passed. Nothing here
    writes an overlay path or rationale into a tracked file.

  * Declared intent only (design principle 3). The validator checks the
    hand-declared registry; discovery computes observed facts. The two are
    joined for reporting and never written back into each other.

  * Discovery is read-only and does not enforce coverage. It reports how many
    artifacts are unregistered and exits 0 either way, because the design gates
    the LINT.md coverage rule on the inventory first reaching 100% (migration
    step 4) — enforcing earlier would mean a knowingly red audit for the whole
    migration. Hashes, link graphs, drift checks, and review scheduling belong
    to the computed snapshot and are deliberately still absent.

  * Registered is not reviewed. `bootstrap` writes only what the tree
    determines and marks every record it emits `status: draft`; the human
    judgment fields — rationale, provenance, risk, success signals, retirement
    triggers, remediation policy — are left empty rather than filled with
    plausible text, and `validate --require-reviewed` fails while any draft
    remains. Full coverage and full review are two different numbers, and both
    are printed on every run. An artifact `bootstrap` cannot honestly describe
    (an orphaned bridge with no canonical source) is named and left uncovered.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2


# --------------------------------------------------------------------------
# YAML subset reader
# --------------------------------------------------------------------------

class YamlSubsetError(Exception):
    """A construct outside the supported YAML subset, or a malformed document."""


_SUPPORTED_YAML = """Supported: block mappings, block sequences, nested
indentation with spaces, `#` comments, flow sequences on one line, and scalars
(plain, 'single-quoted', "double-quoted", integers, true/false, null/~).
Not supported: block scalars (| >), anchors/aliases (& *), tags (!),
multiple documents, flow mappings ({}), and tab indentation."""


def _strip_comment(line: str) -> str:
    """Remove a trailing `#` comment that is not inside a quoted scalar."""
    out = []
    quote = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            if quote == '"' and ch == "\\" and i + 1 < len(line):
                out.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _parse_scalar(text: str, lineno: int):
    text = text.strip()
    if text == "" or text in ("null", "~", "Null", "NULL"):
        return None
    first = text[0]
    if first in "&*!|>":
        raise YamlSubsetError(
            "line %d: unsupported YAML construct %r.\n%s" % (lineno, first, _SUPPORTED_YAML)
        )
    if first == "{":
        raise YamlSubsetError(
            "line %d: flow mappings are not supported; use a block mapping.\n%s"
            % (lineno, _SUPPORTED_YAML)
        )
    if first == "[":
        if not text.endswith("]"):
            raise YamlSubsetError(
                "line %d: flow sequence must open and close on one line" % lineno
            )
        return _parse_flow_sequence(text[1:-1], lineno)
    if first == '"':
        return _parse_double_quoted(text, lineno)
    if first == "'":
        return _parse_single_quoted(text, lineno)
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if re.fullmatch(r"[+-]?\d+", text):
        return int(text)
    if re.fullmatch(r"[+-]?\d+\.\d+", text):
        return float(text)
    # Plain scalar. Dates stay strings on purpose: the schema checks them with
    # `format: date`, and a date object would not round-trip through JSON.
    return text


def _parse_double_quoted(text: str, lineno: int) -> str:
    if len(text) < 2 or not text.endswith('"'):
        raise YamlSubsetError("line %d: unterminated double-quoted scalar" % lineno)
    body = text[1:-1]
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            if i + 1 >= len(body):
                raise YamlSubsetError("line %d: dangling escape in scalar" % lineno)
            nxt = body[i + 1]
            mapping = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
            if nxt not in mapping:
                raise YamlSubsetError(
                    "line %d: unsupported escape \\%s" % (lineno, nxt)
                )
            out.append(mapping[nxt])
            i += 2
            continue
        if ch == '"':
            raise YamlSubsetError("line %d: unescaped quote inside scalar" % lineno)
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_single_quoted(text: str, lineno: int) -> str:
    if len(text) < 2 or not text.endswith("'"):
        raise YamlSubsetError("line %d: unterminated single-quoted scalar" % lineno)
    return text[1:-1].replace("''", "'")


def _split_flow(body: str, lineno: int):
    """Split a flow sequence body on commas that are outside quotes."""
    parts, buf, quote = [], [], None
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if quote:
        raise YamlSubsetError("line %d: unterminated quote in flow sequence" % lineno)
    parts.append("".join(buf))
    return parts


def _parse_flow_sequence(body: str, lineno: int):
    if body.strip() == "":
        return []
    items = []
    for part in _split_flow(body, lineno):
        if part.strip() == "":
            raise YamlSubsetError("line %d: empty element in flow sequence" % lineno)
        items.append(_parse_scalar(part, lineno))
    return items


def _split_key(content: str, lineno: int):
    """Split `key: value` into (key, rest) or return None if there is no key."""
    quote = None
    i = 0
    while i < len(content):
        ch = content[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            if i != 0:
                # A quote may only open a key at the very start.
                pass
            quote = ch
        elif ch == ":" and (i + 1 == len(content) or content[i + 1] in " \t"):
            raw = content[:i].strip()
            if raw == "":
                raise YamlSubsetError("line %d: empty mapping key" % lineno)
            key = _parse_scalar(raw, lineno) if raw[0] in ("'", '"') else raw
            if not isinstance(key, str):
                raise YamlSubsetError("line %d: mapping keys must be strings" % lineno)
            return key, content[i + 1 :].strip()
        i += 1
    if quote:
        raise YamlSubsetError("line %d: unterminated quote" % lineno)
    return None


class _Reader:
    def __init__(self, text: str):
        self.lines = []  # (indent, content, lineno)
        for lineno, raw in enumerate(text.splitlines(), start=1):
            if "\t" in raw[: len(raw) - len(raw.lstrip(" \t"))]:
                raise YamlSubsetError(
                    "line %d: tab indentation is not supported; use spaces" % lineno
                )
            if raw.strip() == "---":
                continue
            if raw.strip() == "...":
                continue
            content = _strip_comment(raw)
            if content.strip() == "":
                continue
            indent = len(content) - len(content.lstrip(" "))
            self.lines.append((indent, content.strip(), lineno))
        self.pos = 0

    def peek(self):
        return self.lines[self.pos] if self.pos < len(self.lines) else None


def _parse_block(rd: _Reader, indent: int):
    head = rd.peek()
    if head is None or head[0] < indent:
        return None
    if head[1].startswith("- ") or head[1] == "-":
        return _parse_sequence(rd, indent)
    return _parse_mapping(rd, indent)


def _parse_mapping(rd: _Reader, indent: int):
    result = {}
    while True:
        cur = rd.peek()
        if cur is None or cur[0] < indent:
            break
        cur_indent, content, lineno = cur
        if cur_indent > indent:
            raise YamlSubsetError(
                "line %d: unexpected indentation (expected %d spaces, got %d)"
                % (lineno, indent, cur_indent)
            )
        if content.startswith("- "):
            raise YamlSubsetError(
                "line %d: sequence item where a mapping key was expected" % lineno
            )
        split = _split_key(content, lineno)
        if split is None:
            raise YamlSubsetError(
                "line %d: expected `key: value`, got %r.\n%s"
                % (lineno, content, _SUPPORTED_YAML)
            )
        key, rest = split
        if key in result:
            raise YamlSubsetError("line %d: duplicate mapping key %r" % (lineno, key))
        rd.pos += 1
        if rest != "":
            result[key] = _parse_scalar(rest, lineno)
            continue
        nxt = rd.peek()
        if nxt is None or nxt[0] <= indent:
            # `key:` with nothing nested under it is an explicit null. Except for
            # a sequence at the same indent, which YAML allows as the value.
            if nxt is not None and nxt[0] == indent and nxt[1].startswith("-"):
                result[key] = _parse_sequence(rd, indent)
            else:
                result[key] = None
            continue
        result[key] = _parse_block(rd, nxt[0])
    return result


def _parse_sequence(rd: _Reader, indent: int):
    items = []
    while True:
        cur = rd.peek()
        if cur is None or cur[0] < indent:
            break
        cur_indent, content, lineno = cur
        if cur_indent > indent:
            raise YamlSubsetError(
                "line %d: unexpected indentation inside sequence" % lineno
            )
        if not (content.startswith("- ") or content == "-"):
            break
        rest = content[2:].strip() if content.startswith("- ") else ""
        rd.pos += 1
        if rest == "":
            nxt = rd.peek()
            if nxt is None or nxt[0] <= indent:
                items.append(None)
            else:
                items.append(_parse_block(rd, nxt[0]))
            continue
        split = _split_key(rest, lineno)
        if split is None:
            items.append(_parse_scalar(rest, lineno))
            continue
        # `- key: value` opens a mapping whose members sit at the column the
        # key starts in. Re-inject the remainder as a line at that column.
        inner_indent = cur_indent + 2
        rd.lines.insert(rd.pos, (inner_indent, rest, lineno))
        items.append(_parse_mapping(rd, inner_indent))
    return items


def load_yaml(text: str, filename: str = "<string>"):
    """Parse the supported YAML subset. Raises YamlSubsetError on anything else."""
    rd = _Reader(text)
    if not rd.lines:
        return None
    try:
        value = _parse_block(rd, rd.lines[0][0])
    except YamlSubsetError as exc:
        raise YamlSubsetError("%s: %s" % (filename, exc)) from None
    leftover = rd.peek()
    if leftover is not None:
        raise YamlSubsetError(
            "%s: line %d: trailing content after the document root" % (filename, leftover[2])
        )
    return value


# --------------------------------------------------------------------------
# JSON Schema subset validator
# --------------------------------------------------------------------------

class SchemaSupportError(Exception):
    """The schema uses a keyword this validator does not implement."""


# Keywords carrying a single subschema.
_SCHEMA_VALUED = ("additionalProperties", "items", "not", "propertyNames")
# Keywords carrying a map of name -> subschema.
_SCHEMA_MAP_VALUED = ("properties", "patternProperties", "$defs")
# Keywords carrying a list of subschemas.
_SCHEMA_LIST_VALUED = ("anyOf", "allOf")
# Keywords whose value is opaque data, never walked as a schema.
_DATA_VALUED = ("const", "enum", "default", "examples")
# Keywords implemented as plain assertions or ignored annotations.
_ASSERTIONS = (
    "type", "required", "minItems", "maxItems", "uniqueItems", "minLength",
    "maxLength", "minProperties", "maxProperties", "pattern", "format", "$ref",
)
_ANNOTATIONS = ("$schema", "$id", "title", "description", "$comment")

_SUPPORTED_KEYWORDS = frozenset(
    _SCHEMA_VALUED + _SCHEMA_MAP_VALUED + _SCHEMA_LIST_VALUED
    + _DATA_VALUED + _ASSERTIONS + _ANNOTATIONS
)

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def assert_schema_supported(schema, path="#"):
    """Walk the whole schema and reject any keyword we do not implement.

    Done up front rather than lazily so an unsupported keyword in a branch the
    current data never reaches still fails, instead of silently asserting
    nothing on some future record.
    """
    if isinstance(schema, bool):
        # `true`/`false` schemas: allow-anything / forbid-anything.
        return
    if not isinstance(schema, dict):
        raise SchemaSupportError("%s: schema must be an object or a boolean" % path)
    for key, value in schema.items():
        if key not in _SUPPORTED_KEYWORDS:
            raise SchemaSupportError(
                "%s: unsupported schema keyword %r (implemented: %s)"
                % (path, key, ", ".join(sorted(_SUPPORTED_KEYWORDS)))
            )
        if key in _SCHEMA_VALUED:
            assert_schema_supported(value, "%s/%s" % (path, key))
        elif key in _SCHEMA_MAP_VALUED:
            for name, sub in value.items():
                assert_schema_supported(sub, "%s/%s/%s" % (path, key, name))
        elif key in _SCHEMA_LIST_VALUED:
            for idx, sub in enumerate(value):
                assert_schema_supported(sub, "%s/%s/%d" % (path, key, idx))
        elif key == "format" and value != "date":
            raise SchemaSupportError(
                "%s: only `format: date` is implemented, got %r" % (path, value)
            )


def _is_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


class SchemaValidator:
    def __init__(self, schema: dict):
        assert_schema_supported(schema)
        self.root = schema

    def _resolve(self, ref: str):
        if not ref.startswith("#/"):
            raise SchemaSupportError("only local `#/` refs are supported, got %r" % ref)
        node = self.root
        for token in ref[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(node, dict) or token not in node:
                raise SchemaSupportError("unresolvable $ref %r" % ref)
            node = node[token]
        return node

    def validate_def(self, instance, ref: str, path: str) -> list:
        """Validate against one named `$defs` subschema, keeping the whole
        schema as the root so `$ref`s inside it still resolve."""
        return self.validate(instance, self._resolve(ref), path)

    def validate(self, instance, schema=None, path="") -> list:
        schema = self.root if schema is None else schema
        loc = path or "(root)"
        if schema is True:
            return []
        if schema is False:
            return ["%s: no value is allowed here" % loc]
        errors = []

        if "$ref" in schema:
            errors.extend(self.validate(instance, self._resolve(schema["$ref"]), path))

        if "type" in schema:
            types = schema["type"]
            types = [types] if isinstance(types, str) else types
            for t in types:
                if t not in _TYPE_CHECKS:
                    raise SchemaSupportError("unknown type %r" % t)
            if not any(_TYPE_CHECKS[t](instance) for t in types):
                errors.append("%s: expected type %s, got %s"
                              % (loc, "/".join(types), _typename(instance)))
                return errors

        if "const" in schema and instance != schema["const"]:
            errors.append("%s: expected the constant %r, got %r" % (loc, schema["const"], instance))
        if "enum" in schema and instance not in schema["enum"]:
            errors.append("%s: %r is not one of %s"
                          % (loc, instance, ", ".join(repr(v) for v in schema["enum"])))

        if isinstance(instance, str):
            if "minLength" in schema and len(instance) < schema["minLength"]:
                errors.append("%s: string is shorter than %d characters" % (loc, schema["minLength"]))
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                errors.append("%s: string is longer than %d characters" % (loc, schema["maxLength"]))
            if "pattern" in schema and not re.search(schema["pattern"], instance):
                errors.append("%s: %r does not match %s" % (loc, instance, schema["pattern"]))
            if schema.get("format") == "date" and not _is_date(instance):
                errors.append("%s: %r is not a YYYY-MM-DD calendar date" % (loc, instance))

        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < schema["minItems"]:
                errors.append("%s: expected at least %d item(s), got %d"
                              % (loc, schema["minItems"], len(instance)))
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                errors.append("%s: expected at most %d item(s), got %d"
                              % (loc, schema["maxItems"], len(instance)))
            if schema.get("uniqueItems"):
                seen = []
                for item in instance:
                    if item in seen:
                        errors.append("%s: duplicate item %r" % (loc, item))
                        break
                    seen.append(item)
            if "items" in schema:
                for idx, item in enumerate(instance):
                    errors.extend(self.validate(item, schema["items"], "%s[%d]" % (loc, idx)))

        if isinstance(instance, dict):
            for name in schema.get("required", []):
                if name not in instance:
                    errors.append("%s: missing required field %r" % (loc, name))
            if "minProperties" in schema and len(instance) < schema["minProperties"]:
                errors.append("%s: expected at least %d propert(ies), got %d"
                              % (loc, schema["minProperties"], len(instance)))
            if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
                errors.append("%s: expected at most %d propert(ies), got %d"
                              % (loc, schema["maxProperties"], len(instance)))
            props = schema.get("properties", {})
            patterns = schema.get("patternProperties", {})
            additional = schema.get("additionalProperties")
            for name, value in instance.items():
                child = "%s.%s" % (path, name) if path else name
                matched = False
                if name in props:
                    matched = True
                    errors.extend(self.validate(value, props[name], child))
                for pat, sub in patterns.items():
                    if re.search(pat, name):
                        matched = True
                        errors.extend(self.validate(value, sub, child))
                if "propertyNames" in schema:
                    name_errors = self.validate(name, schema["propertyNames"], child)
                    if name_errors:
                        errors.append("%s: invalid property name %r (%s)"
                                      % (loc, name, "; ".join(e.split(": ", 1)[-1] for e in name_errors)))
                if not matched:
                    if additional is False:
                        errors.append("%s: unknown field %r" % (loc, name))
                    elif isinstance(additional, dict):
                        errors.extend(self.validate(value, additional, child))

        for sub in schema.get("allOf", []):
            errors.extend(self.validate(instance, sub, path))
        if "anyOf" in schema:
            branch_errors = [self.validate(instance, sub, path) for sub in schema["anyOf"]]
            if all(b for b in branch_errors):
                flat = "; ".join(e for b in branch_errors for e in b)
                errors.append("%s: matched none of the allowed forms (%s)" % (loc, flat))
        if "not" in schema and not self.validate(instance, schema["not"], path):
            errors.append("%s: matched a forbidden form" % loc)

        return errors


def _typename(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


# --------------------------------------------------------------------------
# Registry semantics
# --------------------------------------------------------------------------

# Flattened `defaults` keys, per the design's `defaults.scoped_rule` example,
# mapped to where they land in a record.
DEFAULTABLE = {
    "owner": ("owner",),
    "scope": ("scope",),
    "visibility": ("visibility",),
    "canonicality": ("canonicality",),
    "load_mode": ("load_mode",),
    "consumers": ("consumers",),
    "risk": ("risk",),
    "review_cadence": ("review", "cadence"),
    "review_method": ("review", "method"),
    "remediation_policy": ("remediation_policy",),
}

DERIVED_CANONICALITY = {"generated", "mirror"}

# The fields a mechanical bootstrap cannot supply, because each is a judgment
# about consequence and intent rather than a fact readable from the tree. A
# bootstrapped record declares `status: draft` and may omit all of them; a
# record counts as reviewed only once a person has supplied them and flipped the
# flag. Migration step 3 turns on this split: 100% registry coverage is not 100%
# review coverage, and these two states have to be countable apart.
HUMAN_JUDGMENT_FIELDS = (
    "rationale",
    "provenance",
    "risk",
    "success_signals",
    "retirement_triggers",
    "remediation_policy",
)

DRAFT = "draft"
REVIEWED = "reviewed"

# Types whose canonicality is fixed by what they are, not by the author's choice.
CANONICALITY_BY_TYPE = {
    "generated_rule_bridge": DERIVED_CANONICALITY,
    "generated_command_bridge": DERIVED_CANONICALITY,
    "compatibility_wrapper": DERIVED_CANONICALITY,
    "knowledge_source": {"source"},
}

# Cerebruh content is read-only from C4PO (design principle 6), so no wiki
# artifact may declare a policy the audit could act on unattended.
CEREBRUH_TYPES = {"knowledge_page", "knowledge_source", "retrieval_index"}


def _deep_copy(value):
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    return value


def apply_defaults(record: dict, defaults: dict) -> dict:
    """Merge class defaults into a record. The record always wins."""
    merged = _deep_copy(record)
    klass = record.get("type")
    block = defaults.get(klass) if isinstance(klass, str) else None
    if not isinstance(block, dict):
        return merged
    for key, target in DEFAULTABLE.items():
        if key not in block:
            continue
        if len(target) == 1:
            merged.setdefault(target[0], _deep_copy(block[key]))
        else:
            outer, inner = target
            nested = merged.get(outer)
            if nested is None:
                nested = {}
                merged[outer] = nested
            if isinstance(nested, dict):
                nested.setdefault(inner, _deep_copy(block[key]))
    return merged


def record_status(merged: dict) -> str:
    """`draft` or `reviewed` for one defaults-merged record.

    Absent `status` means reviewed. Every record written before drafts existed
    was hand-authored and complete, so the default has to be the strict state —
    the opposite default would silently downgrade the existing inventory and let
    an unreviewed record hide by omitting a field.
    """
    return DRAFT if merged.get("status") == DRAFT else REVIEWED


def _draft_schema(schema: dict) -> dict:
    """Copy of the schema whose artifact record no longer requires the human
    judgment fields. Used only for records that declare `status: draft`."""
    relaxed = _deep_copy(schema)
    artifact = relaxed.get("$defs", {}).get("artifact")
    if isinstance(artifact, dict) and isinstance(artifact.get("required"), list):
        artifact["required"] = [f for f in artifact["required"]
                                if f not in HUMAN_JUDGMENT_FIELDS]
    return relaxed


def _envelope_schema(schema: dict, private: bool) -> dict:
    """Copy of the schema that checks everything except the records themselves:
    version, defaults, the artifact map's shape, and its ids.

    Records are validated one at a time afterwards, because which requirements
    apply depends on each record's own `status` and no keyword in the supported
    JSON Schema subset can express that.
    """
    envelope = _deep_copy(schema)
    envelope.setdefault("$defs", {})["artifact"] = True
    if private:
        # A private overlay may legitimately hold zero records — an agent with
        # nothing sensitive still gets a file. The tracked registry may not.
        envelope.get("properties", {}).get("artifacts", {}).pop("minProperties", None)
    return envelope


def status_counts(registries):
    """(public_reviewed, public_draft, private_reviewed, private_draft)."""
    tally = {(False, REVIEWED): 0, (False, DRAFT): 0,
             (True, REVIEWED): 0, (True, DRAFT): 0}
    for reg in registries:
        for record in reg.artifacts.values():
            if not isinstance(record, dict):
                continue
            merged = apply_defaults(record, reg.defaults)
            tally[(reg.private, record_status(merged))] += 1
    return (tally[(False, REVIEWED)], tally[(False, DRAFT)],
            tally[(True, REVIEWED)], tally[(True, DRAFT)])


class Registry:
    def __init__(self, data, source: str, private: bool):
        self.data = data if isinstance(data, dict) else {}
        self.source = source
        self.private = private

    @property
    def artifacts(self) -> dict:
        arts = self.data.get("artifacts")
        return arts if isinstance(arts, dict) else {}

    @property
    def defaults(self) -> dict:
        d = self.data.get("defaults")
        return d if isinstance(d, dict) else {}


def _label(registry: Registry, artifact_id: str, show_private: bool) -> str:
    if registry.private and not show_private:
        return "%s: <private artifact>" % os.path.basename(registry.source)
    return "%s: artifacts.%s" % (registry.source, artifact_id)


def validate_registries(registries, schema: dict, today: _dt.date, show_private: bool):
    """Validate every registry against the schema, then the cross-record rules.

    Returns a list of human-readable error strings. Empty means valid.
    """
    reviewed_validator = SchemaValidator(schema)
    draft_validator = SchemaValidator(_draft_schema(schema))
    errors = []

    # 1. Schema validation, per registry, on the defaults-merged record.
    #    Split in two passes: the envelope (version, defaults, the artifact map
    #    and its ids) once per file, then each record against the requirements
    #    its own `status` selects. A `draft` is a mechanically bootstrapped stub
    #    and is exempt from the human judgment fields; everything else is not.
    for reg in registries:
        if not isinstance(reg.data, dict):
            errors.append("%s: document root must be a mapping" % reg.source)
            continue

        def report(msg):
            if reg.private and not show_private:
                errors.append("%s: %s" % (os.path.basename(reg.source),
                                          _redact(msg, reg.artifacts)))
            else:
                errors.append("%s: %s" % (reg.source, msg))

        envelope = SchemaValidator(_envelope_schema(schema, reg.private))
        for msg in envelope.validate(reg.data):
            report(msg)

        for aid, record in reg.artifacts.items():
            loc = "artifacts.%s" % aid
            if not isinstance(record, dict):
                report("%s: expected type object, got %s" % (loc, _typename(record)))
                continue
            merged = apply_defaults(record, reg.defaults)
            active = (draft_validator if record_status(merged) == DRAFT
                      else reviewed_validator)
            for msg in active.validate_def(merged, "#/$defs/artifact", loc):
                report(msg)

    # 2. Cross-record rules the schema cannot express.
    index = {}
    for reg in registries:
        for aid, record in reg.artifacts.items():
            if aid in index:
                errors.append("%s: duplicate artifact id %r (also in %s)"
                              % (reg.source, aid, index[aid][0].source))
                continue
            index[aid] = (reg, record)

    seen_paths = {}
    for aid, (reg, record) in index.items():
        if not isinstance(record, dict):
            continue
        merged = apply_defaults(record, reg.defaults)
        where = _label(reg, aid, show_private)

        declared_id = record.get("id")
        if declared_id is not None and declared_id != aid:
            errors.append("%s: `id` is %r but the map key is %r; the key is the id"
                          % (where, declared_id, aid))

        path = merged.get("path")
        root = merged.get("path_root", "borg_root")
        if isinstance(path, str):
            key = (root, path)
            if key in seen_paths:
                errors.append("%s: path %s:%s is already claimed by %r; every artifact "
                              "resolves to exactly one record" % (where, root, path, seen_paths[key]))
            else:
                seen_paths[key] = aid

        canonicality = merged.get("canonicality")
        ref = merged.get("canonical_ref")
        if canonicality in DERIVED_CANONICALITY and ref is None:
            errors.append("%s: canonicality %r requires `canonical_ref`" % (where, canonicality))
        if canonicality not in DERIVED_CANONICALITY and ref is not None:
            errors.append("%s: `canonical_ref` is only meaningful for generated or mirror "
                          "artifacts, but canonicality is %r" % (where, canonicality))

        atype = merged.get("type")
        allowed = CANONICALITY_BY_TYPE.get(atype)
        if allowed and canonicality not in allowed:
            errors.append("%s: type %r must have canonicality %s, got %r"
                          % (where, atype, " or ".join(sorted(allowed)), canonicality))

        for other in [ref] if ref else []:
            if other not in index:
                errors.append("%s: `canonical_ref` %r does not resolve to a registered artifact"
                              % (where, other))
            elif not reg.private and index[other][0].private:
                errors.append("%s: `canonical_ref` %r points into a private overlay; a "
                              "tracked record may not name a private artifact" % (where, other))

        related = merged.get("related")
        if isinstance(related, list):
            for other in related:
                if other == aid:
                    errors.append("%s: `related` lists itself" % where)
                elif other not in index:
                    errors.append("%s: `related` id %r does not resolve to a registered artifact"
                                  % (where, other))
                elif not reg.private and index[other][0].private:
                    errors.append("%s: `related` id %r points into a private overlay; a "
                                  "tracked record may not name a private artifact" % (where, other))

        visibility = merged.get("visibility")
        if reg.private and visibility not in ("private", "redacted"):
            errors.append("%s: an overlay record must be `private` or `redacted`, got %r"
                          % (where, visibility))
        if not reg.private and visibility == "private":
            errors.append("%s: a `private` record belongs in a gitignored "
                          "<agent>/.private/memory-inventory.yaml overlay, not the tracked registry"
                          % where)
        if atype == "private_memory" and visibility not in ("private", "redacted"):
            errors.append("%s: type `private_memory` requires visibility private or redacted, got %r"
                          % (where, visibility))

        if atype in CEREBRUH_TYPES and merged.get("remediation_policy") == "auto_safe":
            errors.append("%s: %r may not be `auto_safe`; Cerebruh content is read-only from "
                          "C4PO and changes route through its ingest workflow" % (where, atype))

        introduced = merged.get("introduced")
        reviewed = merged.get("review", {}).get("last_reviewed") if isinstance(merged.get("review"), dict) else None

        if record_status(merged) == DRAFT:
            if reviewed is not None:
                errors.append("%s: `status: draft` cannot carry `review.last_reviewed: %s`. "
                              "A bootstrapped stub has not been reviewed; supply a rationale, a "
                              "retirement trigger, and a remediation policy, then set "
                              "`status: reviewed`." % (where, reviewed))
            # A draft may be partially filled on the way to review, but once all
            # three fields the design names as the promotion gate are present it
            # is a record someone forgot to promote, not a stub.
            gate = ("rationale", "retirement_triggers", "remediation_policy")
            if all(merged.get(f) is not None for f in gate):
                errors.append("%s: this record already declares a rationale, retirement "
                              "triggers, and a remediation policy, so it is no longer a stub. "
                              "Set `status: reviewed` or remove the field." % where)
        for field, value in (("introduced", introduced), ("review.last_reviewed", reviewed)):
            if isinstance(value, str) and _is_date(value) and _dt.date.fromisoformat(value) > today:
                errors.append("%s: `%s` is %s, which is in the future" % (where, field, value))
        if (isinstance(introduced, str) and isinstance(reviewed, str)
                and _is_date(introduced) and _is_date(reviewed)
                and _dt.date.fromisoformat(reviewed) < _dt.date.fromisoformat(introduced)):
            errors.append("%s: `review.last_reviewed` (%s) precedes `introduced` (%s)"
                          % (where, reviewed, introduced))

    return errors


def _redact(message: str, artifacts: dict) -> str:
    """Strip private ids and paths out of a schema error before it is printed."""
    out = message
    for aid in artifacts:
        out = out.replace(aid, "<private-id>")
    return re.sub(r"'[^']*/[^']*'", "'<private-path>'", out)


# --------------------------------------------------------------------------
# Discovery (migration step 2)
# --------------------------------------------------------------------------
#
# Read-only by construction. Everything below stats files, reads them, and
# resolves symlinks; nothing writes, moves, regenerates, or repairs a
# discovered artifact. Remediation is migration step 7, behind `--apply`.
#
# Coverage is measured, never enforced: `discover` reports how many artifacts
# are unregistered but exits 0 regardless, because the design gates the LINT.md
# coverage rule on the inventory first reaching 100% (migration step 4) so the
# workspace is never knowingly red during migration.

# Whole subtrees excluded, as workspace-relative prefixes. The design requires
# an explicit list rather than a heuristic, so anything left out of the
# inventory is left out on the record and with a reason.
EXCLUDED_PREFIXES = (
    ("bernard", "inert exhibit; bernard/CLAUDE.md forbids executing or adopting it"),
    ("repos", "independent git repositories, each governed by its own AGENTS.md"),
    ("tmp", "shared scratch space; transient by construction"),
    ("cerebruh/ingest", "staging area for material that is not yet knowledge"),
    (".git", "version-control internals"),
    (".githooks", "executable hooks, not memory"),
    (".obsidian", "per-machine editor state"),
    (".tmp.drivedownload", "Google Drive sync scratch"),
    (".tmp.driveupload", "Google Drive sync scratch"),
)

# Directory basenames excluded wherever they appear. `parent_suffix` narrows a
# name that is only noise in one location, so a future `reports/` of hand-written
# material elsewhere is not silently swallowed.
EXCLUDED_DIR_NAMES = (
    ("node_modules", None, "vendored dependencies"),
    ("dist", None, "build output"),
    ("build", None, "build output"),
    ("__pycache__", None, "bytecode cache"),
    ("logs", None, "transient run logs"),
    ("log", None, "transient run logs"),
    ("state", None, "scheduler state; derived, never authoritative"),
    (".private.example", None, "synthetic public template, not a live artifact"),
    (".cc-writes", None, "harness write ledger"),
    ("worktrees", ".claude", "ephemeral agent checkouts"),
    ("reports", ".claude/scheduled", "generated reports"),
    ("last30days-raw", ".claude/scheduled", "generated report input"),
)

# Noise: never memory, wherever it is found. Checked before everything else, so
# a .DS_Store inside a Cerebruh raw/ directory or a skill package is discarded
# rather than promoted to a source or a package companion.
NOISE_NAMES = (
    ("BACKLOG.md", "work queue, not durable memory"),
    (".gitkeep", "directory placeholder"),
    (".DS_Store", "OS noise"),
    ("settings.json", "harness configuration"),
    ("settings.local.json", "harness configuration"),
)
NOISE_PATTERNS = (
    (r"_bak_\d", "hand-made backup"),
    (r"\.(bak|orig|swp|log|pyc)$", "backup, scratch, or generated output"),
    (r"^\.credentials", "credential material"),
)

# Content-shaped skips. These fire only after noise and companion resolution, so
# a helper script inside a skill package stays with the package.
SKIPPED_PATTERNS = (
    (r"\.example(\.[a-z]+)?$", "synthetic public template"),
    (r"^\.env", "environment file; secrets, not memory"),
    (r"^\.(gitignore|gitattributes|gitleaks\.toml|editorconfig)$", "repository configuration"),
    (r"\.(sh|py|zsh|bash|rb|js|ts)$", "executable code, not memory"),
    (r"\.(json|ya?ml|tsv|toml|ndjson|jsonl)$",
     "machine-maintained structured data: an agent's domain index or tool state, not memory"),
)

# Structured-data files that ARE memory and must survive the skip above. This
# inventory's own registry and schema are durable policy; without an exemption
# the rule that discards an agent's schemaVersion-bearing data index would also
# discard the file that governs the inventory. Listed individually so each
# exemption is a decision rather than a pattern that could quietly widen.
SELF_GOVERNING_PATHS = frozenset({
    "MEMORY-INVENTORY.yaml",
    "MEMORY-INVENTORY.schema.json",
})

# Formats an agent reads as domain data — a resume, a contract, a scan — rather
# than as instruction, procedure, or ingested knowledge. Exempt under a
# Cerebruh `raw/` directory, where exactly these formats are knowledge sources.
DOCUMENT_SUFFIXES = (
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".pptx", ".txt", ".rtf",
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".zip", ".tsv",
)
RAW_SOURCE_RE = r"^cerebruh/wikis/[^/]+/raw/"

# Explicitly private locations, mirroring the .gitignore rules that keep them
# out of the public repository. A private artifact is discovered and counted,
# but its path is withheld from every report unless `--show-private` is passed
# (design principle 5).
PRIVATE_PATTERNS = (
    r"(^|/)\.private/",
    r"(^|/)CLAUDE\.local\.md$",
    r"(^|/)\.claude/rules/[^/]*\.local\.md$",
    r"(^|/)\.agents/skills/[^/]*\.local/",
)
# Gitignored artifacts that carry an agent's confidential domain data but do not
# live under `.private/`. Listed individually so each entry is a decision.
PRIVATE_PATHS = frozenset({
    "warren-bot-fett/PORTFOLIO.md",
    "mrs-beast/.claude/commands/ai-week-image-prompt.md",
    "mrs-beast/.claude/scheduled/mrs-beast-ai-week-image-prompt.prompt",
})

# The per-agent overlay registry itself. It is the private half of this
# inventory, not an artifact the inventory governs, so it is counted apart.
OVERLAY_BASENAME = "memory-inventory.yaml"

CODEX_MANIFEST = "skills/.theborg-managed-skills.tsv"


def _is_private(rel: str) -> bool:
    if rel in PRIVATE_PATHS:
        return True
    return any(re.search(pat, rel) for pat in PRIVATE_PATTERNS)


def _exclusion_reason(rel: str, name: str, parent: str):
    for prefix, reason in EXCLUDED_PREFIXES:
        if rel == prefix:
            return reason
    for dname, parent_suffix, reason in EXCLUDED_DIR_NAMES:
        if name != dname:
            continue
        if parent_suffix is None or parent == parent_suffix or parent.endswith("/" + parent_suffix):
            return reason
    return None


def _noise_reason(name: str):
    for sname, reason in NOISE_NAMES:
        if name == sname:
            return reason
    for pattern, reason in NOISE_PATTERNS:
        if re.search(pattern, name):
            return reason
    return None


def _skip_reason(rel: str, name: str):
    # A Cerebruh raw capture is a knowledge_source whatever its format, so no
    # format-based skip may fire inside one.
    if re.match(RAW_SOURCE_RE, rel):
        return None
    if rel in SELF_GOVERNING_PATHS:
        return None
    for pattern, reason in SKIPPED_PATTERNS:
        if re.search(pattern, name):
            return reason
    if name.lower().endswith(DOCUMENT_SUFFIXES):
        return "domain document or media the agent works on, not memory"
    if rel.split("/")[-2:-1] == ["scheduled-tasks"]:
        # The launchd registration table names the jobs a prompt runs under. It
        # is the runner dependency the taxonomy folds into the scheduled_prompt
        # audit unit, not an instruction of its own.
        return "launchd registration table; a scheduled prompt's runner dependency"
    return None


def walk_workspace(root: str):
    """Yield (relative paths, excluded directories) for the in-scope tree.

    Directory symlinks are never followed: `repos/waiq/.claude/commands` points
    back at the workspace's own command directory, and following it would
    inventory every workspace command a second time under a repo path.
    """
    files, excluded = [], []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        keep = []
        for name in sorted(dirnames):
            rel = "%s/%s" % (rel_dir, name) if rel_dir else name
            if os.path.islink(os.path.join(dirpath, name)):
                excluded.append((rel, "directory symlink; its target is inventoried at its own path"))
                continue
            reason = _exclusion_reason(rel, name, rel_dir)
            if reason:
                excluded.append((rel, reason))
            else:
                keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            files.append(("%s/%s" % (rel_dir, name)) if rel_dir else name)
    return files, excluded


def is_candidate(rel: str) -> bool:
    """Is this path in a location where a durable memory artifact can live?

    Bounds what "unclassified" can mean. Application code, agent data files, and
    scripts are out of scope entirely; anything inside a memory-bearing location
    that no classifier claims is reported so the gap is visible rather than
    silently absent.
    """
    parts = rel.split("/")
    name = parts[-1]
    # cerebruh/template/AGENTS.md is nested three deep and is the canonical
    # source every sub-wiki symlink points at, so instruction files and their
    # wrappers are candidates at any depth.
    if name in ("AGENTS.md", "CLAUDE.md", "CLAUDE.local.md"):
        return True
    if len(parts) == 1:
        return True                                     # workspace-root file
    if len(parts) == 2 and parts[1].endswith(".md"):
        return True                                     # agent-level document
    if any(p in (".claude", ".agents", ".private") for p in parts[:-1]):
        return True
    return rel.startswith("cerebruh/wikis/")


def _scope_of(rel: str, marker: str) -> str:
    """Directory that owns a `<scope>/<marker>/...` path; '.' for the workspace."""
    head = rel.split("/" + marker + "/")[0] if ("/" + marker + "/") in rel else ""
    if rel.startswith(marker + "/"):
        return "."
    return head or "."


def _join(scope: str, tail: str) -> str:
    return tail if scope == "." else "%s/%s" % (scope, tail)


def _import_target(root: str, rel: str):
    """Resolve a `@path` Claude import wrapper to a workspace-relative path."""
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8") as fh:
            first = fh.readline().strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not first.startswith("@"):
        return None
    target = first[1:].strip()
    base = os.path.dirname(rel)
    return os.path.normpath(os.path.join(base, target)).replace(os.sep, "/")


def _symlink_target(root: str, rel: str):
    """Workspace-relative target of a symlinked file, or None when it escapes.

    Resolves the link itself rather than realpath()ing the whole chain: on macOS
    the workspace may sit under a symlinked ancestor, and resolving that too
    would make every in-tree target look like it points outside the workspace.
    A target that is itself a symlink still has its own record, so one hop is
    the right granularity.
    """
    try:
        raw = os.readlink(os.path.join(root, rel))
    except OSError:
        return None
    if os.path.isabs(raw):
        try:
            inside = os.path.relpath(os.path.realpath(raw), os.path.realpath(root))
        except ValueError:
            return None
    else:
        inside = os.path.normpath(os.path.join(os.path.dirname(rel), raw))
    inside = inside.replace(os.sep, "/")
    return None if inside == ".." or inside.startswith("../") else inside


def classify(root: str, rel: str):
    """Map one workspace-relative path onto the design's artifact taxonomy.

    Returns an artifact dict, or None when nothing in the taxonomy claims it.
    """
    parts = rel.split("/")
    name = parts[-1]
    private = _is_private(rel)

    def art(atype, canonicality="canonical", canonical=None, canonical_root="borg_root", note=None):
        return {
            "path": rel,
            "path_root": "borg_root",
            "type": atype,
            "canonicality": canonicality,
            "visibility": "private" if private else "public",
            "canonical_path": canonical,
            "canonical_path_root": canonical_root if canonical else None,
            "note": note,
        }

    # The registry and its schema govern this inventory and are themselves
    # durable policy; leaving them out would make the inventory unable to
    # describe its own governance.
    if rel in ("MEMORY-INVENTORY.yaml", "MEMORY-INVENTORY.schema.json"):
        return art("policy_registry")

    # Always-on instructions and their wrappers. A symlinked AGENTS.md is a
    # mirror of the canonical file it points at, not a second canonical source.
    if name == "AGENTS.md":
        if os.path.islink(os.path.join(root, rel)):
            target = _symlink_target(root, rel)
            return art("compatibility_wrapper", "mirror", target,
                       note="symlink" if target else "symlink outside the workspace")
        return art("always_on_instruction")
    if name in ("CLAUDE.md", "CLAUDE.local.md"):
        return art("compatibility_wrapper", "mirror", _import_target(root, rel),
                   note="@import wrapper")

    # Scoped rules and the Codex stubs generated from them.
    if len(parts) >= 3 and parts[-3:-1] == [".claude", "rules"] and name.endswith(".md"):
        return art("scoped_rule")
    if len(parts) >= 4 and parts[-4:-2] == [".agents", "skills"] and name == "SKILL.md":
        # The stub directory is named for the rule file minus `.md`, including a
        # gitignored rule's `.local` suffix, so the canonical name needs no
        # special-casing: `<stub>.md` is always the rule.
        return art("generated_rule_bridge", "generated",
                   _join(_scope_of(rel, ".agents"),
                         ".claude/rules/%s.md" % parts[-2]))

    # Hand-authored skills and commands.
    if len(parts) >= 4 and parts[-4:-2] == [".claude", "skills"] and name == "SKILL.md":
        return art("procedural_skill")
    if len(parts) >= 3 and parts[-3:-1] == [".claude", "commands"] and name.endswith(".md"):
        return art("command")

    # Scheduled prompts. Their `.settings.json`/`.conf` siblings are attached to
    # the prompt in a later pass: the design's audit unit is the prompt plus its
    # configuration and runner, not three independent memories.
    # Matched on the `scheduled/` directory alone rather than `.claude/scheduled`:
    # an agent may keep a private job under `.private/scheduled/`, and it is the
    # same kind of artifact.
    if len(parts) >= 2 and parts[-2] == "scheduled" and name.endswith(".prompt"):
        return art("scheduled_prompt")

    # Cerebruh. Read-only from C4PO; discovery only looks.
    if rel == "cerebruh/wikis/index.md":
        return art("retrieval_index")
    if rel.startswith("cerebruh/wikis/") and len(parts) >= 5:
        if parts[3] == "wiki" and name.endswith(".md"):
            return art("retrieval_index" if name == "index.md" else "knowledge_page")
        if parts[3] == "raw":
            return art("knowledge_source", "source")

    # Durable private notes. Restricted to Markdown deliberately: the other
    # things that live under `.private/` are domain documents and runner
    # scripts, which the skip rules above have already set aside.
    if ".private" in parts[:-1] and name.endswith(".md"):
        return art("private_memory")

    # Remaining workspace-root and agent-level documents are the policy layer:
    # LINT.md, MCP.md, SECURITY.md, the ingest/audit procedures, README.
    if len(parts) <= 2 and name.endswith(".md"):
        if "DESIGN" in name or name.startswith("ADR-"):
            return art("design_decision")
        return art("policy_registry")

    return None


def discover_codex_bridges(codex_home: str, root: str):
    """Read the command bridge's manifest to inventory generated Codex skills.

    The manifest is the only complete list: the bridge writes into
    $CODEX_HOME/skills alongside skills it does not own, and nothing in the
    checkout otherwise reveals that these files exist.
    """
    manifest = os.path.join(codex_home, CODEX_MANIFEST)
    artifacts, problems = [], []
    if not os.path.isfile(manifest):
        return artifacts, ["codex bridge manifest not found at %s; generated command "
                           "bridges were not inventoried" % CODEX_MANIFEST]
    try:
        with open(manifest, "r", encoding="utf-8") as fh:
            rows = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return artifacts, ["cannot read the codex bridge manifest: %s" % exc]
    for row in rows:
        if not row.strip():
            continue
        fields = row.split("\t")
        if len(fields) < 2:
            problems.append("malformed manifest row: %r" % row)
            continue
        skill, source = fields[0], fields[1]
        try:
            canonical = os.path.relpath(source, root).replace(os.sep, "/")
        except ValueError:
            canonical = None
        if canonical is not None and canonical.startswith("../"):
            canonical = None
        rel = "skills/%s/SKILL.md" % skill
        artifacts.append({
            "path": rel,
            "path_root": "codex_home",
            "type": "generated_command_bridge",
            "canonicality": "generated",
            "visibility": "private" if canonical and _is_private(canonical) else "public",
            "canonical_path": canonical,
            "canonical_path_root": "borg_root" if canonical else None,
            "note": "from %s" % CODEX_MANIFEST,
        })
    return artifacts, problems


def discover_auto_memory(home: str, root: str):
    """Inventory the harness Auto Memory keyed to this workspace.

    Claude Code derives the directory name from the project root, so the path is
    computed rather than configured. Every record here is private.
    """
    slug = os.path.abspath(root).replace("/", "-")
    base = os.path.join(home, ".claude", "projects", slug, "memory")
    artifacts = []
    if not os.path.isdir(base):
        return artifacts
    rel_base = os.path.relpath(base, home).replace(os.sep, "/")
    for name in sorted(os.listdir(base)):
        if not name.endswith(".md") or not os.path.isfile(os.path.join(base, name)):
            continue
        artifacts.append({
            "path": "%s/%s" % (rel_base, name),
            "path_root": "home",
            "type": "private_memory",
            "canonicality": "canonical",
            "visibility": "private",
            "canonical_path": None,
            "canonical_path_root": None,
            "note": "harness Auto Memory for this workspace",
        })
    return artifacts


def _measure(abs_path: str):
    """Byte and line counts. Never decodes: raw sources may be binary."""
    try:
        size = os.path.getsize(abs_path)
        lines = 0
        with open(abs_path, "rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                lines += chunk.count(b"\n")
        return size, lines
    except OSError:
        return None, None


def discover(root: str, codex_home=None, home=None):
    """Enumerate every in-scope durable memory artifact. Read-only."""
    root = os.path.abspath(root)
    files, excluded = walk_workspace(root)

    artifacts, skipped, unclassified, overlays, notes = [], [], [], [], []
    companions = []
    for rel in files:
        name = rel.split("/")[-1]
        if not is_candidate(rel):
            continue
        # The overlay registry is the private half of this inventory, not an
        # artifact the inventory governs, so it is counted apart from both.
        reason = _noise_reason(name)
        if reason:
            skipped.append((rel, reason))
            continue
        if ".private" in rel.split("/")[:-1] and name == OVERLAY_BASENAME:
            overlays.append(rel)
            continue
        owner = companion_owner(rel)
        if owner is not None:
            companions.append((rel, owner))
            continue
        reason = _skip_reason(rel, name)
        if reason:
            skipped.append((rel, reason))
            continue
        record = classify(root, rel)
        if record is None:
            unclassified.append(rel)
            continue
        artifacts.append(record)

    if codex_home:
        bridges, problems = discover_codex_bridges(codex_home, root)
        artifacts.extend(bridges)
        notes.extend(problems)
    if home:
        artifacts.extend(discover_auto_memory(home, root))

    roots = {"borg_root": root, "home": home, "codex_home": codex_home}
    for record in artifacts:
        base = roots.get(record["path_root"])
        abs_path = os.path.join(base, record["path"]) if base else None
        record["exists"] = bool(abs_path and os.path.exists(abs_path))
        record["bytes"], record["lines"] = _measure(abs_path) if record["exists"] else (None, None)

    _attach_companions(artifacts, companions, unclassified)
    pairs = _resolve_pairs(artifacts)

    return {
        "root": root,
        "artifacts": artifacts,
        "excluded": excluded,
        "skipped": skipped,
        "unclassified": unclassified,
        "overlays": overlays,
        "pairs": pairs,
        "notes": notes,
    }


def companion_owner(rel: str):
    """Path of the artifact this file belongs to, or None if it stands alone.

    The taxonomy's audit unit for a scheduled prompt is the prompt plus its
    configuration and runner dependency, and for a skill it is the whole
    package. So a `.settings.json` beside a prompt, or a reference file inside a
    skill directory, is folded into its owner rather than inventoried as a
    memory of its own.
    """
    parts = rel.split("/")
    if len(parts) >= 2 and parts[-2] == "scheduled":
        for suffix in (".settings.json", ".conf"):
            if parts[-1].endswith(suffix):
                return rel[: -len(suffix)] + ".prompt"
    if parts[-1] != "SKILL.md":
        for marker in (".claude/skills", ".agents/skills"):
            head, sep, tail = rel.partition(marker + "/")
            if sep and "/" in tail:
                return "%s%s/%s/SKILL.md" % (head, marker, tail.split("/")[0])
    return None


def _attach_companions(artifacts, companions, unclassified):
    """Hang each companion off its owner; an orphan is reported, not dropped."""
    by_path = {a["path"]: a for a in artifacts if a["path_root"] == "borg_root"}
    for record in artifacts:
        record.setdefault("companions", [])
    for rel, owner_path in companions:
        owner = by_path.get(owner_path)
        if owner is None:
            unclassified.append(rel)
        else:
            owner["companions"].append(rel)


def _resolve_pairs(artifacts):
    """Match every generated bridge and mirror to the canonical artifact it
    derives from. Unresolved pairs are the finding this step exists to surface:
    a wrapper whose canonical source is gone is a memory that points at nothing.
    """
    known = {(a["path_root"], a["path"]) for a in artifacts}
    resolved, dangling = 0, []
    for record in artifacts:
        if record["canonicality"] not in DERIVED_CANONICALITY:
            continue
        target = record.get("canonical_path")
        if target and (record.get("canonical_path_root", "borg_root"), target) in known:
            record["canonical_resolved"] = True
            resolved += 1
        else:
            record["canonical_resolved"] = False
            dangling.append((record["path_root"], record["path"], target,
                             record["visibility"]))
    return {"resolved": resolved, "dangling": dangling}


def join_registry(found, registries):
    """Match discovered artifacts against declared records, both directions.

    Counting only; the coverage rule is migration step 4 and is not enforced
    here (design: do not run a knowingly red audit during migration).
    """
    declared = {}
    for reg in registries:
        for aid, record in reg.artifacts.items():
            if not isinstance(record, dict):
                continue
            merged = apply_defaults(record, reg.defaults)
            path = merged.get("path")
            if isinstance(path, str):
                declared[(merged.get("path_root", "borg_root"), path)] = (aid, reg)

    matched = set()
    unregistered = []
    for record in found:
        key = (record["path_root"], record["path"])
        hit = declared.get(key)
        record["registered_as"] = hit[0] if hit else None
        if hit:
            matched.add(key)
        else:
            unregistered.append(record)

    missing = []
    for key, (aid, reg) in sorted(declared.items()):
        if key in matched:
            continue
        missing.append((aid, key[0], key[1], reg.private))
    return {"unregistered": unregistered, "missing": missing, "declared": len(declared)}


def _counted(rows, key):
    tally = {}
    for row in rows:
        tally[row[key]] = tally.get(row[key], 0) + 1
    return sorted(tally.items())


def format_report(result, join, show_private: bool):
    """Human-readable discovery report. Private paths appear only under
    --show-private; the aggregate counts are always safe to print or email."""
    out = []
    arts = result["artifacts"]
    public = [a for a in arts if a["visibility"] == "public"]
    private = [a for a in arts if a["visibility"] != "public"]

    out.append("Memory artifact discovery — read-only (migration step 2)")
    out.append("Root: %s" % result["root"])
    out.append("")
    out.append("Discovered %d artifact(s): %d public, %d private."
               % (len(arts), len(public), len(private)))
    out.append("")

    out.append("By type")
    for atype in sorted({a["type"] for a in arts}):
        pub = sum(1 for a in public if a["type"] == atype)
        priv = sum(1 for a in private if a["type"] == atype)
        if show_private:
            out.append("  %-26s %4d" % (atype, pub + priv))
        else:
            out.append("  %-26s %4d%s" % (atype, pub,
                                          " (+%d private)" % priv if priv else ""))
    out.append("")

    # Counts, not paths, so this block is printable in every mode.
    out.append("By canonicality")
    for value, count in _counted(arts, "canonicality"):
        out.append("  %-26s %4d" % (value, count))
    out.append("")

    total_bytes = sum(a["bytes"] or 0 for a in arts)
    out.append("Measured %s bytes across %d file(s); %d artifact(s) missing on disk."
               % ("{:,}".format(total_bytes), sum(1 for a in arts if a["exists"]),
                  sum(1 for a in arts if not a["exists"])))
    out.append("")

    pairs = result["pairs"]
    out.append("Canonical/mirror pairs")
    out.append("  resolved                   %4d" % pairs["resolved"])
    out.append("  unresolved                 %4d" % len(pairs["dangling"]))
    for proot, path, target, visibility in pairs["dangling"]:
        if visibility != "public" and not show_private:
            out.append("    <private artifact>: canonical source not found")
        else:
            out.append("    %s:%s -> %s" % (proot, path, target or "(unresolved target)"))
    out.append("")

    out.append("Coverage against MEMORY-INVENTORY.yaml (measured, not enforced)")
    out.append("  declared records           %4d" % join["declared"])
    out.append("  registered                 %4d" % sum(1 for a in arts if a["registered_as"]))
    out.append("  UNREGISTERED               %4d" % len(join["unregistered"]))
    out.append("  MISSING_ARTIFACT           %4d" % len(join["missing"]))
    for aid, proot, path, is_private in join["missing"]:
        if is_private and not show_private:
            out.append("    <private record>: declared path no longer exists")
        else:
            out.append("    %s -> %s:%s" % (aid, proot, path))
    out.append("")
    out.append("  The LINT.md coverage rule stays unwritten until the inventory reaches")
    out.append("  100%; this run measures the gap rather than failing on it.")
    out.append("")

    out.append("Exclusions applied (%d directory/ies)" % len(result["excluded"]))
    seen_reasons = {}
    for path, reason in result["excluded"]:
        seen_reasons.setdefault(reason, []).append(path)
    for reason in sorted(seen_reasons):
        paths = seen_reasons[reason]
        sample = ", ".join(paths[:4]) + (", …" if len(paths) > 4 else "")
        out.append("  %-3d %s" % (len(paths), reason))
        out.append("      %s" % sample)
    out.append("")

    if result["skipped"]:
        out.append("Skipped as non-memory (%d file(s))" % len(result["skipped"]))
        skip_reasons = {}
        for path, reason in result["skipped"]:
            skip_reasons.setdefault(reason, 0)
            skip_reasons[reason] += 1
        for reason, count in sorted(skip_reasons.items()):
            out.append("  %-3d %s" % (count, reason))
        out.append("")

    unclassified = result["unclassified"]
    shown = [p for p in unclassified if show_private or not _is_private(p)]
    hidden = len(unclassified) - len(shown)
    out.append("Unclassified candidates (%d)" % len(unclassified))
    if not unclassified:
        out.append("  none — every file in a memory-bearing location was classified")
    for path in shown:
        out.append("  %s" % path)
    if hidden:
        out.append("  %d private path(s) withheld; rerun with --show-private" % hidden)
    out.append("")

    out.append("Private overlays found: %d" % len(result["overlays"]))
    for path in result["overlays"]:
        out.append("  %s" % (path if show_private else "<private overlay>"))
    for note in result["notes"]:
        if _is_private(note) and not show_private:
            continue
        out.append("note: %s" % note)
    return "\n".join(out)


def _public_json(result, join, show_private: bool):
    """JSON view. Without --show-private this is safe to write to a tracked or
    emailed destination: private records collapse to counts by type."""
    arts = result["artifacts"]
    if show_private:
        artifacts = arts
        redacted = []
    else:
        artifacts = [a for a in arts if a["visibility"] == "public"]
        tally = {}
        for a in arts:
            if a["visibility"] != "public":
                tally[a["type"]] = tally.get(a["type"], 0) + 1
        redacted = sorted(tally.items())
    return {
        "root": result["root"],
        "read_only": True,
        "coverage_enforced": False,
        "artifacts": artifacts,
        "private_counts_by_type": [{"type": t, "count": c} for t, c in redacted],
        "excluded": [{"path": p, "reason": r} for p, r in result["excluded"]
                     if show_private or not _is_private(p)],
        # Paths only; the redacted counts below keep a private skip visible as a
        # number without naming the file, which is what may enter an email.
        "skipped": [{"path": p, "reason": r} for p, r in result["skipped"]
                    if show_private or not _is_private(p)],
        "skipped_private_count": 0 if show_private else
                                 sum(1 for p, _ in result["skipped"] if _is_private(p)),
        "unclassified": [p for p in result["unclassified"]
                         if show_private or not _is_private(p)],
        "overlays": len(result["overlays"]),
        "pairs": {"resolved": result["pairs"]["resolved"],
                  "unresolved": len(result["pairs"]["dangling"])},
        "coverage": {
            "declared": join["declared"],
            "registered": sum(1 for a in arts if a["registered_as"]),
            "unregistered": len(join["unregistered"]),
            "missing": len(join["missing"]),
        },
        "notes": result["notes"] if show_private else
                 [n for n in result["notes"] if not _is_private(n)],
    }

# --------------------------------------------------------------------------
# YAML emitter (the subset the reader above accepts, and nothing more)
# --------------------------------------------------------------------------
#
# Deliberately narrow and deliberately paired with the reader: `bootstrap`
# round-trips everything it emits back through `load_yaml` and refuses to write
# if the parse does not reproduce the records exactly. A writer that can emit
# something its own reader mis-parses would corrupt the registry silently.

# A plain scalar is safe only if it cannot be read as a number, a boolean, a
# null, or a key. Spaces are excluded too: the registry quotes paths containing
# them, and matching that convention keeps the file uniform.
_PLAIN_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_YAML_WORDS = frozenset({"null", "true", "false", "yes", "no", "on", "off", "~"})


def yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if (_PLAIN_SAFE.match(text)
            and text.lower() not in _YAML_WORDS
            and not re.fullmatch(r"[+-]?\d+(\.\d+)?", text)
            and "#" not in text):
        return text
    escaped = (text.replace("\\", "\\\\").replace('"', '\\"')
                   .replace("\n", "\\n").replace("\t", "\\t"))
    return '"%s"' % escaped


# Emission order. Identity first, then the mechanical facts, then review state.
# `_comments` is metadata for the human reader and is never a field.
RECORD_FIELD_ORDER = (
    "path", "path_root", "type", "status", "owner", "scope", "visibility",
    "canonicality", "canonical_ref", "rationale", "introduced", "provenance",
    "load_mode", "consumers", "risk", "review", "success_signals",
    "retirement_triggers", "remediation_policy", "related",
)

_FLOW_WIDTH = 72


def emit_field(key: str, value, pad: str, note=None):
    """Render one `key: value` as YAML lines, recursing into nested mappings.

    Raises rather than guessing when handed a shape this subset cannot write —
    a list of mappings, say. Falling back to `str()` there would emit something
    the reader parses as a scalar, which is exactly the silent corruption
    `verify_roundtrip` exists to catch, and it is cheaper to refuse than to
    write a registry and discover the damage on the next read.
    """
    suffix = "    # %s" % note if note else ""
    if isinstance(value, dict):
        lines = ["%s%s:%s" % (pad, key, suffix)]
        for sub_key in sorted(value):
            lines.extend(emit_field(sub_key, value[sub_key], pad + "  "))
        return lines
    if isinstance(value, list):
        if not value:
            return ["%s%s: []%s" % (pad, key, suffix)]
        if any(isinstance(v, (dict, list)) for v in value):
            raise YamlSubsetError(
                "cannot emit %r: this writer supports only sequences of scalars" % key)
        rendered = [yaml_scalar(v) for v in value]
        flow = "[%s]" % ", ".join(rendered)
        if len(pad) + len(key) + 2 + len(flow) <= _FLOW_WIDTH:
            return ["%s%s: %s%s" % (pad, key, flow, suffix)]
        return (["%s%s:%s" % (pad, key, suffix)]
                + ["%s  - %s" % (pad, r) for r in rendered])
    return ["%s%s: %s%s" % (pad, key, yaml_scalar(value), suffix)]


def emit_record(aid: str, record: dict, indent: str = "  "):
    """Render one record as YAML lines. Ordered, so output is reproducible."""
    comments = record.get("_comments") or {}
    lines = ["%s%s:" % (indent, aid)]
    pad = indent + "  "
    for key in RECORD_FIELD_ORDER:
        if key not in record:
            continue
        lines.extend(emit_field(key, record[key], pad, comments.get(key)))
    unknown = [k for k in record
               if k != "_comments" and k not in RECORD_FIELD_ORDER]
    if unknown:
        raise YamlSubsetError(
            "cannot emit %r: field(s) %s are missing from RECORD_FIELD_ORDER, so "
            "they would be dropped silently" % (aid, ", ".join(sorted(unknown))))
    return lines


def strip_comments(record: dict) -> dict:
    return {k: v for k, v in record.items() if k != "_comments"}


# --------------------------------------------------------------------------
# Mechanical bootstrap (migration step 3, first half)
# --------------------------------------------------------------------------
#
# Emits one `status: draft` record per discovered-but-unregistered artifact,
# populating ONLY what the tree determines: path, class, canonicality and the
# canonical it derives from, owner and scope, visibility, how it enters context,
# and the date it first appeared. Rationale, provenance, risk, success signals,
# retirement triggers, and remediation policy are left out on purpose — those
# are the human half of step 3, and inventing plausible-looking text for them
# would destroy the very distinction the `status` flag exists to preserve.

# How each artifact class enters context and who reads it. Derived from the
# design's taxonomy and cadence tables, so a draft's context cost and review
# schedule are stated rather than assumed. A class-uniform value that matches
# the registry's own `defaults:` block is omitted from the emitted record;
# anything that differs is written out explicitly.
CLASS_DERIVATION = {
    "always_on_instruction": {
        "canonicality": "canonical", "load_mode": "always",
        "consumers": ["claude-code", "codex", "claude-desktop"],
        "review_cadence": "monthly", "review_method": ["semantic", "best_practice"],
    },
    "compatibility_wrapper": {
        "canonicality": "mirror", "load_mode": "always",
        "consumers": ["claude-code"],
        "review_cadence": "each_audit", "review_method": ["drift_only"],
    },
    "scoped_rule": {
        "canonicality": "canonical", "load_mode": "path_triggered",
        "consumers": ["claude-code", "codex"],
        "review_cadence": "quarterly", "review_method": ["semantic", "usage"],
    },
    "generated_rule_bridge": {
        "canonicality": "generated", "load_mode": "explicit",
        "consumers": ["codex"],
        "review_cadence": "each_audit", "review_method": ["drift_only"],
    },
    "procedural_skill": {
        "canonicality": "canonical", "load_mode": "explicit",
        "consumers": ["claude-code"],
        "review_cadence": "quarterly", "review_method": ["semantic", "usage"],
    },
    "command": {
        "canonicality": "canonical", "load_mode": "explicit",
        "consumers": ["claude-code"],
        "review_cadence": "quarterly", "review_method": ["semantic", "usage"],
    },
    "generated_command_bridge": {
        "canonicality": "generated", "load_mode": "explicit",
        "consumers": ["codex"],
        "review_cadence": "each_audit", "review_method": ["drift_only"],
    },
    "scheduled_prompt": {
        "canonicality": "canonical", "load_mode": "scheduled",
        "consumers": ["claude-code", "launchd", "run-scheduled-task.sh"],
        "review_cadence": "quarterly", "review_method": ["mechanical", "semantic"],
    },
    "knowledge_page": {
        "canonicality": "canonical", "load_mode": "retrieved",
        "consumers": ["claude-code", "codex", "claude-desktop"],
        "review_cadence": "rolling_annual",
        "review_method": ["semantic", "source_verification"],
    },
    "knowledge_source": {
        "canonicality": "source", "load_mode": "source_only",
        "consumers": ["cerebruh-ingest"],
        "review_cadence": "monthly",
        "review_method": ["mechanical", "source_verification"],
    },
    "private_memory": {
        "canonicality": "canonical", "load_mode": "explicit",
        "consumers": ["claude-code"],
        "review_cadence": "quarterly", "review_method": ["mechanical", "semantic"],
    },
    "policy_registry": {
        "canonicality": "canonical", "load_mode": "explicit",
        "consumers": ["claude-code", "codex", "claude-desktop"],
        "review_cadence": "monthly", "review_method": ["mechanical", "semantic"],
    },
    "retrieval_index": {
        "canonicality": "canonical", "load_mode": "retrieved",
        "consumers": ["claude-code", "codex", "claude-desktop"],
        "review_cadence": "quarterly", "review_method": ["mechanical", "semantic"],
    },
    "design_decision": {
        "canonicality": "canonical", "load_mode": "explicit",
        "consumers": ["claude-code", "codex"],
        "review_cadence": "annual", "review_method": ["semantic"],
    },
}

# The Auto Memory index is loaded every session; the individual memories beside
# it surface on recall. Same class, different context cost, and the path is
# enough to tell them apart, so it stays a derivation rather than a judgment.
AUTO_MEMORY_INDEX = "MEMORY.md"


def derive_owner_scope(rel: str, path_root: str, canonical_path):
    """Accountable owner and scope for a path. Directory layout is the org chart.

    A bridge under CODEX_HOME and a memory under HOME have no workspace
    directory to inherit from: the bridge takes the owner of the artifact it
    mirrors, and Auto Memory keyed to the repository root is shared by every
    agent, so it belongs to the workspace.
    """
    if path_root != "borg_root":
        if canonical_path:
            return derive_owner_scope(canonical_path, "borg_root", None)
        return "workspace", "workspace"
    parts = rel.split("/")
    if rel.startswith("cerebruh/wikis/") and len(parts) >= 3:
        return "cerebruh", "cerebruh/wikis/%s" % parts[2]
    if parts[0] == "cerebruh":
        return "cerebruh", "cerebruh"
    if len(parts) == 1 or parts[0].startswith("."):
        return "workspace", "workspace"
    return parts[0], parts[0]


# Owner of workspace-scoped private records. The design places every overlay at
# `<agent>/.private/memory-inventory.yaml`, and the workspace root is not an
# agent — AGENTS.md puts durable confidential material under the OWNING AGENT's
# `.private/`. C4PO owns this inventory, so workspace-scoped private records go
# there rather than opening a new top-level `.private/` directory.
WORKSPACE_OVERLAY_OWNER = "c4po"


def overlay_path_for(owner: str) -> str:
    """Where a private record for this owner has to live. Never tracked."""
    if owner == "workspace":
        owner = WORKSPACE_OVERLAY_OWNER
    return "%s/.private/%s" % (owner, OVERLAY_BASENAME)


def _slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return out


def make_id(path_root: str, rel: str, taken) -> str:
    """Deterministic, collision-free id for a path.

    Ids are meant to be path-independent so a record survives relocation. A
    bootstrap has nothing but the path to name a record after, so it derives one
    and a human is free to rename it later — that is exactly the churn the
    schema's id rule anticipates.
    """
    stem = rel
    if "." in stem.split("/")[-1]:
        stem = stem.rsplit(".", 1)[0]
    prefix = {"codex_home": "codex-home", "home": "home"}.get(path_root, "")
    slug = _slug("%s-%s" % (prefix, stem) if prefix else stem)
    if len(slug) > 72:
        digest = hashlib.sha1(("%s:%s" % (path_root, rel)).encode("utf-8")).hexdigest()[:7]
        slug = "%s-%s" % (slug[:64].rstrip("-"), digest)
    if len(slug) < 3:
        slug = "artifact-%s" % (slug or "x")
    candidate, n = slug, 1
    while candidate in taken:
        n += 1
        candidate = "%s-%d" % (slug, n)
    return candidate


def git_add_dates(root: str):
    """path -> earliest date git recorded it as added. One pass over history.

    `--follow` would be more accurate across renames but only works one path at
    a time, and this runs over five hundred of them. The earliest add is a
    deterministic lower bound, and the emitted record says which method produced
    the date so a reviewer can tell a git fact from a filesystem guess.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", root, "-c", "core.quotePath=false", "log",
             "--diff-filter=A", "--date=short", "--format=@%ad", "--name-only",
             "--no-renames"],
            capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0:
        return {}
    dates, current = {}, None
    for line in proc.stdout.splitlines():
        if line.startswith("@"):
            current = line[1:].strip()
        elif line.strip() and current:
            # Log runs newest-first, so the last assignment is the earliest add.
            dates[line.strip()] = current
    return dates


def frontmatter_created(abs_path: str):
    """`created:` from YAML frontmatter, which Cerebruh pages and raw captures
    carry and git cannot supply — the wikis are gitignored."""
    try:
        with open(abs_path, "r", encoding="utf-8") as fh:
            if fh.readline().strip() != "---":
                return None
            for _ in range(40):
                line = fh.readline()
                if not line or line.strip() == "---":
                    return None
                match = re.match(r"created:\s*[\"']?(\d{4}-\d{2}-\d{2})", line.strip())
                if match:
                    return match.group(1)
    except (OSError, UnicodeDecodeError):
        return None
    return None


def derive_introduced(record, roots, add_dates, today):
    """(date, how it was derived). Never in the future: the validator rejects
    that, and a Drive-synced mtime can legitimately be skewed forward."""
    base = roots.get(record["path_root"])
    abs_path = os.path.join(base, record["path"]) if base else None

    value, how = None, None
    if abs_path and record["path"].endswith((".md", ".markdown")):
        value = frontmatter_created(abs_path)
        if value:
            how = "frontmatter created:"
    if value is None and record["path_root"] == "borg_root":
        value = add_dates.get(record["path"])
        if value:
            how = "first git add"
    if value is None and abs_path and os.path.exists(abs_path):
        try:
            value = _dt.date.fromtimestamp(os.path.getmtime(abs_path)).isoformat()
            how = "file mtime (untracked; not a history fact)"
        except (OSError, OverflowError, ValueError):
            value = None
    if value is None or not _is_date(value):
        return today.isoformat(), "unknown; defaulted to the bootstrap date"
    if _dt.date.fromisoformat(value) > today:
        return today.isoformat(), "%s, clamped from a future date" % how
    return value, how


def build_draft(record, ids, roots, add_dates, today):
    """One complete `status: draft` record for a discovered artifact.

    Only mechanically derivable fields are populated. Fields that duplicate a
    class default are removed afterwards by `elide_defaults`, which runs only
    for the tracked registry — routing has to see the full record first.
    """
    atype = record["type"]
    derived = CLASS_DERIVATION.get(atype, {})
    private = record["visibility"] != "public"
    owner, scope = derive_owner_scope(record["path"], record["path_root"],
                                      record.get("canonical_path"))

    load_mode = derived.get("load_mode", "explicit")
    if record["path_root"] == "home" and atype == "private_memory":
        load_mode = ("always" if record["path"].endswith("/" + AUTO_MEMORY_INDEX)
                     else "retrieved")

    draft = {
        "path": record["path"],
        "type": atype,
        "status": DRAFT,
        "owner": owner,
        "scope": scope,
        "visibility": "private" if private else "public",
        "canonicality": record["canonicality"],
        "load_mode": load_mode,
        "consumers": list(derived.get("consumers", ["claude-code"])),
        "review": {"last_reviewed": None,
                   "cadence": derived.get("review_cadence", "quarterly"),
                   "method": list(derived.get("review_method", ["mechanical"]))},
        "related": [],
    }
    if record["path_root"] != "borg_root":
        draft["path_root"] = record["path_root"]
    if record["canonicality"] in DERIVED_CANONICALITY:
        target = record.get("canonical_path")
        key = (record.get("canonical_path_root") or "borg_root", target)
        draft["canonical_ref"] = ids.get(key) if target else None

    introduced, how = derive_introduced(record, roots, add_dates, today)
    draft["introduced"] = introduced
    draft["_comments"] = {"introduced": how}
    return draft


def elide_defaults(draft: dict, defaults: dict) -> dict:
    """Drop fields whose value the class default already supplies.

    Only ever applied to tracked records. A private overlay carries no
    `defaults:` block by convention, so its records state every field in full —
    otherwise a class-wide policy could end up written down only in a gitignored
    file. Eliding is safe because `apply_defaults` puts the identical value back
    before validation; the round-trip check in `verify_roundtrip` and the
    validation pass in `cmd_bootstrap` both run on the elided form.
    """
    out = _deep_copy(draft)
    block = defaults.get(draft.get("type")) or {}
    for key, target in DEFAULTABLE.items():
        if key not in block:
            continue
        if len(target) == 1:
            if out.get(target[0]) == block[key]:
                out.pop(target[0], None)
        else:
            outer, inner = target
            nested = out.get(outer)
            if isinstance(nested, dict) and nested.get(inner) == block[key]:
                del nested[inner]
    out["_comments"] = dict(draft.get("_comments") or {})
    return out


BOOTSTRAP_MARKER = (
    "  # ── bootstrapped drafts — mechanically derived, NOT reviewed ───────────"
)
BOOTSTRAP_NOTE = """  #
  # Emitted by `python3 .bin/build-memory-inventory.py bootstrap --write`
  # (migration step 3 of c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md). Every
  # record below is `status: draft`: its identity, ownership, canonicality, and
  # context cost were read off the tree, and no human judgment has been applied.
  #
  # A draft is REGISTERED, NOT REVIEWED. To promote one, add a rationale,
  # provenance, risk, success signals, retirement triggers, and a remediation
  # policy, then set `status: reviewed`. `validate --require-reviewed` is the
  # gate: it fails while any draft remains, so full coverage can never be
  # mistaken for full review.
"""

OVERLAY_HEADER = """# Private memory-inventory overlay — GITIGNORED, NEVER TRACKED
#
# Records for artifacts whose path or rationale is itself sensitive. Validated
# with the same schema as the tracked registry and never merged into any tracked
# output (design principle 5 of c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md):
#
#   python3 .bin/build-memory-inventory.py validate --overlay %s
#
# No `defaults:` block by convention — class-wide policy lives in the tracked
# registry so a private file never becomes the only place it is written down.
# Every record therefore states its fields in full.

version: 1

artifacts:
"""


def plan_bootstrap(root, result, join, registries, today):
    """Draft records grouped by destination file. Pure computation; no writes."""
    roots_by_id = {}
    for reg in registries:
        for aid, record in reg.artifacts.items():
            if not isinstance(record, dict):
                continue
            merged = apply_defaults(record, reg.defaults)
            path = merged.get("path")
            if isinstance(path, str):
                roots_by_id[(merged.get("path_root", "borg_root"), path)] = aid
    taken = set(roots_by_id.values())

    pending = sorted(join["unregistered"],
                     key=lambda r: (r["type"], r["path_root"], r["path"]))
    for record in pending:
        aid = make_id(record["path_root"], record["path"], taken)
        taken.add(aid)
        roots_by_id[(record["path_root"], record["path"])] = aid

    tracked_defaults = {}
    for reg in registries:
        if not reg.private:
            tracked_defaults = reg.defaults
            break

    home = os.path.expanduser("~")
    roots = {"borg_root": root, "home": home,
             "codex_home": os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")}
    add_dates = git_add_dates(root)

    plan, deferred = {}, []
    for record in pending:
        aid = roots_by_id[(record["path_root"], record["path"])]
        draft = build_draft(record, roots_by_id, roots, add_dates, today)
        if draft["canonicality"] in DERIVED_CANONICALITY and not draft.get("canonical_ref"):
            # An orphaned bridge or wrapper: the canonical source it mirrors is
            # gone, or was never in scope. There is no honest mechanical record
            # to write — the schema requires a `canonical_ref` precisely because
            # a derived artifact without one is a finding, not a memory. Whether
            # to delete it or restore its source is a judgment, so it is
            # reported and left UNREGISTERED rather than papered over.
            deferred.append((aid, draft,
                             "orphaned %s: no canonical source to point at" % draft["type"]))
            continue
        if draft["visibility"] == "public":
            destination = "MEMORY-INVENTORY.yaml"
            draft = elide_defaults(draft, tracked_defaults)
        else:
            destination = overlay_path_for(draft["owner"])
        plan.setdefault(destination, []).append((aid, draft))
    for records in plan.values():
        records.sort(key=lambda pair: (pair[1]["type"], pair[0]))
    deferred.sort(key=lambda row: row[0])
    return plan, deferred


def render_block(records, existing_text: str) -> str:
    """The text to append for one destination file."""
    lines = []
    if BOOTSTRAP_MARKER not in existing_text:
        lines.append("")
        lines.append(BOOTSTRAP_MARKER)
        lines.append(BOOTSTRAP_NOTE.rstrip("\n"))
    for aid, draft in records:
        lines.append("")
        lines.extend(emit_record(aid, draft))
    return "\n".join(lines) + "\n"


def verify_roundtrip(text: str, records, source: str):
    """Parse what we are about to write and confirm it reads back identically.

    The emitter and the reader are both subsets written here; this is what stops
    a scalar one of them quotes differently from corrupting the registry.
    """
    parsed = load_yaml(text, source)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("artifacts"), dict):
        raise YamlSubsetError("%s: emitted document has no artifacts mapping" % source)
    for aid, draft in records:
        got = parsed["artifacts"].get(aid)
        want = strip_comments(draft)
        if got != want:
            raise YamlSubsetError(
                "%s: record %r did not round-trip through the reader" % (source, aid))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _borg_root() -> str:
    return os.environ.get("BORG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def cmd_validate(args) -> int:
    root = _borg_root()
    registry_path = args.registry or os.path.join(root, "MEMORY-INVENTORY.yaml")
    schema_path = args.schema or os.path.join(root, "MEMORY-INVENTORY.schema.json")

    try:
        schema = json.loads(_read(schema_path))
    except (OSError, ValueError) as exc:
        print("error: cannot read schema %s: %s" % (schema_path, exc), file=sys.stderr)
        return EXIT_USAGE

    registries = []
    try:
        registries.append(Registry(load_yaml(_read(registry_path), registry_path),
                                   os.path.relpath(registry_path, root), private=False))
        for overlay in args.overlay:
            registries.append(Registry(load_yaml(_read(overlay), overlay),
                                       os.path.relpath(overlay, root), private=True))
    except OSError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except YamlSubsetError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return EXIT_INVALID

    if args.today:
        if not _is_date(args.today):
            print("error: --today must be YYYY-MM-DD", file=sys.stderr)
            return EXIT_USAGE
        today = _dt.date.fromisoformat(args.today)
    else:
        today = _dt.date.today()

    try:
        errors = validate_registries(registries, schema, today, args.show_private)
    except SchemaSupportError as exc:
        print("error: schema uses an unimplemented construct: %s" % exc, file=sys.stderr)
        return EXIT_USAGE

    public = sum(len(r.artifacts) for r in registries if not r.private)
    private = sum(len(r.artifacts) for r in registries if r.private)
    pub_reviewed, pub_draft, priv_reviewed, priv_draft = status_counts(registries)
    drafts = pub_draft + priv_draft
    reviewed = pub_reviewed + priv_reviewed

    if errors:
        for msg in errors:
            print("INVALID %s" % msg, file=sys.stderr)
        print("\n%d error(s) across %d public and %d private record(s)."
              % (len(errors), public, private), file=sys.stderr)
        return EXIT_INVALID

    total = public + private
    if not args.quiet:
        print("VALID %d public record(s), %d private record(s) — schema %s"
              % (public, private, os.path.relpath(schema_path, root)))
        print("      %d reviewed, %d draft (%s reviewed)"
              % (reviewed, drafts, _percent(reviewed, total)))
    if drafts:
        # Said on every run, including a passing one. A draft is registered but
        # NOT reviewed, and the whole point of the flag is that nobody reads
        # full registry coverage as full review coverage.
        message = ("%d record(s) are bootstrapped stubs: mechanically derived, no human "
                   "judgment yet. Each still needs a rationale, a retirement trigger, and a "
                   "remediation policy before it counts as reviewed." % drafts)
        if args.require_reviewed:
            print("UNREVIEWED %s" % message, file=sys.stderr)
            for aid, reg in _draft_ids(registries):
                if reg.private and not args.show_private:
                    continue
                print("  %s: artifacts.%s" % (reg.source, aid), file=sys.stderr)
            hidden = sum(1 for _, reg in _draft_ids(registries) if reg.private)
            if hidden and not args.show_private:
                print("  %d private draft(s) withheld; rerun with --show-private" % hidden,
                      file=sys.stderr)
            return EXIT_INVALID
        if not args.quiet:
            print("      note: %s" % message)
    return EXIT_OK


def _percent(part: int, whole: int) -> str:
    return "n/a" if not whole else "%.1f%%" % (100.0 * part / whole)


def _draft_ids(registries):
    """(id, registry) for every record still flagged `status: draft`."""
    out = []
    for reg in registries:
        for aid, record in reg.artifacts.items():
            if isinstance(record, dict) and record_status(
                    apply_defaults(record, reg.defaults)) == DRAFT:
                out.append((aid, reg))
    return out


def _load_registries(root, registry_path, overlays):
    """Load the tracked registry and any overlays. Absence is not fatal here:
    discovery's job is to measure the workspace, not to require a registry."""
    registries, notes = [], []
    for path, private in [(registry_path, False)] + [(o, True) for o in overlays]:
        if not os.path.isfile(path):
            notes.append("registry not found: %s" % os.path.relpath(path, root))
            continue
        try:
            data = load_yaml(_read(path), path)
        except (OSError, YamlSubsetError) as exc:
            notes.append("registry unreadable, treated as empty: %s" % exc)
            continue
        registries.append(Registry(data, os.path.relpath(path, root), private=private))
    return registries, notes


def _overlays_in_play(root, result, extra):
    """Every overlay to join against: the ones discovery found on disk, plus any
    named explicitly.

    Discovered overlays are included automatically because a run that could not
    see them would report every private artifact as UNREGISTERED and, in
    `bootstrap`, re-emit records that already exist — a duplicate the id rule
    only catches after the write.
    """
    paths = list(extra)
    for rel in result["overlays"]:
        absolute = os.path.join(root, rel)
        if absolute not in paths:
            paths.append(absolute)
    return paths


def cmd_discover(args) -> int:
    root = os.path.abspath(args.root or _borg_root())
    if not os.path.isdir(root):
        print("error: %s is not a directory" % root, file=sys.stderr)
        return EXIT_USAGE

    home = args.home or os.path.expanduser("~")
    codex_home = args.codex_home or os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")

    result = discover(root, codex_home=codex_home, home=home)

    registry_path = args.registry or os.path.join(root, "MEMORY-INVENTORY.yaml")
    registries, notes = _load_registries(
        root, registry_path, _overlays_in_play(root, result, args.overlay))
    result["notes"].extend(notes)
    join = join_registry(result["artifacts"], registries)

    if args.json:
        print(json.dumps(_public_json(result, join, args.show_private),
                         indent=2, sort_keys=False))
    else:
        print(format_report(result, join, args.show_private))
    return EXIT_OK


def _print_deferred(deferred, show_private: bool) -> None:
    """Report artifacts bootstrap refused to draft, and why.

    These stay UNREGISTERED on purpose. Coverage is honest only if the artifacts
    it cannot mechanically describe are named rather than counted as done.
    """
    if not deferred:
        return
    print("")
    print("Deferred — no valid mechanical record exists yet (%d)" % len(deferred))
    hidden = 0
    for aid, draft, reason in deferred:
        if draft["visibility"] != "public" and not show_private:
            hidden += 1
            continue
        print("  %-52s %s" % (draft["path"], reason))
    if hidden:
        print("  %d private artifact(s) withheld; rerun with --show-private" % hidden)
    print("  Each stays UNREGISTERED until its canonical source is restored or it is")
    print("  removed. That is a judgment call, so bootstrap will not make it.")


def cmd_bootstrap(args) -> int:
    root = os.path.abspath(args.root or _borg_root())
    if not os.path.isdir(root):
        print("error: %s is not a directory" % root, file=sys.stderr)
        return EXIT_USAGE

    home = args.home or os.path.expanduser("~")
    codex_home = args.codex_home or os.environ.get("CODEX_HOME") or os.path.join(home, ".codex")
    today = _dt.date.fromisoformat(args.today) if args.today else _dt.date.today()
    if args.today and not _is_date(args.today):
        print("error: --today must be YYYY-MM-DD", file=sys.stderr)
        return EXIT_USAGE

    result = discover(root, codex_home=codex_home, home=home)

    registry_path = args.registry or os.path.join(root, "MEMORY-INVENTORY.yaml")
    registries, notes = _load_registries(
        root, registry_path, _overlays_in_play(root, result, args.overlay))
    join = join_registry(result["artifacts"], registries)

    plan, deferred = plan_bootstrap(root, result, join, registries, today)
    if not plan:
        print("Nothing to bootstrap: every discovered artifact already has a record.")
        _print_deferred(deferred, args.show_private)
        return EXIT_OK

    schema_path = args.schema or os.path.join(root, "MEMORY-INVENTORY.schema.json")
    try:
        schema = json.loads(_read(schema_path))
    except (OSError, ValueError) as exc:
        print("error: cannot read schema %s: %s" % (schema_path, exc), file=sys.stderr)
        return EXIT_USAGE

    # Build every would-be file in memory, round-trip it through the reader, and
    # validate the result BEFORE anything touches the disk. A registry that fails
    # validation must never exist on disk even momentarily.
    staged, planned = [], []
    for destination in sorted(plan):
        absolute = os.path.join(root, destination)
        private = destination != "MEMORY-INVENTORY.yaml"
        if os.path.isfile(absolute):
            existing = _read(absolute)
        elif private:
            existing = OVERLAY_HEADER % destination
        else:
            print("error: %s does not exist; bootstrap appends to the registry, it does "
                  "not create it" % destination, file=sys.stderr)
            return EXIT_USAGE
        if existing and not existing.endswith("\n"):
            existing += "\n"
        text = existing + render_block(plan[destination], existing)
        try:
            verify_roundtrip(text, plan[destination], destination)
        except YamlSubsetError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return EXIT_INVALID
        staged.append((absolute, destination, text, private))
        planned.append(Registry(load_yaml(text, destination), destination, private=private))

    # Every overlay and the tracked registry are validated together so a draft's
    # canonical_ref into another file is resolved, not merely assumed.
    for reg in registries:
        if not any(p.source == reg.source for p in planned):
            planned.append(reg)
    try:
        errors = validate_registries(planned, schema, today, args.show_private)
    except SchemaSupportError as exc:
        print("error: schema uses an unimplemented construct: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    if errors:
        for msg in errors:
            print("INVALID %s" % msg, file=sys.stderr)
        print("\nnothing was written: the bootstrapped registry would not validate.",
              file=sys.stderr)
        return EXIT_INVALID

    total = sum(len(records) for records in plan.values())
    public_total = len(plan.get("MEMORY-INVENTORY.yaml", []))
    private_total = total - public_total

    out = []
    out.append("Memory inventory bootstrap — %s" % ("WRITE" if args.write else "dry run"))
    out.append("Root: %s" % root)
    out.append("")
    out.append("%d draft record(s) for unregistered artifacts: %d public, %d private."
               % (total, public_total, private_total))
    out.append("")
    out.append("By type")
    tally = {}
    for records in plan.values():
        for _, draft in records:
            tally[draft["type"]] = tally.get(draft["type"], 0) + 1
    for atype in sorted(tally):
        out.append("  %-26s %4d" % (atype, tally[atype]))
    out.append("")
    out.append("Destinations")
    for absolute, destination, _text, private in staged:
        # An overlay path names a private location. It is reported as a count
        # unless --show-private, exactly like every other private fact here.
        label = destination if (not private or args.show_private) else "<private overlay>"
        out.append("  %-40s %4d record(s)%s" % (label, len(plan[destination]),
                                                "" if os.path.isfile(absolute) else "  (new file)"))
    out.append("")
    out.append("Every record is `status: draft`: mechanically derived identity, ownership,")
    out.append("canonicality, and context cost, with NO human judgment. Registered is not")
    out.append("reviewed. Promote one by adding a rationale, provenance, risk, success")
    out.append("signals, retirement triggers, and a remediation policy, then setting")
    out.append("`status: reviewed`. `validate --require-reviewed` fails while any remain.")
    for note in notes:
        out.append("note: %s" % note)
    print("\n".join(out))
    _print_deferred(deferred, args.show_private)

    if not args.write:
        print("")
        print("Dry run: nothing written. Re-run with --write to apply.")
        return EXIT_OK

    for absolute, destination, text, private in staged:
        directory = os.path.dirname(absolute)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, mode=0o700)
        with open(absolute, "w", encoding="utf-8") as fh:
            fh.write(text)
        if private:
            os.chmod(absolute, 0o600)
    print("")
    print("Wrote %d record(s) across %d file(s)." % (total, len(staged)))
    return EXIT_OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="build-memory-inventory.py",
        description="Validate The Borg's long-term memory inventory registry.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="check the registry against the schema")
    v.add_argument("--registry", help="path to MEMORY-INVENTORY.yaml")
    v.add_argument("--schema", help="path to MEMORY-INVENTORY.schema.json")
    v.add_argument("--overlay", action="append", default=[],
                   help="gitignored private overlay to include (repeatable)")
    v.add_argument("--today", help="treat this YYYY-MM-DD as today (for reproducible checks)")
    v.add_argument("--show-private", action="store_true",
                   help="print private ids and paths; never use in a scheduled or emailed run")
    v.add_argument("--quiet", action="store_true", help="print nothing on success")
    v.add_argument("--require-reviewed", action="store_true", dest="require_reviewed",
                   help="fail if any record is still a bootstrapped `status: draft` stub; "
                        "this is the machine-checkable gate between registry coverage and "
                        "review coverage")
    v.set_defaults(func=cmd_validate)

    d = sub.add_parser(
        "discover",
        help="enumerate every durable memory artifact on disk (read-only)",
        description="Read-only discovery. Reports coverage against the registry but "
                    "never enforces it, and never mutates a discovered artifact.",
    )
    d.add_argument("--root", help="workspace root to scan (default: BORG_ROOT)")
    d.add_argument("--home", help="treat this as $HOME when locating Auto Memory")
    d.add_argument("--codex-home", dest="codex_home",
                   help="treat this as $CODEX_HOME when reading the command-bridge manifest")
    d.add_argument("--registry", help="path to MEMORY-INVENTORY.yaml")
    d.add_argument("--overlay", action="append", default=[],
                   help="gitignored private overlay to join against (repeatable)")
    d.add_argument("--json", action="store_true", help="emit the machine-readable snapshot view")
    d.add_argument("--show-private", action="store_true",
                   help="print private ids and paths; never use in a scheduled or emailed run")
    d.set_defaults(func=cmd_discover)

    b = sub.add_parser(
        "bootstrap",
        help="emit a `status: draft` record for every unregistered artifact",
        description="Mechanical half of migration step 3. Appends one draft record per "
                    "discovered-but-unregistered artifact, deriving only what the tree "
                    "determines. Public records go to MEMORY-INVENTORY.yaml; private ones "
                    "go to gitignored <owner>/.private/memory-inventory.yaml overlays and "
                    "never to a tracked file. Drafts are registered, not reviewed.",
    )
    b.add_argument("--root", help="workspace root to scan (default: BORG_ROOT)")
    b.add_argument("--home", help="treat this as $HOME when locating Auto Memory")
    b.add_argument("--codex-home", dest="codex_home",
                   help="treat this as $CODEX_HOME when reading the command-bridge manifest")
    b.add_argument("--registry", help="path to MEMORY-INVENTORY.yaml")
    b.add_argument("--schema", help="path to MEMORY-INVENTORY.schema.json")
    b.add_argument("--overlay", action="append", default=[],
                   help="extra private overlay to join against (repeatable); overlays "
                        "already on disk are found automatically")
    b.add_argument("--today", help="treat this YYYY-MM-DD as today (for reproducible runs)")
    b.add_argument("--write", action="store_true",
                   help="write the drafts; without it this is a dry run")
    b.add_argument("--show-private", action="store_true",
                   help="print private ids and paths; never use in a scheduled or emailed run")
    b.set_defaults(func=cmd_bootstrap)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
