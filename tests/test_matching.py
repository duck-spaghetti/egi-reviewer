"""Exercise context-bound lexical and same-exchange IA suggestions without network."""
from copy import deepcopy
from datetime import date
import unittest
from uuid import uuid4

from review.insertion import interpret
from review.insertion_fields import ContractError, VERSION_V2
from review.insertion import OUTPUT_SHAPE_V2
from review.matching import context_digest, make_context, propose, resolve_matches, validate_context, validate_matches
from tests.test_insertion import FakeAdapter, request, candidate, citation, result


TODAY = date(2026, 11, 27)


def page(labels: tuple[str, ...] = ("Pasto sul posto (mensa)", "Distribuzione pasti"), *, complete: bool = True) -> dict:
    """Build one adopted service-type axis with distinct actual-looking fixture IDs."""
    territory, axis, adoption, release = (str(uuid4()) for _ in range(4))
    return {"context": {"kind": "classification", "territory_id": territory, "axis_id": axis}, "complete": complete,
            "entries": [{"label": label, "published": True, "effective_from": "2026-01-01", "effective_until": None,
                         "target": {"kind": "classification", "adoption_id": adoption, "release_id": release,
                                    "term_id": str(uuid4()), "axis_id": axis}, "broader": []} for label in labels]}


def fact(value: str, key: str = "source-category") -> dict:
    """Preserve one exact source label with a local per-card fact key."""
    return {"fact_key": key, "subject": "service", "kind": "category_label", "source_value": value}


