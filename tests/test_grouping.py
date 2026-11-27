"""Conservative normalization and controlled semantic comparison without real IA."""
from copy import deepcopy
import unittest

from review.grouping import propose
from review.insertion_fields import ContractError
from review.matching import context_digest
from review.workbench import instructions, request_digest, validate_request, validate_result
from tests.test_classification import controlled
from tests.workbench_fixtures import packet, response


def coalesced() -> dict:
    """Represent two original occurrences in one exact contextual label unit."""
    request = packet(task="group_labels", labels=("Corsi di italiano", "temporary"))
    label = request["data"]["labels"][0]
    other = request["data"]["labels"].pop()
    basis, support = request["data"]["bases"][2], request["data"]["supports"][3]
    basis["value"] = label["label"]
    support.update(text=label["label"], quote=label["label"], end=len(label["label"]))
    label["occurrences"].extend(other["occurrences"])
    label["count"] = 2
    request["data"]["units"][0]["member_keys"] = [label["unit_key"]]
    ctx = request["shared_context"]
    ctx["label_inventory"] = [ctx["label_inventory"][0]]
    ctx["label_inventory"][0]["count"] = 2
    ctx["inventory_coverage"].update(total_labels=1, supplied_labels=1)
    ctx["digest"] = context_digest(ctx)
    return request


