"""Validate frozen workbench packets and recover attributable independent outcomes.

Request/context checks preserve exact source ownership and supplied catalog scope.
Result checks reconcile bases and comparison units; interpret performs one injected
exchange. Transport, usage ledgers, current source eligibility and writes stay outside.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re
import unicodedata

from .insertion import Adapter, _adapter_response
from .insertion_fields import ContractError, closed
from .matching import context_digest, validate_context
from . import workbench_profile as profile


def canonical_json(value: object) -> str:
    """Encode the same compact sorted Unicode JSON used by the SQL provider."""
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        text.encode("utf-8")
        return text
    except (TypeError, ValueError, RecursionError, UnicodeError):
        raise ContractError("invalid_shape", "/request") from None


def request_digest(request: dict) -> str:
    """Hash all immutable request fields without removing nested digest members."""
    return hashlib.sha256(canonical_json(request).encode()).hexdigest()


def scope_key(shared_context: dict) -> str:
    """Bind semantic identity to the preparation and catalog snapshot, not a slice."""
    return request_digest({key: shared_context[key] for key in ("scope", "catalog_snapshot")})


def normalize_label(value: str) -> str:
    """Compare NFC, case and whitespace only; preserve accents and punctuation."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _require(condition: bool, code: str = "invalid_shape", path: str = "") -> None:
    """Raise only a safe contract code at a known structural path."""
    if not condition:
        raise ContractError(code, path)


def _closed(value: object, name: str) -> dict:
    """Apply the exact field set shared with the generated output profile."""
    return closed(value, profile.FIELDS[name], profile.FIELDS[name], f"/{name}")


def _text(value: object, limit: int = 50000) -> str:
    """Require bounded retained text without changing source spelling."""
    _require(isinstance(value, str) and 0 < len(value) <= limit and bool(value.strip()))
    return value


def _array(value: object) -> list:
    """Require a JSON array inside the bounded public packet envelope."""
    _require(isinstance(value, list))
    return value


def _keys(value: object, limit: int = 300) -> list:
    """Require unique opaque keys and never silently deduplicate an array."""
    items = _array(value)
    for item in items:
        _text(item, limit)
    _require(len(set(items)) == len(items), "unresolved_reference")
    return items


def _codes(value: object) -> list:
    """Keep all diagnostics free of source/provider prose."""
    items = _keys(value)
    _require(set(items) <= profile.DIAGNOSTICS)
    return items


def _integer(value: object, minimum: int = 0) -> int:
    """Reject Boolean aliases and negative or nonintegral counts."""
    _require(type(value) is int and value >= minimum)
    return value


def _digest(value: object) -> str:
    """Require a canonical SHA256 hexadecimal value."""
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None)
    return value


def _index(items: object, shape: str, key: str) -> dict:
    """Index exact records, rejecting any duplicate identity."""
    indexed = {}
    for item in _array(items):
        _closed(item, shape)
        identity = _text(item[key], 300)
        _require(identity not in indexed, "unresolved_reference")
        indexed[identity] = item
    return indexed


def _catalog(value: dict) -> dict:
    """Validate workbench enrichment while preserving the older matching contract."""
    _require(isinstance(value, dict) and isinstance(value.get("entries"), list))
    _require(value.get("digest") == context_digest(value), "unresolved_reference", "/catalog_context/digest")
    core = deepcopy(value)
    for entry in core["entries"]:
        _require(isinstance(entry, dict) and {"definition", "aliases"} <= set(entry))
        definition, aliases = entry.pop("definition"), entry.pop("aliases")
        if definition is not None:
            _text(definition)
        for alias in _keys(aliases, 4000):
            _text(alias, 4000)
    core["digest"] = context_digest(core)
    validate_context(core, provider=True)
    return value


