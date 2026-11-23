"""Find services whose source text says more than their structured fields, without a model.

`services` pairs each service candidate of a package with its record and cited assertions;
`texts` lists the printed strings worth reading in a record; `signals` finds in one string
hours with their scope (service, intake, contact), phones, emails, websites, access
requirements, intake (appointment, registration, referral) and cost; `triage` compares
them with the candidate's fields and returns gaps (the text has it, the field does not)
and doubts (the importer itself left it to verify). It reads only the package, so it
stays independent of the importer that wrote it.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from typing import Any, Iterator

FORMAT = "egi-review-triage/0.1"
SKIPPED_KEYS = {"sha256", "file", "slug", "identifier", "url", "link_raw", "citta_slug"}
LANGUAGE_KEYS = {"it", "en", "fr", "es", "ca", "ar", "de", "pt"}
WINDOW = 80  # characters around a time in which a day must appear
SCOPE_REACH = 200  # how far back on the same line a scope word still names the hours that follow
FIELDS = ("hours", "phone", "email", "web", "cost", "access", "intake")
# The importers' schedule scopes, folded into the three a reader can tell apart in text.
SCOPE_OF = {"service": "service", "lessons": "service", "office": "intake", "intake": "intake",
            "reception": "intake", "contact": "contact"}

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}", re.I)
WEB = re.compile(r"\b(?:https?://|www\.)[^\s<>\"')]+", re.I)

LOCALES: dict[str, dict[str, Any]] = {
    "it": {
        "day": re.compile(
            r"\b(?:lun(?:edì|edi)?|mar(?:tedì|tedi)?|mer(?:coledì|coledi)?|gio(?:vedì|vedi)?|"
            r"ven(?:erdì|erdi)?|sab(?:ato)?|dom(?:enica)?|feriali|festivi|orari[oe]?)\b", re.I),
        "time": re.compile(r"(?<![\d.,])(?:[01]?\d|2[0-3])[:.][0-5]\d(?![\d.,])|\bore\s+\d{1,2}\b|"
                           r"\bdalle\s+(?:ore\s+)?\d{1,2}\b|"
                           r"(?<![\w.,:/-])(?:[01]?\d|2[0-3])[ \t]*[-–—][ \t]*(?:[01]?\d|2[0-3])(?![\w.,:/-])", re.I),
        "phone": re.compile(r"(?<![\w.,:/-])(?:(?:\+|00)39[\s.-]?)?(?:0\d|3\d\d|80\d)(?:[\s.-]?\d){5,9}(?![\w:])"),
        # "06 45460313/4" may be two numbers: report it as printed, never join the digits
        "phone_suffix": re.compile(r"/\s?\d{1,3}(?!\d)"),
        "date": re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
        "cost": re.compile(r"\bgratuit[oaie]\b(?!\s+patrocinio)|\bgratis\b|\ba pagamento\b|\bcontributo\b|\bquota\b|€|\beuro\b", re.I),
        # a requirement word right after one of these names something the service offers
        "offer_before": re.compile(r"(?:supporto|assistenza|aiuto|rilascio|richiesta|orientamento|consulenza|"
                                   r"rinnovo|pratiche|disbrigo)\W+(?:\w+\W+){0,2}$", re.I),
        # the nearest of these before a time names whose hours they are; none means the service's
        "scope": {
            "intake": re.compile(r"segreteri\w*|accoglienza|ricevimento|sportello|iscrizion\w*|informazioni|colloqu\w*", re.I),
            "contact": re.compile(r"telefon\w*|chiamare|reperibil\w*|\btel\b", re.I),
            "service": re.compile(r"\bcors[oi]\b(?!\s+(?-i:[A-Z]))|lezion\w*|livell\w*|class[ei]\b|apertur\w*|\baperto\b", re.I),
        },
        # how to get in: reported apart from the conditions to be allowed in
        "intake": {
            "appointment": re.compile(r"appuntamento|prenota\w*", re.I),
            "registration": re.compile(r"\biscri(?:zione|zioni|versi)\b|tesseramento", re.I),
            "referral": re.compile(r"invio (?:da|dei|del)|segnalazione", re.I),
        },
        "access": {
            "documents": re.compile(r"\bdocument[oi]\b|carta d.identit|passaporto", re.I),
            "residence_permit": re.compile(r"permesso di soggiorno", re.I),
            "health_card": re.compile(r"tessera sanitaria|\bSTP\b|\bENI\b"),
            "tax_code": re.compile(r"codice fiscale", re.I),
            "residence": re.compile(r"\bresiden(?:za|ti)\b", re.I),
            "isee": re.compile(r"\bISEE\b"),
            "age": re.compile(r"maggiorenn\w*|minorenn\w*|\b\d{2}\s*anni\b", re.I),
        },
    },
}


def services(package: dict[str, Any]) -> Iterator[tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]]:
    """Yield (service candidate, its principal record, assertions by key) for each service."""
    records = {r["key"]: r for r in package["records"]}
    subjects = {s["key"]: s for s in package["subjects"]}
    assertions = {a["key"]: a for a in package["assertions"]}
    for candidate in package["candidates"]:
        if candidate["kind"] != "service":
            continue
        subject = subjects[candidate["subject_keys"][0]]
        yield candidate, records[subject["record_key"]], assertions


def texts(raw: Any, language: str, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield (JSON path, readable text) for every printed string, HTML turned into lines.

    Identifiers, hashes, file names and translations into other languages are skipped.
    """
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in SKIPPED_KEYS or (key in LANGUAGE_KEYS and key != language):
                continue
            yield from texts(value, language, f"{path}/{key}")
    elif isinstance(raw, list):
        for index, value in enumerate(raw):
            yield from texts(value, language, f"{path}/{index}")
    elif isinstance(raw, str) and raw.strip():
        text = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", raw, flags=re.I)
        yield path or "/", html.unescape(re.sub(r"<[^>]+>", " ", text))