class GroupingTests(unittest.TestCase):
    """Relations, contextual issues and declared scope stay separate from records."""

    def test_nfc_casefold_whitespace_only(self):
        """Canonical Unicode/case/space variants group without rewriting source labels."""
        request = packet(task="group_labels", labels=("Caffè sociale", "  CAFFE\u0300   SOCIALE "))
        before = deepcopy(request)
        result = propose(request)
        self.assertEqual(len(result["proposals"]), 1)
        self.assertEqual(result["proposals"][0]["relation"], "equivalent")
        self.assertFalse(result["proposals"][0]["choices"])
        self.assertEqual(request, before)

    def test_accent_punctuation_and_word_order_are_not_equivalence(self):
        """Legacy lexical similarity cannot create a deterministic equivalent group."""
        for other in ("Caffe sociale", "Caffè sociale!", "Sociale caffè"):
            request = packet(task="group_labels", labels=("Caffè sociale", other))
            self.assertFalse(propose(request)["proposals"])

    def test_single_coalesced_label_with_multiple_occurrences_groups(self):
        """One supplied label unit can represent two complete original records."""
        request = coalesced()
        result = propose(request)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["proposals"][0]["unit_keys"], ["label-0"])
        self.assertEqual(len(result["proposals"][0]["support_keys"]), 2)
        request["data"]["seed_groups"] = [{"group_key": "seed-1", "unit_keys": ["label-0"], "relation": "equivalent"}]
        validate_request(request)

    def test_single_unrepeated_occurrence_cannot_be_group(self):
        """A one-occurrence singleton does not manufacture a group or coverage."""
        request = packet(task="group_labels", labels=("Alone",))
        self.assertFalse(propose(request)["proposals"])
        request["data"]["seed_groups"] = [{"group_key": "seed-1", "unit_keys": ["label-0"], "relation": "equivalent"}]
        with self.assertRaises(ContractError):
            validate_request(request)

    def test_homonym_mixed_and_unknown_context_remains_ambiguous(self):
        """Equal labels across incompatible contexts cannot become applicable mapping."""
        for value in (None, "f" * 64):
            request = packet(task="group_labels", labels=("Supporto", "SUPPORTO"))
            request["data"]["labels"][1]["context_key"] = value
            result = propose(request)
            self.assertEqual(result["proposals"][0]["relation"], "ambiguous")
            self.assertTrue(result["proposals"][0]["membership_issues"])
            self.assertFalse(result["proposals"][0]["choices"])
            self.assertEqual(result["unit_results"][0]["state"], "insufficient_context")

    def test_unsampled_occurrences_do_not_disappear(self):
        """An ambiguous supplied comparison never completes omitted occurrences."""
        request = coalesced()
        request["data"]["labels"][0]["count"] = 3
        result = propose(request)
        self.assertEqual(result["proposals"][0]["relation"], "ambiguous")
        self.assertIn("unsampled_occurrences", result["proposals"][0]["membership_issues"][0]["reason"])
        self.assertEqual(request["data"]["labels"][0]["count"], 3)
        self.assertEqual(len(request["data"]["labels"][0]["occurrences"]), 2)

    def test_materialized_interpretations_not_automatic_literal_equivalence(self):
        """Repeated original descriptions remain interpreted and need semantic review."""
        request = packet(task="group_labels")
        for n, label in enumerate(request["data"]["labels"]):
            label["label"] = request["data"]["bases"][n * 2 + 1]["value"]
            label["unit_key"] = f"interpretation:{n}"
            label["occurrences"][0].update(basis_key=f"basis-{n}-description", support_keys=[f"support-{n}-description"])
        request["data"]["units"][0]["member_keys"] = [label["unit_key"] for label in request["data"]["labels"]]
        result = propose(request)
        self.assertEqual(result["proposals"][0]["relation"], "ambiguous")
        self.assertIn("interpreted_basis_requires_semantic_review", result["proposals"][0]["membership_issues"][0]["reason"])
        self.assertFalse(result["proposals"][0]["choices"])

    def test_related_education_semantic_result_does_not_claim_synonymy(self):
        """One controlled exchange may relate distinct activities without equivalent merge."""
        request = packet(task="group_labels", labels=("Sostegno scolastico", "Corsi di italiano"))
        self.assertFalse(propose(request)["proposals"])
        result = response(request)
        result["proposals"] = [{"proposal_key": "semantic-1", "relation": "related", "unit_keys": ["label-0", "label-1"],
                                "membership_issues": [], "choices": [], "reason": "Education offers, different activities",
                                "support_keys": ["support-0-category_label", "support-1-category_label"]}]
        result["unit_results"][0]["proposal_keys"] = ["semantic-1"]
        validated = controlled(request, result)
        self.assertEqual(validated["proposals"][0]["relation"], "related")
        self.assertNotIn("merge", validated["proposals"][0])
        result["proposals"][0]["support_keys"] += ["support-0-description", "metadata-1"]
        self.assertEqual(controlled(request, result)["state"], "complete")

    def test_original_support_and_priors_across_sources(self):
        """Comparison carries originals and actual alternatives, never model summaries only."""
        request = packet(task="group_labels")
        request["data"]["records"][1]["source_key"] = "source-2"
        ctx = request["shared_context"]
        ctx["source_semantics"].append({"source_key": "source-2", "rules": ["Different synthetic structure"]})
        ctx["source_metadata"].append({"source_key": "source-2", "name": "Synthetic school network"})
        ctx["digest"] = context_digest(ctx)
        prior = {"proposal_key": "prior-1", "basis_key": "basis-0-category_label", "state": "proposed", "choices": [{"candidate_key": "catalog-1", "reason": "Original candidate alternative", "support_keys": ["support-0-category_label"]}], "missing_context": []}
        request["data"]["prior_proposals"] = [prior]
        self.assertTrue(propose(request)["proposals"])
        prior["choices"][0]["candidate_key"] = "absent-prior-candidate"
        with self.assertRaises(ContractError):
            validate_request(request)
        prior.update(state="insufficient_context", choices=[], missing_context=["incomplete_catalog"])
        self.assertTrue(propose(request)["proposals"])
        request["data"]["supports"] = []
        with self.assertRaises(ContractError):
            validate_request(request)

    def test_reference_records_cannot_complete_record_analysis(self):
        """Only comparison scope is required; label appearance is never record credit."""
        request = packet(task="group_labels")
        result = propose(request)
        self.assertEqual(request["coverage"]["required_record_keys"], [])
        self.assertEqual(len(request["coverage"]["reference_record_keys"]), 2)
        self.assertEqual(result["unit_results"][0]["record_key"], None)
        result["unit_results"][0]["unit_key"] = "label-0"
        invalid = validate_result(result, request)
        self.assertEqual(invalid["unprocessed_unit_keys"], ["comparison-1"])

    def test_long_tail_inventory_and_prompt_scope_stay_explicit(self):
        """Complete supplied comparison does not upgrade partial label inventory."""
        request = packet(task="group_labels")
        ctx = request["shared_context"]
        ctx["inventory_coverage"].update(complete=False, total_labels=12, omitted_labels=10)
        ctx["limitations"] = ["unsampled_occurrences"]
        ctx["digest"] = context_digest(ctx)
        result = propose(request)
        self.assertEqual(result["state"], "complete")
        self.assertFalse(ctx["inventory_coverage"]["complete"])
        for phrase in ("original supporting passages", "related", "prior proposals", "Distinct label-unit count is not occurrence count"):
            self.assertIn(phrase, instructions(request))

    def test_deterministic_task_rejection_and_output_closure(self):
        """Neither deterministic baseline nor IA group output has mutation authority."""
        with self.assertRaises(ContractError):
            propose(packet())
        request = packet(task="group_labels")
        result = propose(request)
        result["proposals"][0]["term_id"] = "forbidden"
        self.assertEqual(validate_result(result, request)["state"], "incomplete")