def _context(request: dict) -> None:
    """Check actual shared content, frozen versions, digests and supplied scope."""
    ctx = _closed(request["shared_context"], "shared_context")
    scope = _closed(ctx["scope"], "scope")
    _text(ctx["context_id"], 300)
    _integer(ctx["version"], 1)
    _require(ctx["digest"] == context_digest(ctx), "unresolved_reference", "/shared_context/digest")
    _require(ctx["prompt_version"] == profile.PROMPT_VERSION and ctx["schema_profile_version"] == profile.SCHEMA_VERSION
             and ctx["field_dictionary_version"] == profile.FIELD_VERSION, "unsupported_field")
    _require(scope["preparation_snapshot_key"] == request["preparation_snapshot_key"], "unresolved_reference")
    cat = _catalog(request["catalog_context"])
    _require(all(scope[key] == cat["context"][key] for key in ("territory_id", "axis_id")), "unresolved_reference")
    closed(ctx["catalog_snapshot"], {"digest"}, {"digest"})
    _digest(ctx["catalog_snapshot"]["digest"])
    semantics = set()
    for source in _array(ctx["source_semantics"]):
        closed(source, {"source_key", "rules"}, {"source_key", "rules"})
        key = _text(source["source_key"], 300)
        _require(key not in semantics)
        semantics.add(key)
        for rule in _array(source["rules"]):
            _text(rule)
    metadata = set()
    for source in _array(ctx["source_metadata"]):
        closed(source, {"source_key", "name", "publisher", "source_kind", "homepage", "license", "attribution"}, {"source_key"})
        key = _text(source["source_key"], 300)
        _require(key not in metadata)
        metadata.add(key)
        for name, value in source.items():
            if name != "source_key" and value is not None:
                _text(value, 4000)
    _require(set(_keys(ctx["limitations"])) <= profile.INPUT_LIMITATIONS)
    inventory = _array(ctx["label_inventory"])
    seen = set()
    for label in inventory:
        closed(label, {"label", "context_key", "count"}, {"label", "context_key", "count"})
        _text(label["label"])
        if label["context_key"] is not None:
            _digest(label["context_key"])
        identity = (label["label"], label["context_key"])
        _require(identity not in seen)
        seen.add(identity)
        _integer(label["count"], 1)
    coverage = closed(ctx["inventory_coverage"], {"complete", "total_labels", "supplied_labels", "omitted_labels"}, {"complete", "total_labels", "supplied_labels", "omitted_labels"})
    _require(type(coverage["complete"]) is bool)
    for name in ("total_labels", "supplied_labels", "omitted_labels"):
        _integer(coverage[name])
    _require(coverage["supplied_labels"] == len(inventory) and coverage["total_labels"] == len(inventory) + coverage["omitted_labels"]
             and coverage["complete"] == (coverage["omitted_labels"] == 0))


def _owned_support(keys: object, supports: dict, records: set) -> set:
    """Resolve support only within the owning record or comparison occurrences."""
    keys = set(_keys(keys))
    _require(bool(keys) and all(key in supports and supports[key]["record_key"] in records for key in keys), "unresolved_reference")
    return keys


