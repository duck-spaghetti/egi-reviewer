# Workbench protocol — CW1

`review.workbench` owns the closed `workbench.request.v1` and
`workbench.result.v1` profiles for `classify_cards` and `group_labels`. CSV mapping
is reserved for CW2. Existing text extraction and triage protocols are unchanged.
The database owns eligibility, grants, current versions, original source binding,
canonical IDs and persistence. The library validates frozen source-bound packets,
produces one task prompt/schema, and makes at most one injected Adapter exchange.

Public functions are `validate_request(request)`, `validate_result(result, request)`,
`interpret(request, adapter)`, `instructions(request)`, `output_schema(request)`,
`input_bound(request)`, `request_digest(request)`, `scope_key(shared_context)` and
`normalize_label(value)`.
Returned objects are independent copies. The caller retains Adapter usage even if
semantic validation fails. No database, credential, importer or transport dependency.

## Closed indexed data

`data` contains exactly `records,units,bases,supports,labels,seed_groups,prior_proposals`.

- Record: `{record_key,source_key,item_version}`.
- Coverage unit: `{unit_key,record_key,basis_keys,member_keys}`. Classification uses
  an owned record and required bases; comparison uses null record and label members.
- Basis: `{basis_key,record_key,kind,value,support_keys}`; kind is
  `category_label`, `description` or `source_context`. Metadata remains contextual
  evidence; the runtime provider does not create independent metadata-only bases.
- Support: `{support_key,record_key,input_key,field_path,text,start,end,quote,origin}`;
  origin is `source` or `source_metadata`. Text is an owned decoded field view.
  Quote equals `text[start:end]` using Unicode code points, without normalization.
  The database checks the original public input, protection and field ownership.
- Contextual label: `{unit_key,label,variants,context_key,occurrences,count}`;
  occurrence is `{record_key,basis_key,support_keys}`. Count includes unsampled
  occurrences; samples never imply occurrence completeness.
  Literal occurrences bind `category_label` bases. Materialized interpretations
  bind original `description` bases, retain that original text as label, and use
  `interpretation:<UUID>` unit keys; they never become literal source facts.
- Seed: `{group_key,unit_keys,relation}`.
- Prior proposal: the closed classification proposal shape, with original supports
  and only currently supplied catalog alternatives. Missing alternatives require
  `incomplete_catalog`; AI summaries cannot replace original evidence.

The outer request/result, coverage, unit-result, hypothesis and proposal shapes are
the approved r0.2 contracts §6.2. `review.workbench_profile` is the executable shared
source for their field sets, safe codes, version constants and generated output
schema. Reasons and hypothesis statements are bounded to300 characters; choices
to5. Hypotheses are optional `abbreviation_expansion`, always `unverified`, with
`verification_needed:true`. Their trigger is not proof: a category choice needs
support beyond the union of its unit's hypothesis triggers. Full-field triggers
can therefore cause a conservative abstention.

## Frozen context and coverage

Shared context contains exactly `context_id,version,digest,scope,prompt_version,
schema_profile_version,field_dictionary_version,source_semantics,source_metadata,
catalog_snapshot,label_inventory,inventory_coverage,limitations`. Scope contains
`preparation_snapshot_key,territory_id,axis_id`. Source semantics entries contain
`source_key,rules`; metadata entries contain `source_key` and only available
`name,publisher,source_kind,homepage,license,attribution`. Catalog snapshot contains
`digest`; inventory entries contain `label,context_key,count`; inventory coverage
contains `complete,total_labels,supplied_labels,omitted_labels`.

Canonical digests use sorted compact UTF-8 JSON without ASCII escaping. Context
digests exclude only their own top-level digest. `scope_key` hashes
`{scope,catalog_snapshot}`; it survives packet catalog slicing within the same
frozen snapshot. Actual candidate choices must still exist in the supplied slice.
Catalog entries add explicit `definition` and `aliases` to the existing adopted
classification context; absent enrichment remains null/empty, never invented.

