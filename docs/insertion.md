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

## Literal facts v2 — EGI-115 / package0.3.1

Version1 remains the explicit default for existing callers. To request v2 use all
three matching values: schema_version2, field_dictionary_version
`egi-preparation-fields/2`, requested_output_shape `interpretation.result.v2`.
Mixed or unsupported versions fail before calling the adapter. A v2 result must
also declare version2; incomplete/refused/uncertain/error results retain the requested
version instead of silently falling back to v1.

The service/location aggregate vocabulary is unchanged. Each v2 candidate requires
`source_facts`, possibly empty. Each entry has exactly fact_key (nonempty local
string, at most100 characters), subject (service/location), kind
(organization_name/category_label) and source_value (nonblank literal source spelling,
at most50,000 code points). At most1,000 facts per candidate; keys are unique within
the candidate and scoped by candidate_key. Shared organization claims in different
services remain distinct per-candidate facts. The app/database later allocate stable
private UUIDs and initialize their editable values; model keys are not canonical IDs.

Every literal fact needs evidence at its exact `/source_facts/<index>/source_value`
leaf. Existing input hash, Unicode offsets, redaction and exact quote checks apply;
source_value must occur in every cited quotation even if an association is marked
interpreted. Evidence cannot target fact_key, kind or subject. v2 evidence IDs are
unique across candidates, so another candidate's evidence identity cannot be reused.
The same actual public passage may support two claims with independent bindings.

Do not infer an organization merely from an ambiguous desk name, or replace a source
category label by a synthesized EGI class. Multiple explicit organizations/categories
remain distinguishable. No fact_id, organization_id, term_id, role, edited value or
selected resolution is permitted in the extraction fact object. Actual catalog
matching follows EGI-118; editorial creation/confirmation are outside this module.
`dictionary(VERSION_V2)` adds independent source_fact/source_fact_choices descriptions
for the app-owned Structured Outputs schema; its transport consumer is EGI-116.

The validator checks structure, provenance, literal support and candidate bindings;
it does not prove the model chose the right organization/service association from
natural language. Human-annotated shared/ambiguous-service cases and real-provider
quality evaluation remain EGI-112/113, with their existing gates and thresholds.

All44 stdlib tests pass (the original34 plus10 v2 fixture journeys). No real model
request, repair call, source acquisition, benchmark score or paid usage occurred.
The source-only wheel was built twice using the command above, with identical SHA256:

`egi_reviewer-0.3.1-py3-none-any.whl`
`18b83ded49a89e916cda8ebafd1be80cf88cb642aa2e57011fa961d3e84dfdd2`.

It is retained under the workspace `.local/artifacts/community/`. EGI-116 must pin
and verify this artifact before enabling the v2 worker path; existing v1 app runs
remain on their current compatible dependency until that consumer ticket.

The0.3.1 patch also rejects nonempty canonical organization/classification components
in v2 extraction (including role-only organization objects without IDs). This keeps
roles out of provider authority while retaining the existing v1 contract. The new
regression failed on0.3.0 and passes on0.3.1. The earlier0.3.0 wheel remains retained
unchanged; consumers must use the0.3.1 hash above.
