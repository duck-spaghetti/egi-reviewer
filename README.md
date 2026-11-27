# Development CI — EGI-139

See [owning CI verification](docs/development-ci.md) for the PR-to-dev workflow, required-check
identity, selected runtime and actual enforcement-evidence boundary.

# Current development checks — EGI-133

```sh
python3 scripts/check.py --profile quick --json
python3 scripts/check.py --profile complete --json
```

Activate the selected Python/build environment. This repository owns its checks;
shared reporting, commit-title policy and hook installer are consumed from one exact
app Git revision recorded in `.checks/tool-source.json`. Set EGI_DEVTOOLS_SOURCE to
that source checkout if its default sibling location is unavailable. All imported
shared files must match the pinned commit before they execute; missing/mismatched
source returns blocked (exit2). No new web runtime dependency is introduced.

Commit-msg/pre-push/CI use the same canonical validator through
`python3 scripts/commit_guard.py`. `python3 scripts/install_hooks.py` activates only
this assigned worktree's hooks and preserves unrelated hook paths. Ordinary titles
use EGI-positive-number: summary; merge/revert handling and exact legacy SHA exceptions
follow the shared policy. Local checkpoints may be incomplete; pre-push requires
clean matching source, passed Complete and applicable Integration. Required remote
CI enforcement remains session3 work, not evidence from hook configuration alone.

Quick runs source tests; Complete and Integration additionally build twice with the
selected setuptools75.1.0 backend, require byte-identical wheels, install offline
into an owned isolated target and run copied tests from an isolated cwd using that
installed package. Python -I and an import-path assertion exclude the source checkout.
Use the selected build environment including wheel; no network/provider request
is part of this command. Artifact identity is retained in `.local/wheel-last.json`
and `.local/artifacts/`; build/installed-test output is `.local/wheel-last.log`.

Exit0 means passed,1 failed and2 prerequisite-blocked. Common JSON schema1 reports
the selected profile, owning source commit, check status/reasons and timings.
Importer/sources and current product feature integration stay outside this scope.

## Earlier component setup and evidence

# EGI Reviewer

A second, independent reading of each service an importer delivered. It reads an importer
run (the canonical package written by `egi-importer`), finds what the source text says that
the structured fields do not, and later asks an agent to re-read the text with exact quotes.
It imports no importer code and never writes to the database: accepted findings return to
the importer as curation (EGI-62).

```text
review/
  profile.md   what a service is: fields, scopes, quoting rules, language notes
  triage.py    signals in the text (hours, phones, emails, websites, access, cost) vs fields
  cli.py       the egi-review command
tests/
```

Planned: `agent.py` and `compare.py` (EGI-61), decisions, curation and a periodic job
(EGI-62). Record: `project_egi/.scratch/review/plan.md`.

## Triage

Python 3.11+ and the standard library only.

```sh
python3 -m review.cli triage ~/egi-runtime/runs/scuolemigranti/RUN [--show 5]
```

It writes `<root>/reviews/<source>/<run>/triage.json` beside `<root>/runs/`, outside Git,
and `triage.md` next to it: counts, then one section per service with its link and what
is missing, each with the words that say it. A run elsewhere needs `--out FILE`.

| In the document | Meaning |
| --- | --- |
| `gaps` | The text has it, the field does not: a phone, email or host absent from the contacts; hours of a scope with no stated day; requirements, intake or cost with no value at all |
| `doubts` | Days the importer itself left to verify |
| `value` `snippet` `path` | What was found, the words around it, where in the record |

Whole-hour ranges such as `lunedì 9-13` require the same day context as clock times.
Hours carry a scope, named by the nearest word before the time on the same line:
`intake` (segreteria, accoglienza, ricevimento, sportello, iscrizioni), `contact`
(telefonare, tel), otherwise `service` (opening or courses; the importers' `lessons` count
as `service`). Requirements (`access`: documents, permits, residence, age…) are kept apart
from `intake`, how to get in (appointment, booking, registration, referral).

A phone printed as `06 45460313/4` is kept as `0645460313/4`: it may be two numbers, and
the triage never joins or splits it. Requirement words after "supporto", "rilascio",
"richiesta" and similar name something the service offers, not a condition.

Limits: requirements, intake and cost count as covered when any value is stated; a
dedicated follow-up (EGI-63) will clarify access-condition coverage before changing
that behavior. This correction does not change those coverage rules. A
scope word further than 200 characters back, or on another line, is not seen. Signals exist for Italian only. Sources still in the importer's `legacy/` have no
package and are not covered.

## Test

```sh
python3 -m unittest discover -s tests -t . -v
```

## Community text interpretation

`egi-reviewer 0.2.0` adds `review.insertion.interpret(request, adapter)` for exact-
quoted source proposals. The app owns provider transport, private preparation access,
job accounting and canonical acceptance. The library makes at most one injected
exchange, exposes no tools and never writes to a database. See
[the versioned API and artifact](docs/insertion.md) for shapes, evidence rules,
verification and the wheel hash. Deterministic `egi-review triage` remains unchanged.

The reusable modules are `insertion.py` (orchestration/result validation),
`insertion_fields.py` (frozen preparation vocabulary) and `insertion_evidence.py`
(exact locators/redactions). CSV mapping follows in the separately approved batch set.

Package0.3.1 adds explicit v2 literal organization/category proposals alongside v1,
with exact evidence and no canonical identity/write authority. See
[the v2 contract and artifact](docs/insertion.md#literal-facts-v2--egi-115--package031).
The app consumes the versioned field dictionary and owns transport/schema generation;
real-provider quality acceptance remains separately gated.

Package0.5.0b1 adds the independent CW1 workbench request/result validators,
shared task schema/instructions, explicit partial coverage and one-exchange Adapter
entrypoint. See [workbench protocol](docs/workbench.md). This controlled candidate
does not claim Community gold/live acceptance; CSV mapping remains CW2.

Package0.5.0b2 adds `review.classification.propose(request)` as a conservative
exact-label/actual-alias baseline and contextual classification prompt policies.
Optional semantic analysis still uses `review.workbench.interpret` with one injected
exchange; no model or provider dependency is added.

Package0.5.0 adds `review.grouping.propose(request)` and the contextual group task
prompt. Literal spelling variants preserve every original occurrence; semantic
equivalent/related/ambiguous proposals remain optional and require review. Record,
label-inventory and comparison coverage stay distinct. No taxonomy/entity merge.

Package 0.5.1 derives classification unit state from retained explicit basis outcomes:
an abstention stays in the insufficient-context subset of analyzed work, including
mixed/partial units. A supplied unit-state label cannot upgrade it to validated work.