def signals(text: str, language: str) -> dict[str, list[dict[str, Any]]]:
    """Find in one string what a reviewer should compare with the fields.

    Returns lists keyed by the names in `FIELDS`; each item has the matched `value` and a
    short `snippet` of the text around it. For hours the value is the scope (`service`,
    `intake` or `contact`), one item per scope found.
    """
    locale = LOCALES[language]
    found: dict[str, list[dict[str, Any]]] = {k: [] for k in FIELDS}
    scopes = set()
    for match in locale["time"].finditer(text):
        around = text[max(0, match.start() - WINDOW):match.end() + WINDOW]
        if not locale["day"].search(around):
            continue
        line_start = max(text.rfind("\n", 0, match.start()) + 1, match.start() - SCOPE_REACH)
        scope = _scope(text[line_start:match.start()], locale)
        if scope not in scopes:
            scopes.add(scope)
            found["hours"].append(_item(text, match, scope))
    dates = [m.span() for m in locale["date"].finditer(text)]
    for match in locale["phone"].finditer(text):
        if any(s <= match.start() < e for s, e in dates):
            continue
        number = phone_digits(match.group())
        if not 6 <= len(number) <= 11:
            continue
        suffix = locale["phone_suffix"].match(text, match.end())
        if suffix:
            number += "/" + re.sub(r"\D", "", suffix.group())
        found["phone"].append(_item(text, match, number))
    for match in EMAIL.finditer(text):
        found["email"].append(_item(text, match, match.group().lower()))
    for match in WEB.finditer(text):
        found["web"].append(_item(text, match, web_host(match.group())))
    for match in locale["cost"].finditer(text):
        found["cost"].append(_item(text, match, match.group().lower()))
        break
    if len(text.split()) < 2:
        found["cost"] = []
        return found  # a lone word is a code or a category, not a stated condition
    for field in ("access", "intake"):
        for kind, pattern in locale[field].items():
            for match in pattern.finditer(text):
                if not locale["offer_before"].search(text[max(0, match.start() - 40):match.start()]):
                    found[field].append(_item(text, match, kind))
                    break
    return found


def triage(package: dict[str, Any], default_language: str = "it") -> dict[str, Any]:
    """Compare each service's source text with its fields; return the triage document."""
    results, gaps_by_field, doubts_by_field = [], Counter(), Counter()
    total = 0
    for candidate, record, assertions in services(package):
        total += 1
        fields = candidate["fields"]
        language = fields.get("original_language") or default_language
        if language not in LOCALES:
            language = default_language
        have = _structured(fields, assertions)
        gaps, doubts, seen = [], [], set()
        for path, text in texts(record["raw_payload"], language):
            for field, items in signals(text, language).items():
                for item in items:
                    if _covered(field, item["value"], have) or (field, item["value"]) in seen:
                        continue
                    seen.add((field, item["value"]))
                    gaps.append({"field": field, "value": item["value"], "snippet": item["snippet"], "path": path})
        if have["to_verify"]:
            doubts.append({"field": "hours", "value": have["to_verify"], "reason": "importer_to_verify"})
        for gap in {g["field"] for g in gaps}:
            gaps_by_field[gap] += 1
        for doubt in {d["field"] for d in doubts}:
            doubts_by_field[doubt] += 1
        if gaps or doubts:
            results.append({"candidate": candidate["key"], "record": record.get("external_key") or record["key"],
                            "name": (fields.get("name") or {}).get("value"), "link": _link(record["raw_payload"]),
                            "gaps": gaps, "doubts": doubts})
    results.sort(key=lambda r: (-len(r["gaps"]) - len(r["doubts"]), r["candidate"]))
    return {"format": FORMAT, "package_digest": package.get("package_digest"), "services": total,
            "flagged": len(results), "gaps_by_field": dict(sorted(gaps_by_field.items())),
            "doubts_by_field": dict(sorted(doubts_by_field.items())), "results": results}