def _data(request: dict) -> None:
    """Check indexed source-bound records, bases, labels and required/reference sets."""
    data = _closed(request["data"], "data")
    records = _index(data["records"], "record", "record_key")
    units = _index(data["units"], "unit", "unit_key")
    bases = _index(data["bases"], "basis", "basis_key")
    supports = _index(data["supports"], "support", "support_key")
    labels = _index(data["labels"], "label", "unit_key")
    sources = {entry["source_key"] for entry in request["shared_context"]["source_semantics"]}
    metadata = {entry["source_key"]: entry for entry in request["shared_context"]["source_metadata"]}
    for record in records.values():
        _text(record["item_version"], 300)
        _require(record["source_key"] in sources and record["source_key"] in metadata, "unresolved_reference")
    for support in supports.values():
        record = records.get(support["record_key"])
        _require(record is not None, "unresolved_reference")
        _text(support["input_key"], 300)
        path, text = _text(support["field_path"], 500), _text(support["text"])
        start, end = _integer(support["start"]), _integer(support["end"], 1)
        _require(path.startswith("/") and start < end <= len(text) and support["quote"] == text[start:end], "unresolved_reference")
        _require(support["origin"] in ("source", "source_metadata"))
        if support["origin"] == "source_metadata":
            _require(path.startswith("/source_metadata/") and metadata[record["source_key"]].get(path.removeprefix("/source_metadata/")) == text, "unresolved_reference")
        else:
            _require(not path.startswith("/source_metadata/"), "unresolved_reference")
    for basis in bases.values():
        _require(basis["record_key"] in records and basis["kind"] in ("category_label", "description", "source_context"), "unresolved_reference")
        _text(basis["value"])
        keys = _owned_support(basis["support_keys"], supports, {basis["record_key"]})
        _require(any(supports[key]["quote"] == basis["value"] and (basis["kind"] == "source_context" or supports[key]["origin"] == "source") for key in keys), "unresolved_reference")
    for label in labels.values():
        _text(label["label"])
        _keys(label["variants"], 50000)
        if label["context_key"] is not None:
            _digest(label["context_key"])
        occurrences = _array(label["occurrences"])
        _require(0 < len(occurrences) <= _integer(label["count"], 1))
        identities = set()
        for occurrence in occurrences:
            _closed(occurrence, "occurrence")
            basis = bases.get(occurrence["basis_key"])
            _require(basis is not None and basis["record_key"] == occurrence["record_key"] and basis["kind"] in ("category_label", "description")
                     and basis["value"] in [label["label"], *label["variants"]], "unresolved_reference")
            _require(set(_keys(occurrence["support_keys"])) <= set(basis["support_keys"]) and bool(occurrence["support_keys"]), "unresolved_reference")
            identity = (occurrence["record_key"], occurrence["basis_key"])
            _require(identity not in identities)
            identities.add(identity)
    for unit in units.values():
        basis_keys, members = _keys(unit["basis_keys"]), _keys(unit["member_keys"])
        if request["task"] == "classify_cards":
            _require(unit["record_key"] in records and bool(basis_keys) and not members
                     and all(key in bases and bases[key]["record_key"] == unit["record_key"] for key in basis_keys), "unresolved_reference")
        else:
            _require(unit["record_key"] is None and not basis_keys and bool(members) and set(members) <= set(labels), "unresolved_reference")
    coverage = _closed(request["coverage"], "coverage")
    _digest(coverage["selection_digest"])
    _text(coverage["sample_policy"], 300)
    _require(type(coverage["catalog_complete"]) is bool and coverage["catalog_complete"] == request["catalog_context"]["complete"])
    for name in ("total_units", "supplied_units", "omitted_units"):
        _integer(coverage[name])
    sets = {name: set(_keys(coverage[name])) for name in ("required_record_keys", "reference_record_keys", "required_unit_keys", "reference_unit_keys")}
    _require(not sets["required_record_keys"] & sets["reference_record_keys"] and not sets["required_unit_keys"] & sets["reference_unit_keys"])
    _require(sets["required_record_keys"] | sets["reference_record_keys"] == set(records) and sets["required_unit_keys"] | sets["reference_unit_keys"] == set(units), "unresolved_reference")
    _require(coverage["supplied_units"] == len(sets["required_unit_keys"]) and coverage["total_units"] == coverage["supplied_units"] + coverage["omitted_units"])
    _require(set(_keys(coverage["limitations"])) <= profile.INPUT_LIMITATIONS)
    if request["task"] == "classify_cards":
        _require(not labels and not data["seed_groups"] and not data["prior_proposals"])
        _require({units[key]["record_key"] for key in sets["required_unit_keys"]} == sets["required_record_keys"], "unresolved_reference")
    else:
        _require(not sets["required_record_keys"] and sets["reference_record_keys"] == set(records), "unresolved_reference")
        for seed in _index(data["seed_groups"], "seed", "group_key").values():
            keys = _keys(seed["unit_keys"])
            _require(len(keys) >= 2 and set(keys) <= set(labels) and seed["relation"] in ("equivalent", "related", "ambiguous"))
            if seed["relation"] == "equivalent":
                _require(all(labels[key]["context_key"] == scope_key(request["shared_context"]) and labels[key]["count"] == len(labels[key]["occurrences"]) for key in keys), "unresolved_reference")
        for prior in _index(data["prior_proposals"], "classify_proposal", "proposal_key").values():
            _classify_proposal(prior, request, bases, supports)


def validate_request(request: object) -> dict:
    """Return an independent frozen request; invalid input never reaches an Adapter."""
    _require(len(canonical_json(request).encode()) <= 1048576)
    request = deepcopy(_closed(request, "request"))
    _require(type(request["schema_version"]) is int and request["schema_version"] == 1 and isinstance(request["task"], str) and request["task"] in profile.TASKS, "unsupported_field")
    for key in ("plan_key", "packet_key", "preparation_snapshot_key", "config_version"):
        _text(request[key], 300)
    _require(request["prompt_version"] == profile.PROMPT_VERSION and request["field_dictionary_version"] == profile.FIELD_VERSION
             and request["policy_version"] == profile.POLICY_VERSION, "unsupported_field")
    try:
        _context(request)
        _data(request)
    except (TypeError, KeyError, IndexError, AttributeError):
        raise ContractError("invalid_shape", "/request") from None
    return request