Every processed classification basis needs one explicit proposal outcome, including
no-match/abstention. Missing outcomes become unprocessed bases, preserving valid
independent outcomes. Duplicate/foreign identities never earn coverage. A malformed
outer envelope/task/digest is fatal; correctly bound parseable results can retain
independently valid units. Unreadable output has no repair or salvage. Complete
means supplied required work only; reference records, omitted inventory and sampled
occurrences remain separate. Unknown/mixed/incompletely sampled group members need
explicit membership issues, no equivalent relation and no common mapping.

## Input bounds

The fixed profile caps instructions plus generated schema at32768 UTF-8 bytes.
`input_bound` counts JSON-string-escaped request/instructions, schema bytes and1024
explicit framing tokens; bytes
are a conservative token ceiling without a tokenizer dependency. SQL preview
reserves33792 for this profile overhead plus twice raw canonical request bytes to
cover transport escaping. The transport must additionally bound its
actual complete serialized provider payload. No retry or additional repair call.

## Verification status

Implementation follows the verified031/032 provider seam. B03 full-ticket acceptance,
final Community gold/live acceptance (EGI-112/113), and whole-set review remain
separate. Controlled fixtures establish protocol mechanics, never model quality.

B05 candidate0.5.0b1:77 source and77 isolated installed-wheel tests passed
(Python3.13.4, stdlib unittest); the existing60 tests remain unchanged. Two fixed-
epoch builds produced SHA256
`bf72fcb24eae34d179030b395b588a5f023958daac359d27e6f500e5854b77c6`.
The actual synthetic SQL031 claim validated with the same canonical request digest.
New50-record/100-basis validation measured1.684ms per call (best of3 batches of100);
there is no baseline workbench API for comparison. The unchanged legacy suite was
previously60 tests in0.013s; full candidate suite77 tests in0.027s, not a product
latency benchmark. No shared environment was modified, no live model was called.
The sibling development-checks tooling is not integrated in this branch; these are
source, artifact and contract checks rather than a claimed Complete check profile.

## Contextual classification — B06

`review.classification.propose(request)` produces the same closed result profile
without IA. Whole source labels or descriptions must match a supplied candidate's
label or actual alias using NFC, casefold and whitespace only. Punctuation, accents
and word order are retained; lexical scores never establish a match. Descriptions
without an exact match abstain. More than5 equal alternatives abstain rather than
silently dropping candidates. Missing source labels never become invented facts.
The caller may instead use one `workbench.interpret` exchange for semantic proposals.

The classification prompt permits description/network-context interpretations with
original support and explicit human confirmation. It distinguishes activity/audience,
false/default flags, proper names, appointment vs unknown cost, one service with
level/time blocks, source-specific temporal claims, facility category vs unstated
clinical services, and optional unverified sigla expansions. Prompt rules constrain
the model; a structural validator cannot prove a free-text semantic explanation.
Human review and separately approved gold/live evaluation remain necessary.

The10 classification tests use synthetic equivalents of the explored H02/H09,
S05/S09 and C06/C04 policies. They are newly authored fixtures, not records from the
60-record holdout or approved annotations. Controlled Adapter results exercise
allowed/rejected shapes and provenance; assertions about prompt instructions do not
prove that a real model follows them. Baseline abstention is deliberate, with no
semantic recall threshold or model-quality claim.

B06 candidate0.5.0b2:87 source and87 isolated installed-wheel tests passed; two
fixed-epoch builds match SHA256
`3a2cea7859db552c11aa8b22a99de56b377bb30307fdd6b55a684daa03ed509e`.
The50-record/100-basis deterministic path measured7.539ms per call (best of3×100),
including request validation and result reconciliation. No predecessor classification
API exists for a comparable baseline; B05 request validation alone measured1.684ms.

## Contextual grouping — B07

`review.grouping.propose(request)` normalizes literal labels with NFC, casefold and
whitespace only. It preserves accents, punctuation and word order. Stable local
proposal keys bind comparison scope and members; all original variants, counts,
version-bound occurrences and support remain in the immutable request. One label
unit with multiple complete occurrences is a valid group, including a singleton
`unit_keys` array; distinct label-unit count never substitutes occurrence count.

