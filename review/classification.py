"""Conservative category baseline for the same workbench profile used by optional IA.

propose compares whole original labels/descriptions with actual supplied labels or
aliases only. It emits explicit abstentions rather than importing source-specific
rules or simulating semantic model reasoning. All output remains unconfirmed.
"""
from .insertion_fields import ContractError
from .workbench import normalize_label, request_digest, validate_request, validate_result


def propose(request: dict) -> dict:
    """Return deterministic exact-label candidates or attributable per-basis abstention."""
    request = validate_request(request)
    if request["task"] != "classify_cards":
        raise ContractError("unsupported_field", "/task")
    bases = {basis["basis_key"]: basis for basis in request["data"]["bases"]}
    candidates = request["catalog_context"]["entries"]
    proposals, units = [], []
    for unit in request["data"]["units"]:
        if unit["unit_key"] not in request["coverage"]["required_unit_keys"]:
            continue
        refs, interpreted = [], False
        for key in unit["basis_keys"]:
            basis = bases[key]
            matches = [candidate for candidate in candidates if basis["kind"] in ("category_label", "description")
                       and normalize_label(basis["value"]) in {normalize_label(label) for label in [candidate["label"], *candidate["aliases"]]}]
            missing = [] if request["coverage"]["catalog_complete"] else ["incomplete_catalog"]
            state = "proposed" if 0 < len(matches) <= 5 else "no_supplied_match"
            if len(matches) > 5 or (not matches and basis["kind"] != "category_label"):
                state = "insufficient_context"
                missing.append("insufficient_context")
            choices = [{"candidate_key": candidate["candidate_key"], "reason": "exact_source_label" if basis["kind"] == "category_label" else "exact_description_label",
                        "support_keys": list(basis["support_keys"])} for candidate in matches] if state == "proposed" else []
            proposal_key = "classification:" + key
            refs.append(proposal_key)
            proposals.append({"proposal_key": proposal_key, "basis_key": key, "state": state, "choices": choices, "missing_context": missing})
            interpreted |= state == "insufficient_context"
        units.append({"unit_key": unit["unit_key"], "record_key": unit["record_key"], "state": "insufficient_context" if interpreted else "analyzed",
                      "processed_basis_keys": list(unit["basis_keys"]), "unprocessed_basis_keys": [], "proposal_keys": refs, "hypotheses": [],
                      "diagnostics": ["insufficient_context"] if interpreted else []})
    result = {"schema_version": 1, "task": "classify_cards", "request_digest": request_digest(request), "state": "complete", "unit_results": units,
              "unprocessed_unit_keys": [], "proposals": proposals, "diagnostics": []}
    return validate_result(result, request)
