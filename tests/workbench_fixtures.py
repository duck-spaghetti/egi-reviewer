"""Synthetic public-field workbench packets; no source gold or provider quality data."""
from copy import deepcopy
from datetime import date
from uuid import UUID

from review.matching import context_digest, make_context
from review.workbench import request_digest, scope_key
from review import workbench_profile as profile


def packet(*, task: str = "classify_cards", labels: tuple = ("Corsi di italiano", "CORSI DI ITALIANO")) -> dict:
    """Build deterministic IDs, original decoded fields and one adopted fixture axis."""
    territory, axis, adoption, release, term = (str(UUID(int=n)) for n in range(1, 6))
    catalog = make_context({"context": {"kind": "classification", "territory_id": territory, "axis_id": axis},
        "complete": True, "entries": [{"label": "Corsi di italiano", "published": True,
        "effective_from": "2026-01-01", "effective_until": None, "broader": [],
        "target": {"kind": "classification", "adoption_id": adoption, "release_id": release, "term_id": term, "axis_id": axis}}]}, as_of=date(2026, 11, 27))
    for entry in catalog["entries"]:
        entry.update(definition=None, aliases=[])
    catalog["digest"] = context_digest(catalog)
    ctx = {"context_id": "context-1", "version": 1, "scope": {"preparation_snapshot_key": "snapshot-1", "territory_id": territory, "axis_id": axis},
        "prompt_version": profile.PROMPT_VERSION, "schema_profile_version": profile.SCHEMA_VERSION, "field_dictionary_version": profile.FIELD_VERSION,
        "source_semantics": [{"source_key": "source-1", "rules": ["Public synthetic school network; context is interpretive evidence."]}],
        "source_metadata": [{"source_key": "source-1", "name": "Synthetic school network"}], "catalog_snapshot": {"digest": catalog["digest"]},
        "label_inventory": [], "inventory_coverage": {"complete": True, "total_labels": len(labels), "supplied_labels": len(labels), "omitted_labels": 0}, "limitations": []}
    context = scope_key(ctx)
    data = {key: [] for key in profile.FIELDS["data"]}
    for n, label in enumerate(labels):
        record = f"record-{n}"
        data["records"].append({"record_key": record, "source_key": "source-1", "item_version": f"version-{n}"})
        basis_keys = []
        for kind, text, path in (("category_label", label, "/source_facts/0/source_value"),
                                 ("description", "Caffè e lezioni A1.\r\nA2: martedì 18–20.", "/service/description")):
            basis, support = f"basis-{n}-{kind}", f"support-{n}-{kind}"
            basis_keys.append(basis)
            data["bases"].append({"basis_key": basis, "record_key": record, "kind": kind, "value": text, "support_keys": [support]})
            data["supports"].append({"support_key": support, "record_key": record, "input_key": "input-1", "field_path": path,
                "text": text, "start": 0, "end": len(text), "quote": text, "origin": "source"})
        data["supports"].append({"support_key": f"metadata-{n}", "record_key": record, "input_key": "input-1", "field_path": "/source_metadata/name",
            "text": "Synthetic school network", "start": 0, "end": 24, "quote": "Synthetic school network", "origin": "source_metadata"})
        if task == "classify_cards":
            data["units"].append({"unit_key": f"unit-{n}", "record_key": record, "basis_keys": basis_keys, "member_keys": []})
        else:
            data["labels"].append({"unit_key": f"label-{n}", "label": label, "variants": [], "context_key": context,
                "occurrences": [{"record_key": record, "basis_key": basis_keys[0], "support_keys": [f"support-{n}-category_label"]}], "count": 1})
        ctx["label_inventory"].append({"label": label, "context_key": context, "count": 1})
    if task == "group_labels":
        data["units"].append({"unit_key": "comparison-1", "record_key": None, "basis_keys": [], "member_keys": [label["unit_key"] for label in data["labels"]]})
    ctx["digest"] = context_digest(ctx)
    records = [record["record_key"] for record in data["records"]]
    units = [unit["unit_key"] for unit in data["units"]]
    coverage = {"selection_digest": "a" * 64, "total_units": len(units), "supplied_units": len(units), "omitted_units": 0,
        "sample_policy": "all_frozen_members", "catalog_complete": True, "required_record_keys": records if task == "classify_cards" else [],
        "reference_record_keys": records if task == "group_labels" else [], "required_unit_keys": units, "reference_unit_keys": [], "limitations": []}
    return {"schema_version": 1, "task": task, "plan_key": "plan-1", "packet_key": "packet-1", "preparation_snapshot_key": "snapshot-1",
        "config_version": "config-1", "prompt_version": profile.PROMPT_VERSION, "field_dictionary_version": profile.FIELD_VERSION,
        "policy_version": profile.POLICY_VERSION, "shared_context": ctx, "catalog_context": catalog, "coverage": coverage, "data": data}


def response(request: dict) -> dict:
    """Return explicit controlled abstentions for every required classification basis."""
    proposals, units = [], []
    for unit in request["data"]["units"]:
        refs = []
        for basis in unit["basis_keys"]:
            key = "proposal-" + basis
            refs.append(key)
            proposals.append({"proposal_key": key, "basis_key": basis, "state": "insufficient_context", "choices": [], "missing_context": ["insufficient_context"]})
        units.append({"unit_key": unit["unit_key"], "record_key": unit["record_key"], "state": "insufficient_context",
            "processed_basis_keys": deepcopy(unit["basis_keys"]), "unprocessed_basis_keys": [], "proposal_keys": refs,
            "hypotheses": [], "diagnostics": ["insufficient_context"]})
    return {"schema_version": 1, "task": request["task"], "request_digest": request_digest(request), "state": "complete",
        "unit_results": units, "unprocessed_unit_keys": [], "proposals": proposals, "diagnostics": []}