def instructions(request: dict) -> str:
    """Return the centrally owned task instructions for an authorized valid packet."""
    request = validate_request(request)
    return profile.INSTRUCTIONS + "\n" + profile.TASK_INSTRUCTIONS[request["task"]] + "\nTask: " + request["task"] + ". Request digest: " + request_digest(request) + "."


def output_schema(request: dict) -> dict:
    """Generate the same closed schema the transport must send to the provider."""
    request = validate_request(request)
    schema = profile.result_schema(request["task"], request_digest(request))
    _require(len(canonical_json(schema).encode()) + len(canonical_json(instructions(request)).encode()) <= profile.PROFILE_BYTES)
    return schema


def input_bound(request: dict, *, framing_tokens: int = profile.FRAMING_TOKENS) -> dict:
    """Expose exact input material sizes and a conservative bytes-based token bound."""
    _integer(framing_tokens, profile.FRAMING_TOKENS)
    request_text = canonical_json(validate_request(request))
    sizes = {"request_bytes": len(canonical_json(request_text).encode()),
             "instructions_bytes": len(canonical_json(instructions(request)).encode()), "schema_bytes": len(canonical_json(output_schema(request)).encode())}
    return {**sizes, "framing_tokens": framing_tokens, "token_ceiling": sum(sizes.values()) + framing_tokens,
            "profile_overhead_ceiling": profile.PROFILE_BYTES + profile.FRAMING_TOKENS}


def _choices(value: object, request: dict, supports: dict, allowed: set, triggers: set | None = None) -> None:
    """Check supplied candidate choices and independent original supporting keys."""
    choices = _array(value)
    _require(len(choices) <= 5)
    candidates = {entry["candidate_key"] for entry in request["catalog_context"]["entries"]}
    seen = set()
    for choice in choices:
        _closed(choice, "choice")
        key = _text(choice["candidate_key"], 300)
        _require(key in candidates and key not in seen, "unresolved_reference")
        seen.add(key)
        _text(choice["reason"], 300)
        keys = set(_keys(choice["support_keys"]))
        _require(bool(keys) and keys <= allowed and keys <= set(supports), "unresolved_reference")
        _require(triggers is None or not keys <= triggers, "insufficient_context")


def _classify_proposal(proposal: dict, request: dict, bases: dict, supports: dict, triggers: set | None = None) -> None:
    """Validate an explicit basis outcome without selecting a canonical reference."""
    _closed(proposal, "classify_proposal")
    _text(proposal["proposal_key"], 300)
    basis = bases.get(_text(proposal["basis_key"], 300))
    _require(basis is not None, "unresolved_reference")
    _require(proposal["state"] in ("proposed", "no_supplied_match", "insufficient_context"))
    codes = _codes(proposal["missing_context"])
    allowed = {key for key, support in supports.items() if support["record_key"] == basis["record_key"]}
    _choices(proposal["choices"], request, supports, allowed, triggers)
    _require(bool(proposal["choices"]) == (proposal["state"] == "proposed"))
    _require(proposal["state"] != "insufficient_context" or bool(codes), "insufficient_context")
    _require(request["coverage"]["catalog_complete"] or "incomplete_catalog" in codes, "incomplete_catalog")


def _group_proposal(proposal: dict, request: dict, unit: dict, supports: dict) -> None:
    """Validate contextual members, occurrence completeness and group-only support."""
    _closed(proposal, "group_proposal")
    _text(proposal["proposal_key"], 300)
    _require(proposal["relation"] in ("equivalent", "related", "ambiguous"))
    keys = _keys(proposal["unit_keys"])
    _require(len(keys) >= 2 and set(keys) <= set(unit["member_keys"]), "unresolved_reference")
    labels = {label["unit_key"]: label for label in request["data"]["labels"]}
    issues = {}
    for issue in _array(proposal["membership_issues"]):
        _closed(issue, "membership_issue")
        _require(issue["unit_key"] in keys and issue["unit_key"] not in issues, "unresolved_reference")
        _text(issue["reason"], 300)
        issues[issue["unit_key"]] = issue["reason"]
    allowed = {support for key in keys for occurrence in labels[key]["occurrences"] for support in occurrence["support_keys"]}
    cited = set(_keys(proposal["support_keys"]))
    _require(bool(cited) and cited <= allowed, "unresolved_reference")
    unsafe = {key for key in keys if labels[key]["context_key"] != scope_key(request["shared_context"])
              or labels[key]["count"] != len(labels[key]["occurrences"])}
    if unsafe:
        _require(unsafe <= set(issues) and proposal["relation"] != "equivalent" and not proposal["choices"], "insufficient_context")
    _require(proposal["relation"] != "equivalent" or not issues, "insufficient_context")
    _text(proposal["reason"], 300)
    _choices(proposal["choices"], request, supports, allowed)


