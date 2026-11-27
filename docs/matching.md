# Context-bound catalog matching

Reviewer0.4.0 adds the EGI-118 matching seam, retaining v1 and context-free v2
interpretation contracts. It owns no catalog authority, transport, database, source
eligibility, budget, canonical writer or confirmation operation.

`matching.make_context(page, as_of=date)` freezes an authorized EGI-117 catalog
page (or an explicitly aggregated sequence of pages) into a closed context v1.
The caller supplies truthful complete/continuation state and actual references.
There are at most100 entries, each with a local candidate_key, retained label,
typed target, published/active state, effective dates and broader IDs. Category
scope requires territory_id and axis_id. Both adoption endpoints are checked.
Organization scope is empty and local name matching can include authorized drafts.
Inactive, future/expired, cross-axis and malformed contexts fail rather than being
silently repaired. This structural check cannot prove DB existence or access;
the owning database revalidates actual references, heads and current adoption.

Digest is SHA256 of UTF8, ensure_ascii=False, sorted JSON keys and compact separators,
excluding digest itself. It binds labels, identities/heads, territory/axis, dates,
coverage and the recorded as_of date. It is an identity token, not an authorization
signature. It must be part of immutable job configuration/cache identity whenever
a provider consumes this context. A later current-date/head/adoption check remains
necessary at confirmation and acceptance.

`propose(local_source_facts, context)` runs without IA. Comparison case-folds,
removes diacritics and collapses punctuation/whitespace; literal facts and labels
are copied, never replaced. Category heuristics order exact normalized labels,
shared words, then close lexical spelling. Organizations use exact normalized
names only; this still proves neither identity nor role. Ordinal reasons are
normalized_label/shared_words/similar_label; internal lexical scores never become
confidence percentages. Synonyms with no lexical overlap require human choice or
optional IA suggestions. No-match explicitly has empty choices, scoped to the
supplied bounded catalog. Coverage remains visible in context.complete.

`validate_matches` checks each local fact_key, digest and ordered choices containing
only supplied candidate_key/reason pairs. Unknown keys, canonical IDs, role/selection,
duplicate choices, foreign facts and mixed fact kinds fail. Category proposals apply
to service facts; source labels about locations remain unresolved literals.
`resolve_matches` maps checked keys to `{fact_key,state,context,candidates}` with
actual target/rank/reason. It never returns a selected or confirmed association.
The owning app maps local keys to its stable fact IDs and DB-revalidated payload.

An extract_text v2 request may additionally supply catalog_context. Only published
adopted category contexts are provider eligible; organization/draft contexts are
rejected before dispatch. Each returned candidate then requires matches, including
an empty array when nothing matches. These suggestions share the existing single
adapter exchange and retain exact source-fact quote validation. V1 rejects the
extra context; context-free v2 keeps its original closed shape. Invalid matching
results become safe incomplete diagnostics; transport usage still belongs to the
caller and no repair/second request is made. All existing source eligibility and
protected-contact redaction obligations stay with the app.

The owning worker must freeze context in its job/configuration, include its digest
in cache identity, supply the conditional structured-output schema and persist only
validated proposals. This package alone does not authorize or perform a paid call.
Tests exercise deterministic and injected-response behavior, not real-model quality.
