"""Exercise the triage: signals in Italian text, coverage by structured fields and the command.

Packages are invented and minimal: only the members the triage reads.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from review import cli
from review.triage import phone_digits, signals, triage, web_host


def values(text: str, field: str) -> list:
    """Return the values the triage finds for one field in one string."""
    return [item["value"] for item in signals(text, "it")[field]]


def package(raw: dict, fields: dict | None = None, assertions: list | None = None) -> dict:
    """Build a package with one service record and candidate."""
    base = {"name": {"value": "Scuola"}, "original_language": "it", "contacts": [], "cost_state": "unknown",
            "cost_note": {"value": None}, "schedule_assertion_keys": [], "access_assertion_keys": []}
    base.update(fields or {})
    return {
        "package_digest": "digest",
        "records": [{"key": "record:1", "external_key": "site:1", "raw_payload": raw}],
        "subjects": [{"key": "subject:1", "record_key": "record:1", "kind": "service"}],
        "assertions": assertions or [],
        "candidates": [{"key": "candidate:1", "kind": "service", "subject_keys": ["subject:1"], "fields": base},
                       {"key": "candidate:2", "kind": "location", "subject_keys": ["subject:1"], "fields": {}}],
    }


class SignalTest(unittest.TestCase):
    """What one string says, in Italian."""

    def test_whole_hour_ranges_keep_day_context_and_scope(self) -> None:
        """Whole-hour intervals require day context and retain the nearest scope."""
        for text, scope in [('dal lunedì al venerdì 9-13', 'service'),
                            ('Corsi lunedì 9–13', 'service'),
                            ('Segreteria lunedì 9 - 13', 'intake'),
                            ('Telefonare lunedì 9—13', 'contact')]:
            with self.subTest(text=text):
                self.assertEqual(values(text, 'hours'), [scope])
        for text in ['9-13', 'lunedì 03-12-2025', 'lunedì 03/12/2025',
                     'lunedì Tel. 06 8621-2391', 'lunedì telefono 333-123-4567']:
            with self.subTest(text=text):
                self.assertEqual(values(text, 'hours'), [])

    def test_hours_need_a_day_or_hours_word_near_a_time(self) -> None:
        """Require day context when recognizing printed clock times."""
        self.assertTrue(values("dal lunedi al venerdi ore 9.30 – 12.30", "hours"))
        self.assertTrue(values("LUN - GIO 10:00 - 12:00", "hours"))
        self.assertFalse(values("08:00", "hours"))
        self.assertFalse(values("Tel. 06 86212391 (ore pasti)", "hours"))

    def test_hours_scope_is_the_nearest_word_before(self) -> None:
        """Assign each hours signal to its nearest printed scope on the same line."""
        self.assertEqual(values("Segreteria: giovedì 15.30-19.30", "hours"), ["intake"])
        self.assertEqual(values("Corsi A1: Lun-Mer 16.30-18.00. Segreteria: martedì ore 10 – 13", "hours"),
                         ["service", "intake"])
        self.assertEqual(values("Telefonare lunedì dalle 9 alle 12", "hours"), ["contact"])
        long_line = "Segreteria ( sede centrale Rieti ): dal lunedi al venerdi ore 9.30 – 12.30; martedi e giovedi anche ore 15.30 – 16.30."
        self.assertEqual(values(long_line, "hours"), ["intake"])
        self.assertEqual(values("Segreteria: lunedì 9:00-12:00\nCorsi A1: martedì 10:00-12:00", "hours"), ["intake", "service"])
        self.assertEqual(values("LUN - GIO 10:00 - 12:00", "hours"), ["service"])
        street = "rivolgersi alla segreteria didattica in Corso Vittorio Emanuele II, 217: martedì ore 10 – 13"
        self.assertEqual(values(street, "hours"), ["intake"])

    def test_phones_ignore_prefix_dates_and_times(self) -> None:
        """Normalize Italian phone prefixes without treating dates or times as phones."""
        self.assertEqual(values("Tel. +39 06 8621 2391", "phone"), ["0686212391"])
        self.assertEqual(values("cell. 380 219 0044", "phone"), ["3802190044"])
        self.assertEqual(values("dal 03/12/2025 al 10.06.2026", "phone"), [])
        self.assertEqual(values("Mer-Ven. 17.00-18.30", "phone"), [])

    def test_abbreviated_second_number_is_kept_as_printed(self) -> None:
        """Retain a terminal phone suffix as evidence without interpreting alternatives."""
        self.assertEqual(values("Tel. 06 45460313/4 Mail", "phone"), ["0645460313/4"])
        self.assertEqual(values("0667105197/98", "phone"), ["0667105197/98"])

    def test_email_and_web_are_normalized(self) -> None:
        """Compare case-normalized emails and website hosts."""
        self.assertEqual(values("Mail: Scuola@SantEgidio.org", "email"), ["scuola@santegidio.org"])
        self.assertEqual(values("Iscrizioni: www.gentidipace.it/form.", "web"), ["gentidipace.it"])
        self.assertEqual(web_host("https://www.example.org/a/b"), "example.org")

    def test_requirements_and_offers(self) -> None:
        """Distinguish printed conditions from offered assistance and category codes."""
        self.assertEqual(values("Accesso con permesso di soggiorno e codice fiscale", "access"),
                         ["residence_permit", "tax_code"])
        self.assertEqual(values("Supporto richiesta documenti", "access"), [])
        self.assertEqual(values("Si accede su appuntamento", "access"), [])
        self.assertEqual(values("Si accede su appuntamento", "intake"), ["appointment"])
        self.assertEqual(values("Prenotazione iscrizione: www.gentidipace.it", "intake"), ["appointment", "registration"])
        self.assertEqual(values("documenti", "access"), [])  # a category code, not a condition
        self.assertEqual(values("gratuito", "cost"), [])

    def test_cost(self) -> None:
        """Recognize stated costs while excluding free legal-aid terminology."""
        self.assertEqual(values("Corsi gratuiti", "cost"), ["gratuiti"])
        self.assertEqual(values("Con contributo", "cost"), ["contributo"])
        self.assertEqual(values("Gratuito patrocinio", "cost"), [])

    def test_italian_prefix(self) -> None:
        """Remove explicit international prefixes without shortening Italian mobiles."""
        self.assertEqual(phone_digits("0039 06 1234567"), "061234567")
        self.assertEqual(phone_digits("3912345678"), "3912345678")


class TriageTest(unittest.TestCase):
    """What the fields already say is not reported; what they miss is."""

    def test_whole_hour_range_with_missing_schedule_is_reported(self) -> None:
        """The triage reports a source whole-hour interval absent from the package."""
        document = triage(package({'description': 'dal lunedì al venerdì 9-13'}))
        self.assertEqual(document['flagged'], 1)
        self.assertEqual(document['gaps_by_field'], {'hours': 1})
        self.assertEqual(document['results'][0]['gaps'][0]['value'], 'service')

    def test_gaps_against_empty_fields(self) -> None:
        """Report missing structured facts from the original-language source text."""
        raw = {"description_html": "Corsi: Lun-Mer 16.30-18.00<br>Tel. 06 86212391<br>Mail: a@b.it<br>Su appuntamento",
               "translations": {"en": "Monday 10:00 phone 06 99999999"}}
        document = triage(package(raw))
        self.assertEqual(document["services"], 1)
        self.assertEqual(document["gaps_by_field"], {"email": 1, "hours": 1, "intake": 1, "phone": 1})
        self.assertNotIn("0699999999", [g["value"] for g in document["results"][0]["gaps"]])

    def test_signals_already_in_fields_are_not_reported(self) -> None:
        """Avoid repeating source facts already covered by structured fields."""
        raw = {"text": "Lun 9:00-12:00. Tel. +39 06 86212391, www.example.org, a@b.it, gratis, residenti"}
        fields = {"contacts": [{"channel": "phone", "value": "06 86212391"},
                               {"channel": "web", "value": "https://example.org/x"},
                               {"channel": "email", "value": "A@B.it"}],
                  "cost_state": "free", "schedule_assertion_keys": ["assertion:s"], "access_assertion_keys": ["assertion:a"]}
        assertions = [
            {"key": "assertion:s", "normalized_value": {"schedule": {"scope": "service", "days": [
                {"weekday": 1, "state": "intervals"}]}}},
            {"key": "assertion:a", "normalized_value": {"criteria": ["residenza"]}},
        ]
        document = triage(package(raw, fields, assertions))
        self.assertEqual((document["flagged"], document["gaps_by_field"]), (0, {}))

    def test_hours_of_another_scope_are_a_gap(self) -> None:
        """Report missing intake hours even when service hours are structured."""
        raw = {"page": "Corsi: lunedì 10:00-12:00. Segreteria: martedì ore 10 – 13."}
        fields = {"schedule_assertion_keys": ["assertion:s", "assertion:o"]}
        assertions = [
            {"key": "assertion:s", "normalized_value": {"schedule": {"scope": "service", "days": [
                {"weekday": 1, "state": "intervals"}]}}},
            {"key": "assertion:o", "normalized_value": {"scope": "office", "weekly": None, "office_text": "Segreteria"}},
        ]
        gaps = triage(package(raw, fields, assertions))["results"][0]["gaps"]
        self.assertEqual([(g["field"], g["value"]) for g in gaps], [("hours", "intake")])

    def test_importer_doubts_and_repeated_values(self) -> None:
        """Keep importer doubts and deduplicate repeated printed contacts."""
        raw = {"a": "Tel. 06 86212391", "b": "tel 06 86212391"}
        fields = {"schedule_assertion_keys": ["assertion:s"]}
        assertions = [{"key": "assertion:s", "normalized_value": {
            "schedule": None, "to_verify": [{"weekday": 2, "reason": "overlap"}]}}]
        result = triage(package(raw, fields, assertions))["results"][0]
        self.assertEqual(len(result["gaps"]), 1)
        self.assertEqual(result["doubts"][0]["value"], [{"weekday": 2, "reason": "overlap"}])


class CommandTest(unittest.TestCase):
    """The command writes beside the run and refuses a run it cannot place."""

    def test_writes_under_reviews(self) -> None:
        """Write machine and readable triage reports beside the runtime runs."""
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "runs" / "demo" / "RUN1"
            run.mkdir(parents=True)
            (run / "package.json").write_text(json.dumps(package({"t": "Tel. 06 86212391"})), encoding="utf-8")
            (run / "run.json").write_text(json.dumps({"source": "demo", "run_id": "RUN1"}), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(["triage", str(run)]), 0)
            written = Path(root) / "reviews" / "demo" / "RUN1" / "triage.json"
            self.assertEqual(json.loads(written.read_text(encoding="utf-8"))["gaps_by_field"], {"phone": 1})
            report = written.with_suffix(".md").read_text(encoding="utf-8")
            self.assertIn("## Scuola", report)
            self.assertIn("**telefono: 0686212391**", report)
            self.assertIn("1 of 1 services", out.getvalue())

    def test_unplaced_run_needs_out(self) -> None:
        """Require an explicit output for runs outside the runtime layout."""
        with tempfile.TemporaryDirectory() as root:
            run = Path(root) / "RUN1"
            run.mkdir()
            (run / "package.json").write_text(json.dumps(package({})), encoding="utf-8")
            (run / "run.json").write_text(json.dumps({"source": "demo", "run_id": "RUN1"}), encoding="utf-8")
            with redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cli.main(["triage", str(run)]), 2)
            self.assertIn("--out", err.getvalue())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["triage", str(run), "--out", str(Path(root) / "t.json")]), 0)

    def test_missing_run(self) -> None:
        """Return a readable command error when the input run cannot be read."""
        with redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["triage", "/nonexistent/run"]), 2)


if __name__ == "__main__":
    unittest.main()