def _hypotheses(value: object, record_key: str | None, supports: dict) -> set:
    """Accept optional unverified explanations; their triggers do not prove meaning."""
    hypotheses = _index(value, "hypothesis", "hypothesis_key")
    triggers = set()
    for hypothesis in hypotheses.values():
        _require(record_key is not None and hypothesis["kind"] == "abbreviation_expansion"
                 and hypothesis["status"] == "unverified" and hypothesis["verification_needed"] is True)
        _text(hypothesis["statement"], 300)
        triggers.update(_owned_support(hypothesis["trigger_support_keys"], supports, {record_key}))
    return triggers


def _recover_unit(value: dict, expected: dict, proposals: dict, ownership: Counter, request: dict) -> tuple[dict, list]:
    """Retain attributable outcomes and demote bases missing explicit outcomes."""
    unit = deepcopy(_closed(value, "unit_result"))
    _require(unit["record_key"] == expected["record_key"] and unit["state"] in ("analyzed", "insufficient_context", "not_analyzed"), "unresolved_reference")
    processed, unresolved = set(_keys(unit["processed_basis_keys"])), set(_keys(unit["unprocessed_basis_keys"]))
    required = set(expected["basis_keys"])
    _require(not processed & unresolved and processed | unresolved <= required, "unresolved_reference")
    codes = _codes(unit["diagnostics"])
    keys = _keys(unit["proposal_keys"])
    supports = {support["support_key"]: support for support in request["data"]["supports"]}
    triggers = _hypotheses(unit["hypotheses"], unit["record_key"], supports)
    _require(all(ownership[key] == 1 for key in keys), "duplicate_proposal")
    retained = []
    for key in keys:
        if key not in proposals:
            if "missing_proposal" not in codes:
                codes.append("missing_proposal")
            continue
        proposal = deepcopy(proposals[key])
        if request["task"] == "classify_cards":
            bases = {basis["basis_key"]: basis for basis in request["data"]["bases"]}
            _classify_proposal(proposal, request, bases, supports, triggers)
            _require(proposal["basis_key"] in processed, "unresolved_reference")
        else:
            _group_proposal(proposal, request, expected, supports)
        retained.append(proposal)
    if request["task"] == "classify_cards":
        by_basis = Counter(proposal["basis_key"] for proposal in retained)
        _require(all(count == 1 for count in by_basis.values()), "duplicate_proposal")
        missing = required - set(by_basis)
        if missing - unresolved:
            codes.append("incomplete_bases")
        processed -= missing
        unresolved |= missing
    else:
        _require(not processed and not unresolved)
    if unit["state"] == "not_analyzed":
        _require(not processed and not retained and not unit["hypotheses"])
        unresolved = required
    if required and not processed:
        unit["state"] = "not_analyzed"
        unit["hypotheses"] = []
    unit.update(processed_basis_keys=[key for key in expected["basis_keys"] if key in processed],
                unprocessed_basis_keys=[key for key in expected["basis_keys"] if key in unresolved],
                proposal_keys=[proposal["proposal_key"] for proposal in retained], diagnostics=list(dict.fromkeys(codes)))
    return unit, retained


def _empty(request: dict, code: str, state: str = "incomplete") -> dict:
    """Return safe known provenance and unresolved coverage without invented output."""
    return {"schema_version": 1, "task": request["task"], "request_digest": request_digest(request),
            "state": state, "unit_results": [], "unprocessed_unit_keys": deepcopy(request["coverage"]["required_unit_keys"]),
            "proposals": [], "diagnostics": [code]}


