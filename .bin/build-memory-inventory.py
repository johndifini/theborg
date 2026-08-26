#!/usr/bin/env python3
"""Deterministic tooling for The Borg's long-term memory inventory.

Implements migration step 1 of `c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md`:
the registry schema and a validator for it. Discovery (step 2) is deliberately
not implemented here yet; the `discover` subcommand exits non-zero saying so
rather than pretending a partial scan is a complete inventory.

    build-memory-inventory.py validate [options]
    build-memory-inventory.py discover          # step 2, not yet implemented

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

  * Declared intent only (design principle 3). This validator checks the
    hand-declared registry. Hashes, sizes, token estimates, and link graphs are
    computed snapshot fields and are not read, written, or required here.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2
EXIT_NOT_IMPLEMENTED = 3


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


def _without_artifact_minimum(schema: dict) -> dict:
    """Copy of the schema with `artifacts.minProperties` dropped, for overlays."""
    relaxed = _deep_copy(schema)
    relaxed.get("properties", {}).get("artifacts", {}).pop("minProperties", None)
    return relaxed


def _label(registry: Registry, artifact_id: str, show_private: bool) -> str:
    if registry.private and not show_private:
        return "%s: <private artifact>" % os.path.basename(registry.source)
    return "%s: artifacts.%s" % (registry.source, artifact_id)


def validate_registries(registries, schema: dict, today: _dt.date, show_private: bool):
    """Validate every registry against the schema, then the cross-record rules.

    Returns a list of human-readable error strings. Empty means valid.
    """
    validator = SchemaValidator(schema)
    errors = []

    # 1. Schema validation, per registry, on the defaults-merged record.
    for reg in registries:
        if not isinstance(reg.data, dict):
            errors.append("%s: document root must be a mapping" % reg.source)
            continue
        shell = {k: v for k, v in reg.data.items() if k != "artifacts"}
        shell["artifacts"] = {}
        for aid, record in reg.artifacts.items():
            if isinstance(record, dict):
                shell["artifacts"][aid] = apply_defaults(record, reg.defaults)
            else:
                shell["artifacts"][aid] = record
        active = validator
        if reg.private:
            # A private overlay may legitimately hold zero records — an agent
            # with nothing sensitive still gets a file. The tracked registry may
            # not, so minProperties is relaxed only for overlays.
            active = SchemaValidator(_without_artifact_minimum(schema))
        for msg in active.validate(shell):
            if reg.private and not show_private:
                errors.append("%s: %s" % (os.path.basename(reg.source),
                                          _redact(msg, reg.artifacts)))
            else:
                errors.append("%s: %s" % (reg.source, msg))

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

    if errors:
        for msg in errors:
            print("INVALID %s" % msg, file=sys.stderr)
        print("\n%d error(s) across %d public and %d private record(s)."
              % (len(errors), public, private), file=sys.stderr)
        return EXIT_INVALID

    if not args.quiet:
        print("VALID %d public record(s), %d private record(s) — schema %s"
              % (public, private, os.path.relpath(schema_path, root)))
    return EXIT_OK


def cmd_discover(args) -> int:
    print(
        "discovery is migration step 2 of c4po/LONG-TERM-MEMORY-INVENTORY-DESIGN.md "
        "and is not implemented yet.\nOnly step 1 (schema + validation) has landed; "
        "run `validate` instead.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


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
    v.set_defaults(func=cmd_validate)

    d = sub.add_parser("discover", help="(step 2) enumerate artifacts on disk")
    d.set_defaults(func=cmd_discover)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
