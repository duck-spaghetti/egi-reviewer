"""Verify frozen context, exact support, partial recovery and one-exchange mechanics."""
from copy import deepcopy
import unittest

from review.insertion_fields import ContractError
from review.matching import context_digest
from review.workbench import canonical_json, input_bound, instructions, interpret, output_schema, request_digest, scope_key, validate_request, validate_result
from tests.workbench_fixtures import packet, response


class WorkbenchTests(unittest.TestCase):
    """Protocol tests use synthetic decoded fields and never call a real provider."""

    def test_valid_request_and_independent_copy(self):
        """Exact field views, metadata and CRLF survive validation unchanged."""
        request = packet()
        self.assertEqual(validate_request(request), request)
        clone = validate_request(request)
        clone["data"]["supports"][0]["text"] = "changed"
        self.assertNotEqual(clone, request)
        self.assertEqual(request_digest({"é": "\r\n", "b": 1}), "c8d0c027f490a673576f1d357b2e4cbda72f81825b2877cb4c15e28a1c4e5a72")

    def test_closed_versions_digests_and_actual_context(self):
        """Unknown fields/versions, fake context content and wrong scope fail closed."""
        for mutate in (lambda r: r.update(extra=True), lambda r: r.update(policy_version="future"),
                       lambda r: r["shared_context"].update(digest="0" * 64),
                       lambda r: r["catalog_context"]["entries"][0].update(definition="invented"),
                       lambda r: r["shared_context"]["scope"].update(axis_id="foreign")):
            request = packet()
            mutate(request)
            with self.assertRaises(ContractError):
                validate_request(request)

    def test_slice_changes_do_not_change_semantic_scope(self):
        """Snapshot identity survives a supplied-catalog slice, choices do not."""
        request = packet()
        key = scope_key(request["shared_context"])
        request["catalog_context"]["entries"] = []
        request["catalog_context"]["complete"] = False
        request["catalog_context"]["digest"] = context_digest(request["catalog_context"])
        request["coverage"]["catalog_complete"] = False
        validate_request(request)
        self.assertEqual(scope_key(request["shared_context"]), key)
        result = response(request)
        result["proposals"][0].update(state="proposed", choices=[{"candidate_key": "catalog-1", "reason": "old slice", "support_keys": ["support-0-category_label"]}], missing_context=["incomplete_catalog"])
        self.assertEqual(validate_result(result, request)["unprocessed_unit_keys"], ["unit-0", "unit-1"])

    def test_exact_quote_and_source_metadata_origin(self):
        """Wrong Unicode offsets, normalized quotes and forged metadata are rejected."""
        for mutate in (lambda s: s.update(quote=s["quote"].replace("è", "e")), lambda s: s.update(end=s["end"] - 1),
                       lambda s: s.update(origin="source_metadata"), lambda s: s.update(record_key="foreign")):
            request = packet()
            mutate(request["data"]["supports"][1])
            with self.assertRaises(ContractError):
                validate_request(request)

    def test_required_reference_and_duplicate_input_keys(self):
        """Reference-only appearance and repeated opaque identities earn no work."""
        for mutate in (lambda r: r["coverage"]["reference_record_keys"].append("record-0"),
                       lambda r: r["data"]["records"].append(deepcopy(r["data"]["records"][0])),
                       lambda r: r["data"]["units"][0]["basis_keys"].append("foreign")):
            request = packet()
            mutate(request)
            with self.assertRaises(ContractError):
                validate_request(request)

    def test_partial_missing_basis_retains_independent_outcomes(self):
        """Bare processed claims are demoted, with valid sibling bases retained."""
        request = packet()
        result = response(request)
        result["proposals"].pop(1)
        validated = validate_result(result, request)
        self.assertEqual(validated["state"], "incomplete")
        self.assertEqual(validated["unit_results"][0]["processed_basis_keys"], ["basis-0-category_label"])
        self.assertEqual(validated["unit_results"][0]["unprocessed_basis_keys"], ["basis-0-description"])
        self.assertEqual(len(validated["unit_results"]), 2)

    def test_foreign_support_invalidates_only_owning_unit(self):
        """Another record's evidence cannot support a choice or contaminate siblings."""
        request = packet()
        result = response(request)
        result["proposals"][0].update(state="proposed", choices=[{"candidate_key": "catalog-1", "reason": "literal", "support_keys": ["support-1-category_label"]}], missing_context=[])
        validated = validate_result(result, request)
        self.assertEqual(validated["unprocessed_unit_keys"], ["unit-0"])
        self.assertEqual([unit["unit_key"] for unit in validated["unit_results"]], ["unit-1"])

    def test_duplicate_units_and_proposals_never_first_win(self):
        """All units implicated by duplicate identity lose coverage explicitly."""
        request = packet()
        for target in ("unit_results", "proposals"):
            result = response(request)
            result[target].append(deepcopy(result[target][0]))
            validated = validate_result(result, request)
            self.assertEqual(validated["unprocessed_unit_keys"], ["unit-0"])
            self.assertEqual(validated["state"], "incomplete")

    def test_outer_binding_is_fatal(self):
        """Correct siblings cannot salvage a result for another packet."""
        request = packet()
        for mutate in (lambda r: r.update(request_digest="0" * 64), lambda r: r.update(task="group_labels"), lambda r: r.update(sql="unsafe")):
            result = response(request)
            mutate(result)
            with self.assertRaises(ContractError):
                validate_result(result, request)

    def test_hypotheses_optional_unverified_and_not_category_proof(self):
        """Trigger-only expansions cannot justify a category; independent support can."""
        request = packet()
        result = response(request)
        hypothesis = {"hypothesis_key": "h-1", "kind": "abbreviation_expansion", "statement": "Possible expansion to check", "status": "unverified",
                      "trigger_support_keys": ["support-0-category_label"], "verification_needed": True}
        result["unit_results"][0]["hypotheses"] = [hypothesis]
        result["proposals"][0].update(state="proposed", choices=[{"candidate_key": "catalog-1", "reason": "literal", "support_keys": ["support-0-category_label"]}], missing_context=[])
        self.assertEqual(validate_result(result, request)["unprocessed_unit_keys"], ["unit-0"])
        result["proposals"][0]["choices"][0]["support_keys"].append("support-0-description")
        self.assertEqual(validate_result(result, request)["state"], "complete")
        hypothesis["status"] = "verified"
        self.assertEqual(validate_result(result, request)["state"], "incomplete")

    def test_schema_prompt_and_preflight_single_source(self):
        """Generated task/schema binding and measured bytes stay below profile cap."""
        request = packet()
        schema = output_schema(request)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["request_digest"]["enum"], [request_digest(request)])
        self.assertIn("untrusted data", instructions(request))
        bound = input_bound(request)
        self.assertEqual(bound["request_bytes"], len(canonical_json(canonical_json(request)).encode()))
        self.assertLess(bound["instructions_bytes"] + bound["schema_bytes"], 32768)

    def test_adapter_one_exchange_partial_and_independent_usage(self):
        """Parseable partial units survive one exchange; accounting object is untouched."""
        request, calls = packet(), []
        output = response(request)
        envelope = {"outcome": "incomplete", "provider_request_id": "test", "structured_output": output,
                    "usage": {"input_tokens": 10, "output_tokens": 20}, "error_code": "incomplete"}
        before = deepcopy(envelope)
        def adapter(value):
            """Record the only dispatch and supply a controlled adapter envelope."""
            calls.append(value)
            return envelope
        validated = interpret(request, adapter)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(validated["unit_results"]), 2)
        self.assertEqual(validated["state"], "incomplete")
        self.assertEqual(envelope, before)
        envelope["structured_output"] = None
        self.assertFalse(interpret(request, adapter)["unit_results"])

    def test_refusal_and_invalid_request_never_repair(self):
        """Invalid input makes zero calls and refusal returns only unresolved work."""
        calls, request = [], packet()
        def adapter(value):
            """Return a refusal without a model result or a second attempt."""
            calls.append(value)
            return {"outcome": "refused", "provider_request_id": None, "structured_output": None, "usage": None, "error_code": "refusal"}
        self.assertEqual(interpret(request, adapter)["state"], "refused")
        request["schema_version"] = 9
        with self.assertRaises(ContractError):
            interpret(request, adapter)
        self.assertEqual(len(calls), 1)

    def test_group_support_and_context_are_member_bound(self):
        """A valid comparison cannot borrow another label's evidence or scope."""
        request = packet(task="group_labels", labels=("A", "B", "C"))
        result = response(request)
        proposal = {"proposal_key": "group-1", "relation": "related", "unit_keys": ["label-0", "label-1"],
                    "membership_issues": [], "choices": [], "reason": "Related offers", "support_keys": ["support-0-category_label"]}
        result["proposals"] = [proposal]
        result["unit_results"][0]["proposal_keys"] = ["group-1"]
        self.assertEqual(validate_result(result, request)["state"], "complete")
        proposal["support_keys"] = ["support-2-category_label"]
        self.assertEqual(validate_result(result, request)["state"], "incomplete")
        proposal["support_keys"] = ["support-0-category_label"]
        request["data"]["labels"][0]["context_key"] = None
        result["request_digest"] = request_digest(request)
        self.assertEqual(validate_result(result, request)["state"], "incomplete")
        proposal["membership_issues"] = [{"unit_key": "label-0", "reason": "Unknown context"}]
        self.assertEqual(validate_result(result, request)["state"], "complete")

    def test_unsampled_group_members_never_equivalent(self):
        """Explicit abstention covers only supplied comparison, never missing members."""
        request = packet(task="group_labels")
        request["data"]["labels"][0]["count"] = 2
        result = response(request)
        proposal = {"proposal_key": "group-1", "relation": "equivalent", "unit_keys": ["label-0", "label-1"],
                    "membership_issues": [], "choices": [], "reason": "Same label", "support_keys": ["support-0-category_label"]}
        result["proposals"] = [proposal]
        result["unit_results"][0]["proposal_keys"] = ["group-1"]
        self.assertEqual(validate_result(result, request)["state"], "incomplete")
        proposal.update(relation="ambiguous", membership_issues=[{"unit_key": "label-0", "reason": "unsampled_occurrences"}])
        validated = validate_result(result, request)
        self.assertEqual(validated["state"], "complete")
        self.assertEqual(validated["unit_results"][0]["state"], "insufficient_context")

    def test_hostile_types_and_json_string_framing(self):
        """Malformed reference types fail safely and quote-heavy framing stays bounded."""
        request = packet()
        request["data"]["records"][0]["source_key"] = []
        with self.assertRaises(ContractError):
            validate_request(request)
        request = packet()
        support = request["data"]["supports"][1]
        support.update(text='"\\' * 100, quote='"\\' * 100, end=200)
        request["data"]["bases"][1]["value"] = support["text"]
        bound = input_bound(request)
        self.assertGreater(bound["request_bytes"], len(canonical_json(request).encode()))

    def test_interpreted_label_preserves_original_description_basis(self):
        """A materialized interpretation never disguises a description as a literal label."""
        request = packet(task="group_labels")
        label = request["data"]["labels"][0]
        label["unit_key"] = "interpretation:controlled-1"
        label["label"] = request["data"]["bases"][1]["value"]
        label["occurrences"][0].update(basis_key="basis-0-description", support_keys=["support-0-description"])
        request["data"]["units"][0]["member_keys"][0] = label["unit_key"]
        self.assertEqual(validate_request(request)["data"]["bases"][1]["kind"], "description")
        label["label"] = "picked candidate text"
        with self.assertRaises(ContractError):
            validate_request(request)

    def test_explicit_abstentions_override_supplied_classify_unit_state(self):
        """Validated abstentions remain the insufficient-context subset of analyzed work."""
        request = packet()
        for supplied in ("analyzed", "not_analyzed"):
            with self.subTest(supplied=supplied):
                result = response(request)
                for unit in result["unit_results"]:
                    unit.update(state=supplied, diagnostics=[])
                validated = validate_result(result, request)
                self.assertEqual(validated["state"], "complete")
                self.assertTrue(all(unit["state"] == "insufficient_context" for unit in validated["unit_results"]))
                self.assertTrue(all("insufficient_context" in unit["diagnostics"] for unit in validated["unit_results"]))
                self.assertEqual(len(validated["proposals"]), 4)

    def test_mixed_abstention_keeps_valid_category_choice(self):
        """One abstaining basis cannot relabel the unit validated or discard a valid choice."""
        request = packet()
        result = response(request)
        result["unit_results"][0].update(state="analyzed", diagnostics=[])
        result["proposals"][0].update(state="proposed", missing_context=[], choices=[{
            "candidate_key": "catalog-1", "reason": "Literal label", "support_keys": ["support-0-category_label"]}])
        validated = validate_result(result, request)
        self.assertEqual(validated["unit_results"][0]["state"], "insufficient_context")
        self.assertEqual(validated["proposals"][0]["choices"][0]["candidate_key"], "catalog-1")
        self.assertEqual(len(validated["unit_results"][0]["processed_basis_keys"]), 2)

    def test_partial_abstention_and_independent_no_match_are_derived_separately(self):
        """Unresolved bases stay partial while independent explicit no-match stays analyzed."""
        request = packet()
        result = response(request)
        result["unit_results"][0].update(state="analyzed", diagnostics=[])
        result["proposals"].pop(1)
        for proposal in result["proposals"][1:]:
            proposal.update(state="no_supplied_match", missing_context=[])
        validated = validate_result(result, request)
        self.assertEqual(validated["state"], "incomplete")
        self.assertEqual(validated["unit_results"][0]["state"], "insufficient_context")
        self.assertEqual(validated["unit_results"][0]["processed_basis_keys"], ["basis-0-category_label"])
        self.assertEqual(validated["unit_results"][0]["unprocessed_basis_keys"], ["basis-0-description"])
        self.assertEqual(validated["unit_results"][1]["state"], "analyzed")

    def test_absent_outcomes_and_partial_catalog_choices_do_not_imply_abstention(self):
        """Missing work stays unprocessed; useful bounded-catalog choices stay analyzed."""
        request = packet(labels=("Corsi di italiano",))
        result = response(request)
        result["unit_results"][0].update(state="analyzed", diagnostics=[])
        result["proposals"] = []
        missing = validate_result(result, request)
        self.assertEqual(missing["unit_results"][0]["state"], "not_analyzed")
        self.assertEqual(missing["unit_results"][0]["processed_basis_keys"], [])
        self.assertEqual(missing["state"], "incomplete")
        request["data"]["units"][0]["basis_keys"] = ["basis-0-category_label"]
        request["catalog_context"]["complete"] = False
        request["catalog_context"]["digest"] = context_digest(request["catalog_context"])
        request["coverage"]["catalog_complete"] = False
        result = response(request)
        result["unit_results"][0]["diagnostics"] = []
        result["proposals"][0].update(state="proposed", missing_context=["incomplete_catalog"], choices=[{
            "candidate_key": "catalog-1", "reason": "Valid supplied choice", "support_keys": ["support-0-category_label"]}])
        useful = validate_result(result, request)
        self.assertEqual(useful["unit_results"][0]["state"], "analyzed")
        self.assertEqual(useful["proposals"][0]["missing_context"], ["incomplete_catalog"])
