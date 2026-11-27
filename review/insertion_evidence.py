"""Exact preparation evidence and redaction validation, using Unicode code points.

`validate_map` checks offset-preserving redactions; `resolve` reads a closed field
path; `validate_evidence` checks original identity, literal slices and claim scope.
No whitespace, HTML, phone or address normalization is performed here.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from .insertion_fields import ESSENTIAL_FIELDS, ContractError, closed


def uuid_text(value: Any, path: str) -> str:
    """Validate a UUID as data; it grants no identity or database authority."""
    try:
        if not isinstance(value, str):
            raise ValueError("string required")
        return str(UUID(value))
    except ValueError as error:
        raise ContractError("invalid_shape", path) from error


def validate_map(value: Any, text: str) -> list[dict]:
    """Require an identity map with explicitly blanked, in-bounds text intervals."""
    closed(value, {"kind", "redactions"}, {"kind", "redactions"}, "/locator_map")
    if value["kind"] != "identity_with_redactions" or not isinstance(value["redactions"], list):
        raise ContractError("invalid_shape", "/locator_map")
    for span in value["redactions"]:
        start, end = _span(span, len(text), "/locator_map/redactions")
        if text[start:end] != " " * (end - start):
            raise ContractError("invalid_shape", "/locator_map/redactions")
    return value["redactions"]


def _span(value: Any, length: int, path: str) -> tuple[int, int]:
    """Read a nonempty start-inclusive/end-exclusive code-point interval."""
    closed(value, {"start", "end"}, {"start", "end"}, path)
    start, end = value["start"], value["end"]
    if any(not isinstance(item, int) or isinstance(item, bool) for item in (start, end)) or not 0 <= start < end <= length:
        raise ContractError("invalid_quote", path)
    return start, end


def resolve(value: Any, path: str) -> Any:
    """Resolve one RFC6901 pointer without permissive indices or implicit fields."""
    if not isinstance(path, str) or not (re.match(r"^/(service|location)/", path)
            or re.fullmatch(r"/source_facts/(0|[1-9][0-9]*)/source_value", path)):
        raise ContractError("invalid_shape", "/evidence/path")
    current = value
    for part in path[1:].split("/"):
        if re.search(r"~(?![01])", part):
            raise ContractError("invalid_shape", "/evidence/path")
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(current, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", part):
                    raise KeyError(part)
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                raise KeyError(part)
        except (KeyError, IndexError) as error:
            raise ContractError("invalid_shape", "/evidence/path") from error
    return current


def validate_evidence(evidence: Any, candidate: dict, request: dict) -> None:
    """Verify every quote against eligible text and refuse redacted/manual claims."""
    if not isinstance(evidence, list) or len(evidence) > 4000:
        raise ContractError("invalid_shape", "/evidence")
    seen = set()
    for item in evidence:
        closed(item, {"id", "path", "input_id", "input_hash", "kind", "span", "cell", "quote", "note"},
               {"id", "path", "input_id", "input_hash", "kind", "span", "quote"}, "/evidence")
        identity = uuid_text(item["id"], "/evidence/id")
        if identity in seen:
            raise ContractError("invalid_shape", "/evidence/id")
        seen.add(identity)
        if (uuid_text(item["input_id"], "/evidence/input_id") != request["input_id"]
                or item["input_hash"] != request["input_hash"] or item["kind"] not in ("stated", "interpreted")
                or "cell" in item):
            raise ContractError("invalid_quote", "/evidence")
        claimed = resolve(candidate, item["path"])
        start, end = _span(item["span"], len(request["text"]), "/evidence/span")
        if not isinstance(item["quote"], str) or item["quote"] != request["text"][start:end]:
            raise ContractError("invalid_quote", item["path"])
        if any(span["start"] < end and span["end"] > start for span in request["locator_map"]["redactions"]):
            raise ContractError("redacted_value", item["path"])
        if item["kind"] == "stated":
            for literal in _literals(claimed):
                if literal not in item["quote"]:
                    raise ContractError("invalid_quote", item["path"])
        if "note" in item and (not isinstance(item["note"], str) or len(item["note"]) > 2000):
            raise ContractError("invalid_shape", "/evidence/note")
        item["id"], item["input_id"] = identity, request["input_id"]


def _literals(value: Any):
    """Yield literal essential values; transformed claims must be interpreted."""
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        yield str(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in ESSENTIAL_FIELDS:
                yield from _literals(child)
            elif isinstance(child, (dict, list)):
                yield from _literals(child)
    elif isinstance(value, list):
        for child in value:
            yield from _literals(child)
