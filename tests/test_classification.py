"""Controlled exploration-policy mechanics, not approved gold or real-model quality."""
from copy import deepcopy
import unittest

from review.classification import propose
from review.insertion_fields import ContractError
from review.matching import context_digest
from review.workbench import instructions, interpret, request_digest, scope_key
from tests.workbench_fixtures import packet, response


def example(label: str, description: str, candidate: str) -> dict:
    """Use synthetic policy equivalents while retaining original field ownership."""
    request = packet(labels=(label,))
    request["catalog_context"]["entries"][0]["label"] = candidate
    request["catalog_context"]["digest"] = context_digest(request["catalog_context"])
    ctx = request["shared_context"]
    ctx["catalog_snapshot"]["digest"] = request["catalog_context"]["digest"]
    ctx["label_inventory"][0]["context_key"] = scope_key(ctx)
    ctx["digest"] = context_digest(ctx)
    basis, support = request["data"]["bases"][1], request["data"]["supports"][1]
    basis["value"] = description
    support.update(text=description, quote=description, end=len(description))
    return request


def controlled(request: dict, result: dict) -> dict:
    """Run one fake exchange, preserving the actual workbench semantic boundary."""
    def adapter(value):
        """Return manually authored controlled output without any model call."""
        return {"outcome": "completed", "provider_request_id": "controlled", "structured_output": result,
                "usage": {"input_tokens": 1, "output_tokens": 1}, "error_code": None}
    return interpret(request, adapter)


