# Reusable text interpretation — egi-reviewer 0.2.0

`review.insertion.interpret(request, adapter)` is the Community text proposal
entrypoint. It is independent of deterministic triage, importer normalization,
HTTP, database/session access, jobs, billing and publication. It invokes at most
one injected adapter. There is no repair, continuation, URL fetch or tool runner.

The caller supplies an authorized eligible decoded view, not arbitrary original
private material. The SQL provider checks source attestation, permissions and
redacts protected/private contacts before this module sees a request. This module
verifies the retained offset/redaction map and every returned quotation. It does
not decide that a source is public or admitted.

## Request and output

Request version 1 has exactly:

- `schema_version: 1`, `task: "extract_text"`, `input_id` (UUID), `input_hash` (the
  lowercase original-byte SHA-256), `config_version`;
- `text`: at most 50,000 Unicode code points, with a leading original BOM already
  excluded from the view; CRLF and combining/emoji characters remain unchanged;
- `source_metadata`: known non-confidential name/publisher/source_kind/homepage/
  license/attribution strings or nulls, already filtered by the caller;
- `locator_map: {kind: "identity_with_redactions", redactions: [{start,end}]}`;
  every redacted interval is blanked with exactly the same number of spaces;
- `field_dictionary_version: "egi-preparation-fields/1"`, nonempty
  `language_version` and `taxonomy_version`,
  `requested_output_shape: "interpretation.result.v1"`.

The request contains no credentials, account/session identity, private notes or
unrelated input rows. `map_csv` is deliberately unavailable until the batch milestone.
`validate_request` raises a safe `ContractError` before invoking the adapter.

The result has exactly `schema_version`, `input_id`, `input_hash`, `config_version`,
`state` (complete/incomplete/refused), `candidates`, `mapping` (null for text) and
`diagnostics`. Each candidate has `candidate_key`, `service`, `location`, `evidence`
and `diagnostics`. Keys identify candidates locally, never canonical services.
The SQL provider mints actual opaque candidate IDs after validation/persistence.

`insertion_fields.dictionary()` exposes the frozen B3.1 service/location/component
vocabulary. Bodies may be incomplete, but unknown keys, wrong types/domains,
provider-owned component/canonical references, inferred public-contact permission,
invalid coordinate/time ranges and incompatible location schedule scopes fail.
No field is defaulted to in-person delivery, a physical location, known hours or
closed unmentioned days. A closed day requires specifically scoped evidence;
this structural check is not a substitute for human semantic evaluation.

Evidence has the approved locator shape: UUID id/input_id, input_hash, field path,
stated/interpreted classification, exact span/quote and optional note. Manual/cell
locators are not provider text evidence. Spans are start-inclusive/end-exclusive
Unicode code points, not UTF-8 bytes or collapsed whitespace. They cannot intersect
redactions, reference another input/hash, point to an absent value or invent quotes.
A stated literal must occur in its quote; a transformed value is labelled interpreted.
Essential names, contacts, addresses, coordinates and times need scoped passages.
This verifies provenance and literal support, not the truth of every interpretation.

`INSTRUCTIONS` is a fixed adapter instruction, never assembled from source text.
The app transport must keep source data separate from instructions and expose no
provider tools. Unknown/malformed tool-call properties are rejected as output.

## Adapter and cost ownership

The injected callable receives an independent request and returns exactly:
`{outcome,provider_request_id,structured_output,usage,error_code}`. Outcomes are
completed/refused/incomplete/uncertain/known_failure; IDs/errors may be null;
structured output is an object or null. Known usage has nonnegative input/output
counts, optional cached-input/reasoning counts bounded by their parent totals.
Error codes are catalogued classes, never raw HTTP exceptions or response bodies.

The **app-owned adapter instance retains its response and usage**. The interpreter
returns only the semantic result, as specified; invalid quotes or incomplete output
must not erase usage needed for settlement. Caller/adapter tests must check this
boundary. The module never declares a failed request unbilled and never retries it.
An unexpected adapter exception becomes an incomplete/provider_uncertain diagnostic
without reflecting the exception message. Process interrupts remain interrupts.

Malformed/refused/incomplete outputs cannot be treated as a successful complete
selection. Original material remains in the preparation for manual editing or an
explicit new request. Diagnostics use catalogued codes and known field paths;
no fabricated confidence score or raw provider error is returned.

## Verification and artifact

On 2026-11-26, 34 stdlib unittest tests passed: the existing 17 deterministic triage
checks and 17 interpretation tests. Fixtures exercise multiple services, remote/
physical separation, unknown/overnight hours, Unicode/BOM/CRLF, redactions, invented
quotes/identities, source-instruction isolation, malformed/refused/incomplete
responses, no automatic repairs and preserved adapter usage. Tests use controlled
responses; no actual model, quality threshold, paid usage or latency is claimed.

Build with the existing selected backend `setuptools==75.1.0`, no runtime dependencies:

```sh
SOURCE_DATE_EPOCH=315532800 .venv/bin/python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir WHEEL_DIRECTORY .
```

The 1980 ZIP epoch makes the source-only wheel reproducible. Candidate artifact:
`egi_reviewer-0.2.0-py3-none-any.whl`, SHA-256
`bbbf8cc126c5fb07fa38a3beabd93cadefa7034949bdd2146173a7e8aaac7d72`.
The workspace retains it under `.local/artifacts/community/`; the app must pin this
version/hash, not import a mutable neighboring checkout. It was installed into the
isolated Reviewer environment and imported with Python `-I` from outside the source
tree; installed CLI help also worked. Final combined review and human corpus/model/
provider acceptance remain pending. General Reviewer comparison EGI-61 is unchanged.