class MatchingTests(unittest.TestCase):
    """Suggestions retain literal claims, bounded context and human confirmation."""

    def test_normalized_equivalent_labels_preserve_source(self) -> None:
        """Case, accents, whitespace and punctuation affect comparison only."""
        context = make_context(page(("Caffè sociale",)), as_of=TODAY)
        facts = [fact("  CAFFE SOCIALE! ")]
        original = deepcopy(facts)
        matches = propose(facts, context)
        self.assertEqual(matches[0]["choices"][0]["reason"], "normalized_label")
        resolved = resolve_matches(matches, facts, context)
        self.assertEqual(resolved[0]["state"], "proposed")
        self.assertNotIn("selected", resolved[0])
        self.assertEqual(facts, original)

    def test_multiple_categories_are_ordinal_suggestions(self) -> None:
        """Overlapping explicit labels may suggest several terms without selection."""
        context = make_context(page(), as_of=TODAY)
        output = resolve_matches(propose([fact("Mensa e distribuzione pasti")], context), [fact("Mensa e distribuzione pasti")], context)
        self.assertEqual([item["rank"] for item in output[0]["candidates"]], [1, 2])
        self.assertTrue(all("confidence" not in item for item in output[0]["candidates"]))

    def test_no_match_and_incomplete_coverage_remain_explicit(self) -> None:
        """No match refers only to the bounded supplied catalog, not a whole ontology."""
        context = make_context(page(complete=False), as_of=TODAY)
        matches = propose([fact("Consulenza legale")], context)
        self.assertEqual(matches[0]["choices"], [])
        self.assertFalse(context["complete"])
        self.assertEqual(resolve_matches(matches, [fact("Consulenza legale")], context)[0]["state"], "unresolved")

    def test_unknown_territory_or_axis_fails(self) -> None:
        """Missing context cannot confidently compare unrelated taxonomy axes."""
        for key in ("territory_id", "axis_id"):
            source = page()
            del source["context"][key]
            with self.assertRaises(ContractError):
                make_context(source, as_of=TODAY)

    def test_same_label_on_another_axis_is_not_a_candidate(self) -> None:
        """A term cannot disguise a different axis through a familiar label."""
        source = page(("Mensa", "Mensa"))
        source["entries"][1]["target"]["axis_id"] = str(uuid4())
        with self.assertRaises(ContractError):
            make_context(source, as_of=TODAY)

    def test_inactive_future_and_expired_entries_fail_closed(self) -> None:
        """Both effective endpoints and active state are required before matching."""
        for change in ({"active": False}, {"effective_from": "2026-11-28"}, {"effective_until": "2026-11-26"}):
            source = page()
            source["entries"][0].update(change)
            with self.assertRaises(ContractError):
                make_context(source, as_of=TODAY)

    def test_digest_binds_heads_labels_coverage_and_context(self) -> None:
        """A changed catalog cannot reuse a prior matching result silently."""
        context = make_context(page(), as_of=TODAY)
        for field, replacement in (("complete", False), ("as_of", "2026-11-26")):
            changed = deepcopy(context)
            changed[field] = replacement
            with self.assertRaises(ContractError):
                validate_context(changed)
        changed = deepcopy(context)
        changed["entries"][0]["label"] = "Changed label"
        with self.assertRaises(ContractError):
            validate_context(changed)

    def test_wrong_keys_foreign_facts_and_forged_ids_fail(self) -> None:
        """Provider output can only rank supplied keys for that candidate's fact."""
        context = make_context(page(), as_of=TODAY)
        facts = [fact("mensa")]
        valid = propose(facts, context)
        for change in (lambda x: x[0].update(fact_key="another-card"),
                       lambda x: x[0].update(context_digest="0" * 64),
                       lambda x: x[0]["choices"][0].update(candidate_key=str(uuid4())),
                       lambda x: x[0]["choices"][0].update(term_id=str(uuid4())),
                       lambda x: x[0]["choices"][0].update(confidence=99)):
            bad = deepcopy(valid)
            change(bad)
            with self.assertRaises(ContractError):
                validate_matches(bad, facts, context)

    def test_duplicate_context_keys_targets_and_choices_fail(self) -> None:
        """A repeated candidate cannot acquire extra rank or stand for two identities."""
        context = make_context(page(), as_of=TODAY)
        for member in ("candidate_key", "target"):
            changed = deepcopy(context)
            changed["entries"][1][member] = changed["entries"][0][member]
            changed["digest"] = context_digest(changed)
            with self.assertRaises(ContractError):
                validate_context(changed)
        matches = propose([fact("mensa")], context)
        matches[0]["choices"] *= 2
        with self.assertRaises(ContractError):
            validate_matches(matches, [fact("mensa")], context)

    def test_context_limit_is_one_hundred(self) -> None:
        """Catalog overflow fails before any provider dispatch."""
        with self.assertRaises(ContractError):
            make_context(page(tuple(f"Category {i}" for i in range(101))), as_of=TODAY)

    def test_organization_matching_is_local_and_never_infers_role(self) -> None:
        """A name can suggest an authorized draft; IA never receives that context."""
        source = {"context": {"organization_name": "Associazione Alfa", "catalog_digest": "local"}, "complete": True,
                  "entries": [{"label": "Associazione Alfa", "published": False,
                               "target": {"kind": "organization", "organization_id": str(uuid4()),
                                          "expected_work": str(uuid4()), "expected_public": None}}]}
        context = make_context(source, as_of=TODAY)
        facts = [{**fact("Associazione Alfa"), "kind": "organization_name"}]
        output = resolve_matches(propose(facts, context), facts, context)
        self.assertEqual(output[0]["state"], "proposed")
        self.assertNotIn("role", output[0]["candidates"][0])
        with self.assertRaises(ContractError):
            validate_context(context, provider=True)

    def test_single_extraction_exchange_can_also_propose_categories(self) -> None:
        """Eligible caller-supplied context adds suggestions in the same one exchange."""
        req = request("Sportello. Categoria: mensa.")
        req.update(schema_version=2, field_dictionary_version=VERSION_V2, requested_output_shape=OUTPUT_SHAPE_V2,
                   catalog_context=make_context(page(), as_of=TODAY))
        card = candidate(req, "Sportello")
        card["source_facts"] = [fact("mensa")]
        card["evidence"].append(citation(req, "/source_facts/0/source_value", "mensa"))
        card["matches"] = propose(card["source_facts"], req["catalog_context"])
        output = result(req, [card])
        output["schema_version"] = 2
        adapter = FakeAdapter(output)
        actual = interpret(req, adapter)
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(actual["state"], "complete")
        self.assertEqual(actual["candidates"][0]["matches"], card["matches"])
        self.assertNotIn("classifications", actual["candidates"][0]["service"])

    def test_invalid_context_dispatches_zero_requests(self) -> None:
        """No invented axis or unpublished context can leak through request validation."""
        req = request("Sportello")
        req.update(schema_version=2, field_dictionary_version=VERSION_V2, requested_output_shape=OUTPUT_SHAPE_V2,
                   catalog_context=make_context(page(), as_of=TODAY))
        req["catalog_context"]["entries"][0]["published"] = False
        req["catalog_context"]["digest"] = context_digest(req["catalog_context"])
        adapter = FakeAdapter(None)
        with self.assertRaises(ContractError):
            interpret(req, adapter)
        self.assertEqual(adapter.calls, [])

    def test_invalid_provider_match_returns_incomplete_without_retry(self) -> None:
        """Unknown supplied keys fail semantic validation while usage stays external."""
        req = request("Sportello. mensa")
        req.update(schema_version=2, field_dictionary_version=VERSION_V2, requested_output_shape=OUTPUT_SHAPE_V2,
                   catalog_context=make_context(page(), as_of=TODAY))
        card = candidate(req, "Sportello")
        card["source_facts"] = [fact("mensa")]
        card["evidence"].append(citation(req, "/source_facts/0/source_value", "mensa"))
        card["matches"] = propose(card["source_facts"], req["catalog_context"])
        card["matches"][0]["choices"][0]["candidate_key"] = "invented"
        output = result(req, [card])
        output["schema_version"] = 2
        adapter = FakeAdapter(output)
        actual = interpret(req, adapter)
        self.assertEqual(actual["state"], "incomplete")
        self.assertEqual(actual["candidates"], [])
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.response["usage"]["input_tokens"], 50)

    def test_v1_rejects_catalog_context_before_dispatch(self) -> None:
        """The original protocol cannot silently acquire a different result shape."""
        req = request("Sportello")
        req["catalog_context"] = make_context(page(), as_of=TODAY)
        adapter = FakeAdapter(None)
        with self.assertRaises(ContractError):
            interpret(req, adapter)
        self.assertEqual(adapter.calls, [])

    def test_digest_matches_the_native_database_golden_vector(self) -> None:
        """Sorted compact UTF8 JSON hashes identically in Python and PostgreSQL."""
        self.assertEqual(context_digest({'z': [True, None, 'Caffè'], 'a': 1}),
                         '9544cd924c9e1b36939b292dd3b977c282ae62a13d85e5f1d37d6429847fdae2')
