# Workbench protocol — CW1

`review.workbench` owns the closed `workbench.request.v1` and
`workbench.result.v1` profiles for `classify_cards` and `group_labels`. CSV mapping
is reserved for CW2. Existing text extraction and triage protocols are unchanged.
The database owns eligibility, grants, current versions, original source binding,
canonical IDs and persistence. The library validates frozen source-bound packets,
produces one task prompt/schema, and makes at most one injected Adapter exchange.

Public functions are `validate_request(request)`, `validate_result(result, request)`,
`interpret(request, adapter)`, `instructions(request)`, `output_schema(request)`,
`input_bound(request)`, `request_digest(request)` and `scope_key(shared_context)`.
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