Deterministic `equivalent` means literal spelling variants in the frozen scope,
always with empty category choices. It cannot discover same-scope homonyms from
spelling alone. Original descriptions/context and prior alternatives let optional
semantic comparison downgrade to `related`/`ambiguous`; human review is still needed.
Description-origin interpreted units never become deterministic literal equivalence.
Unknown/mixed contexts and unsampled occurrences produce ambiguous proposals with
membership issues and no mapping. A valid insufficient-context abstention analyzes
only its supplied comparison; omitted inventory/occurrences stay incomplete.

The group prompt distinguishes related offers from synonyms, original quotations
from prior AI summaries, literal labels from materialized description interpretations,
and required comparison scopes from reference-only records. Cross-source comparison
retains original source/version/territory/axis binding. A prior alternative absent
from this catalog slice must be omitted with `incomplete_catalog`, never resolved to
an invented or unavailable target. No taxonomy reorganization, term/entity/service
merge, canonical write, or automatic group mapping is part of this library.
Group reasons/choices may cite any exact supplied source/metadata support belonging
to records of proposed member occurrences, including their contextual descriptions;
unrelated packet records remain forbidden and metadata provenance stays explicit.

The12 grouping tests cover normalized variants, accents/punctuation, coalesced
singletons, homonym scopes, incomplete occurrences, interpreted originals, related
education, cross-source original evidence/prior alternatives, long-tail inventory,
reference-only coverage and closed output authority. Fixtures are synthetic;
controlled semantic outputs do not establish real-model precision or recall.

B07 candidate0.5.0:99 source and99 isolated installed-wheel tests passed, including
the unchanged60 legacy cases. Two fixed-epoch builds match SHA256
`4c8d035e129790971cba6c5db610597f0ad748f19762a2bb3abf14eed467138a`.
The frozen SQL031/032 synthetic request digest
`b0c761337c08c09745588926af210478ae270dce93221ab3ac4445a76ba49bd0`
also validates unchanged. Group instructions/schema occupy7257 JSON-framed bytes,
below the32768 cap. The50-label/100-basis deterministic comparison measured5.780ms
per call (best of3×100), including request validation and result reconciliation;
no predecessor grouping API exists for direct comparison. Source suite99 cases
took0.072s; installed suite0.073s. No live IA/provider credential or shared venv.
Artifacts live in the owned ignored `.local/artifacts/community-cw1/` directory.
The input-only historical `blocked_records` limitation is accepted in frozen
provider requests; output diagnostics remain the closed19-code profile.

## Classification coverage correction —0.5.1

The final Spec review found that a model could return explicit basis abstentions
while labeling the owning unit `analyzed`, causing the database to count validated
work instead of its insufficient-context subset. Classification unit state is now
derived from retained attributable proposal outcomes, independently of that supplied
label: no processed outcome means `not_analyzed`; any explicit
`insufficient_context` proposal means `insufficient_context`; otherwise the unit is
`analyzed`. An insufficient-context diagnostic accompanies a derived abstention.
Proposed/no-supplied-match outcomes remain inspected work; a proposed choice with an
incomplete supplied catalog is not itself an abstention. Group scope state remains
separate. Valid choices, independent sibling units and processed/unprocessed basis
sets survive normalization; unresolved bases still force an incomplete result.

Four new regression tests failed against0.5.0 before the correction and passed
afterward. They cover all/mixed abstentions with inconsistent supplied states,
partial basis success with an independent no-match sibling, absent outcomes, and
useful partial-catalog choices. All103 source and103 isolated installed-wheel tests
passed (the original99 remain unchanged), with no provider exchange or new dependency.
Two fixed-epoch0.5.1 builds match SHA256
`252e39b1ea10e0a3bf7f129833f462e9c42969cdc899f996e14778038d072b8c`;
the0.5.0 artifact is retained unchanged. Source tests took0.056s and installed tests
0.052s. The same50-record/100-basis validation measured4.346ms before and4.349ms after
(best of3 batches of100 calls using isolated installed artifacts); these are local
mechanical timings, not model latency or a quality measurement.
