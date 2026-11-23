# What a service is (review profile 0.1)

This profile tells a reviewer, human or agent, what to look for in a source's text for
one service. It follows the canonical package contract
([common-import](../../egi-importer/docs/contracts/common-import.md)) (on the importer's C2 branch until merged) and the weekly hours shape of
`importers/common/schedule.py`. A reviewer reads only what the source printed. It never
fills a field from general knowledge, and it quotes the exact words it relied on.

## Fields

| Field | What counts | Never |
| --- | --- | --- |
| name | The name the source gives to the service or the site | A name invented from the organization |
| hours | Days and times, with their scope: `service` (open to the public), `intake` (reception, first contact, registration), `contact` (phone or email hours), `lessons` (courses) | Read a missing day as closed; join two scopes in one week |
| contacts | Phone, WhatsApp, email, website, each with its purpose if printed (e.g. "ore pasti", "solo SMS") | Treat an organization's generic switchboard as the service's own when the text says otherwise |
| access | Conditions to use the service: documents required or not, residence permit, health card (STP/ENI), tax code, residence, ISEE, age, gender, family, appointment or booking, registration, referral by another service | Read "for migrants" as a requirement when it describes the audience only; infer a requirement from silence |
| cost | Free, paid, contribution, membership fee, with the printed amount | Read free from a missing price |
| languages | Languages spoken or taught, when printed | |
| place | Address or area where it happens; online or phone only | Combine an area with a fixed address |
| audience | Who it is for (women, minors, families, people without a home) | Turn an audience into an exclusion unless the text says only |

## Rules

- A value comes with the shortest exact quotation that supports it, copied character for
  character from the source text. No quotation, no value.
- Uncertain is a valid answer: say what is ambiguous instead of choosing.
- A day or time that looks impossible (start equals end, end before start) is reported as
  printed, not repaired.
- Several services printed together (e.g. two courses, a canteen and a shower) stay
  separate; say which one each value belongs to.
- Dates of validity (summer closure, "fino a giugno") are reported with the value they
  limit.

## Language notes

### Italian (`it`)

Days: lunedì … domenica, abbreviated `lun mar mer gio ven sab dom`, ranges such as
"dal lunedì al venerdì", "Lun-Gio", "feriali", "festivi". Times: `9:30`, `9.30`, `ore 9`,
`dalle 9 alle 13`, `9-13`. Phones: landlines start with `0` (Rome `06`), mobiles with `3`,
toll free `800`; the `+39` prefix is not part of the number. Typical requirements:
"senza documenti", "permesso di soggiorno", "tessera sanitaria", "STP", "ENI",
"codice fiscale", "residenza", "ISEE", "su appuntamento", "prenotazione", "iscrizione",
"tessera", "maggiorenni".
