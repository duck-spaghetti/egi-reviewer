"""Conservative spelling groups with original occurrences and optional IA comparison.

propose supplies only deterministic NFC/casefold/whitespace groups. Contextual
semantic relations use the shared workbench one-exchange Adapter and schema, not
lexical similarity or a second model call. No grouping mutates source/canonical data.
"""
from collections import defaultdict

from .insertion_fields import ContractError
from .workbench import normalize_label, request_digest, scope_key, validate_request, validate_result


def _issues(label: dict, bases: dict, context: str) -> list:
    """Identify why a spelling match cannot become deterministic equivalence."""
    issues = []
    if label["context_key"] is None:
        issues.append("unknown_context")
    elif label["context_key"] != context:
        issues.append("mixed_context")
    if label["count"] != len(label["occurrences"]):
        issues.append("unsampled_occurrences")
    if any(bases[occurrence["basis_key"]]["kind"] != "category_label" for occurrence in label["occurrences"]):
        issues.append("interpreted_basis_requires_semantic_review")
    if any(normalize_label(variant) != normalize_label(label["label"]) for variant in label["variants"]):
        issues.append("non_equivalent_variants")
    return issues


def propose(request: dict) -> dict:
    """Group literal spelling variants only, retaining unsafe matches as ambiguous."""
    request = validate_request(request)
    if request["task"] != "group_labels":
        raise ContractError("unsupported_field", "/task")
    labels = {label["unit_key"]: label for label in request["data"]["labels"]}
    bases = {basis["basis_key"]: basis for basis in request["data"]["bases"]}
    context = scope_key(request["shared_context"])
    proposals, units = [], []
    for unit in request["data"]["units"]:
        if unit["unit_key"] not in request["coverage"]["required_unit_keys"]:
            continue
        buckets = defaultdict(list)
        for key in unit["member_keys"]:
            label = labels[key]
            buckets[normalize_label(label["label"])].append(key)
        refs, issues_present = [], False
        for normalized in sorted(buckets):
            keys = sorted(buckets[normalized])
            if len(keys) < 2 and labels[keys[0]]["count"] < 2:
                continue
            issues = [{"unit_key": key, "reason": ", ".join(_issues(labels[key], bases, context))}
                      for key in keys if _issues(labels[key], bases, context)]
            relation = "ambiguous" if issues else "equivalent"
            issues_present |= bool(issues)
            proposal_key = "spelling-group:" + request_digest({"unit_key": unit["unit_key"], "member_keys": keys})
            supports = sorted({support for key in keys for occurrence in labels[key]["occurrences"] for support in occurrence["support_keys"]})
            proposals.append({"proposal_key": proposal_key, "relation": relation, "unit_keys": keys, "membership_issues": issues,
                              "choices": [], "reason": "Spelling variants require contextual review" if issues else "NFC, casefold and whitespace variants of literal source labels",
                              "support_keys": supports})
            refs.append(proposal_key)
        diagnostics = ["insufficient_context"] if issues_present else []
        units.append({"unit_key": unit["unit_key"], "record_key": None, "state": "insufficient_context" if issues_present else "analyzed",
                      "processed_basis_keys": [], "unprocessed_basis_keys": [], "proposal_keys": refs, "hypotheses": [], "diagnostics": diagnostics})
    return validate_result({"schema_version": 1, "task": "group_labels", "request_digest": request_digest(request), "state": "complete",
                            "unit_results": units, "unprocessed_unit_keys": [], "proposals": proposals, "diagnostics": []}, request)