class ClassificationTests(unittest.TestCase):
    """Baseline abstention and optional semantic proposals share closed contracts."""

    def test_exact_baseline_preserves_accents_punctuation_and_source(self):
        """No legacy lexical-score or accent stripping establishes a category match."""
        for label, expected in (("  CORSI  DI ITALIANO ", True), ("Corsi di italiano!", False), ("Córsi di italiano", False)):
            request = packet(labels=(label,))
            before = deepcopy(request)
            result = propose(request)
            self.assertEqual(bool(result["proposals"][0]["choices"]), expected)
            self.assertEqual(result["proposals"][1]["state"], "insufficient_context")
            self.assertEqual(request, before)
            self.assertEqual(result["unit_results"][0]["hypotheses"], [])

    def test_only_actually_supplied_aliases_support_baseline(self):
        """Missing catalog enrichment stays missing rather than invented by Reviewer."""
        request = packet(labels=("Italiano L2",))
        self.assertFalse(propose(request)["proposals"][0]["choices"])
        request["catalog_context"]["entries"][0]["aliases"] = ["Italiano L2"]
        request["catalog_context"]["digest"] = context_digest(request["catalog_context"])
        self.assertEqual(propose(request)["proposals"][0]["choices"][0]["candidate_key"], "catalog-1")

    def test_incomplete_catalog_and_no_match_stay_explicit(self):
        """An analyzed bounded no-match is never a claim about the whole taxonomy."""
        request = packet(labels=("Unknown label",))
        request["catalog_context"]["complete"] = False
        request["catalog_context"]["digest"] = context_digest(request["catalog_context"])
        request["coverage"]["catalog_complete"] = False
        result = propose(request)
        self.assertEqual(result["proposals"][0]["state"], "no_supplied_match")
        self.assertIn("incomplete_catalog", result["proposals"][0]["missing_context"])

    def test_h02_activity_audience_default_flags_are_not_rewritten(self):
        """Synthetic school support keeps audience and a misleading proper name apart."""
        request = example("Minori", "Casa Famiglia Example: sostegno scolastico; a_pagamento=false; stranieri=false.", "Minori e famiglie")
        before = deepcopy(request)
        result = response(request)
        result["proposals"][0].update(state="proposed", choices=[{"candidate_key": "catalog-1", "reason": "Audience label; family access is unconfirmed", "support_keys": ["support-0-category_label"]}], missing_context=[])
        validated = controlled(request, result)
        self.assertEqual(validated["state"], "complete")
        self.assertEqual(request, before)
        prompt = instructions(request)
        for phrase in ("Separate offered activity from audience", "False/default flags", "proper name", "unrestricted family access"):
            self.assertIn(phrase, prompt)

    def test_h09_one_legal_service_appointment_unknown_cost(self):
        """Related legal labels do not force duplicate services or a free-cost claim."""
        request = example("Supporto legale", "Consulenza legale e assistenza, su appuntamento; a_pagamento=false.", "Consulenza legale")
        result = controlled(request, response(request))
        self.assertEqual(len(result["unit_results"]), 1)
        self.assertEqual(result["task"], "classify_cards")
        prompt = instructions(request)
        for phrase in ("one service without being perfect synonyms", "appointment", "Unknown cost remains unknown"):
            self.assertIn(phrase, prompt)

    def test_s05_level_schedules_and_temporal_claims_remain_separate(self):
        """One record retains map/page and level/time claims without adjudicating dates."""
        description = "Mappa: A1 lunedì18–20, A2 martedì18–20 (stagione non chiara). Pagina: giovedì17–19. Segreteria10–12."
        request = example("Attività didattiche", description, "Corsi di italiano")
        result = response(request)
        result["proposals"][1].update(state="proposed", choices=[{"candidate_key": "catalog-1", "reason": "Interpretation from school context; human confirmation required", "support_keys": ["support-0-description", "metadata-0"]}], missing_context=[])
        validated = controlled(request, result)
        self.assertEqual(len(validated["unit_results"]), 1)
        self.assertEqual(request["data"]["bases"][1]["value"], description)
        prompt = instructions(request)
        for phrase in ("Never split a service solely by course", "contact hours", "temporal applicability", "interpreted Italian-course proposal"):
            self.assertIn(phrase, prompt)

    def test_description_only_contextual_proposal_stays_interpreted(self):
        """Synthetic S09 equivalent has no source category and no invented literal fact."""
        request = example("to remove", "A1 e A2 per adulti: iscrizioni in segreteria.", "Corsi di italiano")
        request["data"]["bases"].pop(0)
        request["data"]["supports"].pop(0)
        request["data"]["units"][0]["basis_keys"].pop(0)
        request["shared_context"]["label_inventory"] = []
        request["shared_context"]["inventory_coverage"].update(total_labels=0, supplied_labels=0)
        request["shared_context"]["digest"] = context_digest(request["shared_context"])
        self.assertEqual(propose(request)["proposals"][0]["state"], "insufficient_context")
        result = response(request)
        result["proposals"][0].update(state="proposed", choices=[{"candidate_key": "catalog-1", "reason": "Interpreted from original description and school-network context", "support_keys": ["support-0-description", "metadata-0"]}], missing_context=[])
        self.assertEqual(controlled(request, result)["state"], "complete")
        result["proposals"][0]["source_fact"] = "invented literal label"
        self.assertEqual(controlled(request, result)["state"], "incomplete")

    def test_c06_facility_name_does_not_enumerate_unstated_care(self):
        """A synthetic facility name can support a category without new service facts."""
        request = example("Registro strutture", "Consultorio Familiare Example", "Consultori familiari")
        result = response(request)
        result["proposals"][1].update(state="proposed", choices=[{"candidate_key": "catalog-1", "reason": "Facility-name interpretation only; confirm category", "support_keys": ["support-0-description"]}], missing_context=[])
        self.assertEqual(controlled(request, result)["state"], "complete")
        self.assertIn("never every clinical service", instructions(request))
        self.assertFalse(propose(request)["proposals"][1]["choices"])

    def test_c04_abbreviation_is_optional_hypothesis_not_assignment(self):
        """A synthetic opaque sigla has no deterministic category or verified expansion."""
        request = example("C.F.", "C.F. Example", "Consultori familiari")
        baseline = propose(request)
        self.assertFalse(any(proposal["choices"] for proposal in baseline["proposals"]))
        result = response(request)
        result["unit_results"][0]["hypotheses"] = [{"hypothesis_key": "sigla-1", "kind": "abbreviation_expansion", "statement": "Possible expansion, to verify", "status": "unverified", "trigger_support_keys": ["support-0-category_label"], "verification_needed": True}]
        self.assertEqual(controlled(request, result)["state"], "complete")
        self.assertFalse(any(proposal["choices"] for proposal in result["proposals"]))

    def test_no_other_task_or_fabricated_confidence(self):
        """Baseline rejects a grouping packet and model confidence is outside schema."""
        with self.assertRaises(ContractError):
            propose(packet(task="group_labels"))
        request = packet(labels=("Corsi di italiano",))
        result = propose(request)
        result["proposals"][0]["choices"][0]["confidence"] = 0.99
        self.assertEqual(controlled(request, result)["state"], "incomplete")
