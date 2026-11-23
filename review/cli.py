"""The egi-review command: `triage` reads one importer run and writes what to review.

Output goes to `<root>/reviews/<source>/<run>/` beside the run's `<root>/runs/`, outside Git:
`triage.json` for programs and `triage.md`, one section per service, for a person.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from review.triage import triage


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run a subcommand; return the exit status."""
    parser = argparse.ArgumentParser(prog="egi-review", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("triage", help="find services whose text says more than their fields")
    run.add_argument("run", type=Path, help="an importer run directory (holding package.json and run.json)")
    run.add_argument("--language", default="it", help="language of the source when a service does not say")
    run.add_argument("--out", type=Path, help="output file instead of <root>/reviews/<source>/<run>/triage.json")
    run.add_argument("--show", type=int, default=5, help="examples to print per field")
    args = parser.parse_args(argv)
    return _triage(args.run, args.language, args.out, args.show)


def _triage(run: Path, language: str, out: Path | None, show: int) -> int:
    """Triage one run, write the document and print a summary."""
    try:
        package = json.loads((run / "package.json").read_text(encoding="utf-8"))
        meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"egi-review: cannot read the run: {error}", file=sys.stderr)
        return 2
    if out is None:
        if run.resolve().parent.parent.name != "runs":
            print("egi-review: the run is not under <root>/runs/<source>/; pass --out", file=sys.stderr)
            return 2
        root = run.resolve().parent.parent.parent
        out = root / "reviews" / meta["source"] / meta["run_id"] / "triage.json"
    document = {"source": meta["source"], "run_id": meta["run_id"], **triage(package, language)}
    report = out.with_suffix(".md")
    _write(out, json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    _write(report, markdown(document))
    print(_summary(document, show))
    print(f"\nwritten: {out}\n         {report}")
    return 0


def _summary(document: dict[str, Any], show: int) -> str:
    """Render counts per field and a few examples of each gap."""
    lines = [f"{document['source']} {document['run_id']}: {document['flagged']} of {document['services']} services to review"]
    for title, counts in (("text has it, field does not", document["gaps_by_field"]),
                          ("importer left to verify", document["doubts_by_field"])):
        if counts:
            lines.append(f"  {title}: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    for field in document["gaps_by_field"]:
        lines.append(f"\n[{field}]")
        examples = [(r, g) for r in document["results"] for g in r["gaps"] if g["field"] == field][:show]
        for result, gap in examples:
            lines.append(f"  {result['name']}: {gap['value']} | …{gap['snippet']}…")
    return "\n".join(lines)


LABELS = {"hours": "orari", "phone": "telefono", "email": "email", "web": "sito", "cost": "costo",
          "access": "requisiti", "intake": "accesso (iscrizione, prenotazione, invio)"}
SCOPES = {"service": "del servizio o dei corsi", "intake": "di segreteria o accoglienza", "contact": "di contatto"}


def markdown(document: dict[str, Any]) -> str:
    """Render the triage for a person: counts, then one section per service with what is missing."""
    lines = [f"# Triage {document['source']} — run {document['run_id']}", "",
             f"{document['flagged']} servizi da rivedere su {document['services']}.", "",
             "| Campo | Servizi: il testo lo dice, il campo no |", "| --- | --- |"]
    lines += [f"| {LABELS.get(k, k)} | {v} |" for k, v in document["gaps_by_field"].items()]
    lines += [f"| {LABELS.get(k, k)} da verificare (importer) | {v} |" for k, v in document["doubts_by_field"].items()]
    for result in document["results"]:
        title = result["name"] or result["record"]
        lines += ["", f"## {title}", "", f"`{result['record']}`" + (f" — <{result['link']}>" if result["link"] else ""), ""]
        for gap in result["gaps"]:
            what = f"orari {SCOPES.get(gap['value'], gap['value'])}" if gap["field"] == "hours" else \
                f"{LABELS.get(gap['field'], gap['field'])}: {gap['value']}"
            lines.append(f"- **{what}** — «{gap['snippet']}»")
        for doubt in result["doubts"]:
            printed = "; ".join(f"giorno {d.get('weekday')}: {d.get('printed')} ({d.get('reason')})" for d in doubt["value"])
            lines.append(f"- **orari da verificare** — {printed}")
    return "\n".join(lines) + "\n"


def _write(path: Path, content: str) -> None:
    """Write text atomically, creating the directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".triage-")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(content)
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
