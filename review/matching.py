"""Bounded catalog matching without database, transport or confirmation authority.

`make_context` freezes authorized catalog pages; `propose` supplies deterministic
ordinal choices; `validate_matches` accepts only supplied keys for the same fact
and context. `resolve_matches` returns unconfirmed references for the owning app.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from difflib import SequenceMatcher
import hashlib
import json
import re
import unicodedata

from .insertion_evidence import uuid_text
from .insertion_fields import ContractError, closed, validate_source_facts

CONTEXT_KEYS = {"schema_version", "kind", "context", "as_of", "entries", "complete", "digest"}
ENTRY_KEYS = {"candidate_key", "label", "target", "published", "active", "effective_from", "effective_until", "broader"}


def _text(value: object, path: str, limit: int = 4000) -> str:
    """Require bounded nonblank text without normalizing the retained spelling."""
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not value.strip():
        raise ContractError("invalid_shape", path)
    return value


def _date(value: object, path: str) -> date:
    """Require a canonical ISO date rather than silently accepting a timestamp."""
    if not isinstance(value, str):
        raise ContractError("invalid_shape", path)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ContractError("invalid_shape", path) from None
    if parsed.isoformat() != value:
        raise ContractError("invalid_shape", path)
    return parsed


def context_digest(context: dict) -> str:
    """Hash the complete frozen context, including coverage, without its digest."""
    content = {k: v for k, v in context.items() if k != "digest"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate_context(context: object, *, provider: bool = False) -> dict:
    """Validate typed supplied references; their existence stays the DB's duty.

    Provider contexts admit published adopted category labels only. Organization
    name lookup stays local, so authorized drafts never enter an IA request here.
    """
    closed(context, CONTEXT_KEYS, CONTEXT_KEYS, "/catalog_context")
    value = deepcopy(context)
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ContractError("unsupported_field", "/catalog_context/schema_version")
    kind = value["kind"]
    if kind not in ("organization", "classification") or (provider and kind != "classification"):
        raise ContractError("unresolved_reference", "/catalog_context/kind")
    current = _date(value["as_of"], "/catalog_context/as_of")
    if type(value["complete"]) is not bool or not isinstance(value["entries"], list) or len(value["entries"]) > 100:
        raise ContractError("invalid_shape", "/catalog_context/entries")
    scope = value["context"]
    if kind == "classification":
        closed(scope, {"territory_id", "axis_id"}, {"territory_id", "axis_id"}, "/catalog_context/context")
        for key in scope:
            if uuid_text(scope[key], f"/catalog_context/context/{key}") != scope[key]:
                raise ContractError("invalid_shape", f"/catalog_context/context/{key}")
    elif scope != {}:
        raise ContractError("invalid_shape", "/catalog_context/context")
    keys, identities = set(), set()
    for entry in value["entries"]:
        closed(entry, ENTRY_KEYS, ENTRY_KEYS, "/catalog_context/entries")
        key = _text(entry["candidate_key"], "/catalog_context/candidate_key", 100)
        _text(entry["label"], "/catalog_context/label")
        if key in keys or type(entry["published"]) is not bool or entry["active"] is not True:
            raise ContractError("invalid_shape", "/catalog_context/entries")
        keys.add(key)
        target = entry["target"]
        fields = ({"kind", "organization_id", "expected_work", "expected_public"} if kind == "organization"
                  else {"kind", "adoption_id", "release_id", "term_id", "axis_id"})
        closed(target, fields, fields, "/catalog_context/target")
        if target["kind"] != kind:
            raise ContractError("unresolved_reference", "/catalog_context/target/kind")
        for field in fields - {"kind"}:
            if field == "expected_public" and target[field] is None:
                continue
            if uuid_text(target[field], f"/catalog_context/target/{field}") != target[field]:
                raise ContractError("invalid_shape", f"/catalog_context/target/{field}")
        identity = json.dumps(target, sort_keys=True)
        if identity in identities:
            raise ContractError("unresolved_reference", "/catalog_context/target")
        identities.add(identity)
        if not isinstance(entry["broader"], list) or len(entry["broader"]) > 100:
            raise ContractError("invalid_shape", "/catalog_context/broader")
        for parent in entry["broader"]:
            uuid_text(parent, "/catalog_context/broader")
        if kind == "classification":
            if target["axis_id"] != scope["axis_id"] or entry["published"] is not True:
                raise ContractError("unresolved_reference", "/catalog_context/target/axis_id")
            start = _date(entry["effective_from"], "/catalog_context/effective_from")
            end = _date(entry["effective_until"], "/catalog_context/effective_until") if entry["effective_until"] is not None else None
            if start > current or (end is not None and (end < current or end < start)):
                raise ContractError("unresolved_reference", "/catalog_context/effective_from")
        elif entry["effective_from"] is not None or entry["effective_until"] is not None:
            raise ContractError("invalid_shape", "/catalog_context/effective_from")
    if value["digest"] != context_digest(value):
        raise ContractError("unresolved_reference", "/catalog_context/digest")
    return value


def make_context(page: dict, *, as_of: date) -> dict:
    """Freeze at most100 entries from the authorized EGI catalog read contract.

    The caller owns pagination, permissions and truthful coverage. No inactive or
    out-of-date entry is silently repaired; invalid source pages fail closed.
    """
    if not isinstance(page, dict) or not isinstance(page.get("entries"), list):
        raise ContractError("invalid_shape", "/catalog_context")
    raw_scope = page.get("context", {})
    entries = []
    kind = raw_scope.get("kind", "organization" if "organization_name" in raw_scope else None)
    if kind == "classification":
        scope = {key: raw_scope[key] for key in ("territory_id", "axis_id") if key in raw_scope}
    else:
        scope = {}
    if type(as_of) is not date:
        raise ContractError("invalid_shape", "/catalog_context/as_of")
    for index, entry in enumerate(page["entries"]):
        entries.append({"candidate_key": f"catalog-{index + 1}", "label": entry.get("label"), "target": deepcopy(entry.get("target")),
                        "published": entry.get("published"), "active": entry.get("active", True),
                        "effective_from": entry.get("effective_from"), "effective_until": entry.get("effective_until"),
                        "broader": deepcopy(entry.get("broader", []))})
    context = {"schema_version": 1, "kind": kind, "context": scope, "as_of": as_of.isoformat(),
               "entries": entries, "complete": page.get("complete"), "digest": ""}
    context["digest"] = context_digest(context)
    return validate_context(context)


def _key(value: str) -> str:
    """Normalize comparison only, retaining original labels and source facts."""
    text = "".join(ch for ch in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(ch))
    return " ".join(re.findall(r"\w+", text, re.UNICODE))


def _facts(facts: object) -> dict:
    """Index distinct per-card fact keys eligible for this selected catalog kind."""
    validate_source_facts(facts)
    return {fact["fact_key"]: fact for fact in facts}


def validate_matches(matches: object, facts: list, context: dict) -> list:
    """Accept ordinal proposals for supplied keys only, never target IDs or roles."""
    context = validate_context(context)
    indexed = _facts(facts)
    candidates = {entry["candidate_key"] for entry in context["entries"]}
    if not isinstance(matches, list) or len(matches) > len(indexed):
        raise ContractError("invalid_shape", "/matches")
    seen = set()
    for match in matches:
        closed(match, {"fact_key", "context_digest", "choices"}, {"fact_key", "context_digest", "choices"}, "/matches")
        fact = indexed.get(match["fact_key"]) if isinstance(match["fact_key"], str) else None
        kind = "organization_name" if context["kind"] == "organization" else "category_label"
        if fact is None or match["fact_key"] in seen or fact["kind"] != kind or (kind == "category_label" and fact["subject"] != "service"):
            raise ContractError("unresolved_reference", "/matches/fact_key")
        seen.add(match["fact_key"])
        if match["context_digest"] != context["digest"] or not isinstance(match["choices"], list) or len(match["choices"]) > 100:
            raise ContractError("unresolved_reference", "/matches/context_digest")
        chosen = set()
        for choice in match["choices"]:
            closed(choice, {"candidate_key", "reason"}, {"candidate_key", "reason"}, "/matches/choices")
            key = choice["candidate_key"]
            if not isinstance(key, str) or key not in candidates or key in chosen:
                raise ContractError("unresolved_reference", "/matches/choices/candidate_key")
            chosen.add(key)
            _text(choice["reason"], "/matches/choices/reason", 1000)
    return deepcopy(matches)


def propose(facts: list, context: dict) -> list:
    """Suggest lexical category/name matches with ordinal reasons and no IA call.

    Scores only sort internal lexical heuristics; they are never a calibrated
    confidence. Empty choices explicitly represent no match within this context.
    """
    context = validate_context(context)
    indexed = _facts(facts)
    matches = []
    for key, fact in indexed.items():
        wanted = "organization_name" if context["kind"] == "organization" else "category_label"
        if fact["kind"] != wanted or (wanted == "category_label" and fact["subject"] != "service"):
            continue
        source = _key(fact["source_value"])
        ranked = []
        for entry in context["entries"]:
            label = _key(entry["label"])
            if not source or not label:
                continue
            if label == source:
                score, reason = 3.0, "normalized_label"
            elif wanted == "category_label" and ((set(source.split()) & set(label.split())) - {"di", "e", "a", "per", "il", "la", "del", "dei", "con", "in"}):
                score, reason = 2 + SequenceMatcher(None, source, label).ratio(), "shared_words"
            elif wanted == "category_label" and len(source) >= 5 and SequenceMatcher(None, source, label).ratio() >= .85:
                score, reason = 1.0, "similar_label"
            else:
                continue
            ranked.append((-score, label, entry["candidate_key"], reason))
        ranked.sort()
        matches.append({"fact_key": key, "context_digest": context["digest"],
                        "choices": [{"candidate_key": candidate, "reason": reason} for _, _, candidate, reason in ranked]})
    return validate_matches(matches, facts, context)


def resolve_matches(matches: list, facts: list, context: dict) -> list:
    """Resolve supplied keys into unconfirmed references for the owning application."""
    matches = validate_matches(matches, facts, context)
    entries = {entry["candidate_key"]: entry for entry in context["entries"]}
    return [{"fact_key": match["fact_key"], "state": "proposed" if match["choices"] else "unresolved",
             "context": deepcopy(context["context"]) if match["choices"] else {},
             "candidates": [{"target": deepcopy(entries[choice["candidate_key"]]["target"]), "rank": index + 1, "reason": choice["reason"]}
                            for index, choice in enumerate(match["choices"])]} for match in matches]