def validate_result(result: object, request: dict) -> dict:
    """Recover independent units from a bound parseable envelope, never repair text.

    Outer shape, task and digest failures raise ContractError. Unit-local invalid,
    duplicate or foreign data lose coverage explicitly; missing basis outcomes are
    moved to unprocessed while valid outcomes from that unit remain attributable.
    """
    request = validate_request(request)
    _require(len(canonical_json(result).encode()) <= 1048576)
    result = deepcopy(_closed(result, "result"))
    _require(type(result["schema_version"]) is int and result["schema_version"] == 1
             and result["task"] == request["task"] and result["request_digest"] == request_digest(request), "unresolved_reference")
    _require(result["state"] in ("complete", "incomplete", "refused"))
    diagnostics = _codes(result["diagnostics"])
    raw_units, raw_proposals = _array(result["unit_results"]), _array(result["proposals"])
    raw_unprocessed = _array(result["unprocessed_unit_keys"])
    for key in raw_unprocessed:
        _text(key, 300)
    if result["state"] == "refused":
        _require(not raw_units and not raw_proposals)
        _require(len(raw_unprocessed) == len(set(raw_unprocessed)) and set(raw_unprocessed) <= set(request["coverage"]["required_unit_keys"]), "unresolved_reference")
        return _empty(request, "provider_refused", "refused")
    required = request["coverage"]["required_unit_keys"]
    units = {unit["unit_key"]: unit for unit in request["data"]["units"]}
    unit_counts = Counter(unit.get("unit_key") for unit in raw_units if isinstance(unit, dict) and isinstance(unit.get("unit_key"), str))
    proposal_counts = Counter(proposal.get("proposal_key") for proposal in raw_proposals if isinstance(proposal, dict) and isinstance(proposal.get("proposal_key"), str))
    proposals = {proposal["proposal_key"]: proposal for proposal in raw_proposals if isinstance(proposal, dict)
                 and isinstance(proposal.get("proposal_key"), str) and proposal_counts[proposal["proposal_key"]] == 1}
    ownership = Counter(key for unit in raw_units if isinstance(unit, dict) and isinstance(unit.get("proposal_keys"), list)
                        for key in unit["proposal_keys"] if isinstance(key, str))
    retained_units, retained_proposals = [], []
    invalid = False
    for value in raw_units:
        key = value.get("unit_key") if isinstance(value, dict) else None
        if not isinstance(key, str) or key not in required:
            diagnostics.append("foreign_unit")
            invalid = True
            continue
        if unit_counts[key] != 1 or key in raw_unprocessed:
            diagnostics.append("duplicate_unit")
            invalid = True
            continue
        try:
            _require(isinstance(value.get("proposal_keys"), list))
            _require(not any(isinstance(ref, str) and proposal_counts[ref] > 1 for ref in value["proposal_keys"]), "duplicate_proposal")
            unit, unit_proposals = _recover_unit(value, units[key], proposals, ownership, request)
            retained_units.append(unit)
            retained_proposals.extend(unit_proposals)
        except ContractError as error:
            diagnostics.append(error.code if error.code in profile.DIAGNOSTICS else "invalid_unit")
            diagnostics.append("invalid_unit")
            invalid = True
    kept = {proposal["proposal_key"] for proposal in retained_proposals}
    if len(raw_proposals) != len(kept):
        diagnostics.append("unreferenced_proposal")
        invalid = True
    if len(raw_unprocessed) != len(set(raw_unprocessed)) or not set(raw_unprocessed) <= set(required):
        diagnostics.append("invalid_unit")
        invalid = True
    known = {unit["unit_key"] for unit in retained_units}
    unresolved = [key for key in required if key not in known]
    partial = any(unit["unprocessed_basis_keys"] or unit["state"] == "not_analyzed" for unit in retained_units)
    if unresolved:
        diagnostics.append("incomplete_units")
    if partial:
        diagnostics.append("incomplete_bases")
    result.update(state="incomplete" if invalid or unresolved or partial or result["state"] == "incomplete" else "complete",
                  unit_results=retained_units, proposals=retained_proposals, unprocessed_unit_keys=unresolved,
                  diagnostics=list(dict.fromkeys(diagnostics)))
    return result


def interpret(request: dict, adapter: Adapter) -> dict:
    """Perform one exchange with independent accounting retained by the caller."""
    request = validate_request(request)
    try:
        response = _adapter_response(adapter(deepcopy(request)))
    except Exception:
        return _empty(request, "invalid_result")
    outcome = response["outcome"]
    if outcome == "refused":
        return _empty(request, "provider_refused", "refused")
    if outcome not in ("completed", "incomplete") or response["structured_output"] is None:
        return _empty(request, "provider_incomplete" if outcome == "incomplete" else "invalid_result")
    try:
        result = validate_result(response["structured_output"], request)
    except ContractError:
        return _empty(request, "invalid_result")
    if outcome == "incomplete":
        result["state"] = "incomplete"
        result["diagnostics"] = list(dict.fromkeys([*result["diagnostics"], "provider_incomplete"]))
    return result