def phone_digits(value: str) -> str:
    """Return a phone number's digits without the Italian international prefix."""
    digits = re.sub(r"\D", "", value)
    for prefix in ("0039", "39"):
        if digits.startswith(prefix) and len(digits) - len(prefix) >= 6 and digits[len(prefix)] in "038":
            return digits[len(prefix):]
    return digits


def web_host(value: str) -> str:
    """Return a website's host without scheme, `www.` or trailing punctuation."""
    host = re.sub(r"^(?:https?://)?(?:www\.)?", "", value.lower()).split("/")[0]
    return host.rstrip(".,;:")


def _structured(fields: dict[str, Any], assertions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Collect what the candidate already states: contacts, hours, access and cost."""
    contacts = fields.get("contacts") or []
    schedule = [assertions[k]["normalized_value"] for k in fields.get("schedule_assertion_keys", []) if k in assertions]
    access = [assertions[k]["normalized_value"] for k in fields.get("access_assertion_keys", []) if k in assertions]
    return {
        "phone": {phone_digits(c["value"]) for c in contacts if c["channel"] in {"phone", "whatsapp"}},
        "email": {c["value"].lower() for c in contacts if c["channel"] == "email"},
        "web": {web_host(c["value"]) for c in contacts if c["channel"] in {"web", "website"}},
        "hours": {SCOPE_OF.get(scope, scope) for value in schedule for scope in _scopes(value)},
        "to_verify": [d for value in schedule for d in _find(value, "to_verify")],
        "access": any(_nonempty(value) for value in access),
        "intake": any(_nonempty(value) for value in access),
        "cost": fields.get("cost_state") not in (None, "unknown") or bool((fields.get("cost_note") or {}).get("value")),
    }


def _covered(field: str, value: Any, have: dict[str, Any]) -> bool:
    """Say whether a signal from the text is already in the structured fields."""
    if field in {"phone", "email", "web", "hours"}:
        return value in have[field]
    return bool(have[field])


def _has_days(value: Any) -> bool:
    """True when a schedule value states at least one open or closed day."""
    if isinstance(value, dict):
        if value.get("state") in {"intervals", "closed"}:
            return True
        return any(_has_days(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_days(v) for v in value)
    return False


def _link(raw: Any) -> str | None:
    """Return the first web address the record stores under a key named `url`."""
    if isinstance(raw, dict):
        value = raw.get("url")
        if isinstance(value, str) and value.startswith("http"):
            return value
        values = raw.values()
    elif isinstance(raw, list):
        values = raw
    else:
        return None
    return next((link for link in map(_link, values) if link), None)


def _scope(before: str, locale: dict[str, Any]) -> str:
    """Name the scope whose keyword ends nearest to the time that follows `before`."""
    nearest, scope = -1, "service"
    for name, pattern in locale["scope"].items():
        for match in pattern.finditer(before):
            if match.end() > nearest:
                nearest, scope = match.end(), name
    return scope


def _scopes(value: Any) -> set[str]:
    """Collect the scope of every schedule part that states at least one day."""
    if isinstance(value, dict):
        own = {value["scope"]} if isinstance(value.get("scope"), str) and _has_days(value) else set()
        return own | {s for v in value.values() for s in _scopes(v)}
    if isinstance(value, list):
        return {s for v in value for s in _scopes(v)}
    return set()


def _find(value: Any, key: str) -> list[Any]:
    """Collect every list stored under `key` anywhere in a value."""
    if isinstance(value, dict):
        own = value.get(key) if isinstance(value.get(key), list) else []
        return own + [x for k, v in value.items() if k != key for x in _find(v, key)]
    if isinstance(value, list):
        return [x for v in value for x in _find(v, key)]
    return []


def _nonempty(value: Any) -> bool:
    """True when a value holds any list item or text."""
    if isinstance(value, dict):
        return any(_nonempty(v) for v in value.values())
    if isinstance(value, list):
        return bool(value)
    return isinstance(value, str) and bool(value.strip())


def _item(text: str, match: re.Match[str], value: Any) -> dict[str, Any]:
    """Describe a match with its value and up to 60 characters on each side, on one line."""
    snippet = text[max(0, match.start() - 60):match.end() + 60]
    return {"value": value, "snippet": " ".join(snippet.split())}
