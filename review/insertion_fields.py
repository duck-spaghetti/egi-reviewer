"""Frozen B3.1 preparation vocabulary, independent of provider and importer code.

`validate_body` checks proposed service/location structures and scalar domains;
`dictionary` exposes the versioned field vocabulary for an adapter's output schema.
No function resolves identities, normalizes contacts, geocodes or writes data.
"""
from __future__ import annotations

import math
from datetime import date, time
from typing import Any

VERSION = "egi-preparation-fields/1"
ESSENTIAL_FIELDS = {"name", "description", "value", "formatted", "line1", "locality", "postal_code",
                    "administrative_area", "country_code", "latitude", "longitude", "opens", "closes"}

SERVICE = {
    "name": "str", "description": "str", "original_language": "str",
    "delivery_mode": "str", "operational_status": "str", "cost_state": "str",
    "cost_note": "str", "valid_from": "date", "valid_until": "date",
    "closure_date": "date", "closure_reason": "str", "contacts": "contacts[]",
    "territories": "references", "place": "place", "organizations": "organizations[]",
    "conditions": "conditions[]", "contact_links": "contact_links[]",
    "languages": "languages[]", "coverage": "coverage[]",
    "classifications": "classifications[]", "schedules": "schedules[]",
    "calendar_links": "calendar_links[]",
}
LOCATION = {
    "name": "str", "original_language": "str", "location_kind": "str",
    "latitude": "number", "longitude": "number", "coordinate_state": "str",
    "selected_geocoding_result_id": "reference", "parent_location_id": "reference",
    "addresses": "addresses[]", "contacts": "contacts[]", "organizations": "organizations[]",
    "territories": "references", "schedules": "schedules[]", "calendar_links": "calendar_links[]",
}
COMPONENTS = {
    "contacts": {"component_id": "reference", "channel_type": "str", "value": "str",
                 "normalized_value": "str", "purpose_code": "str", "label": "str",
                 "sort_order": "int", "is_public": "permission"},
    "addresses": {"component_id": "reference", "address_kind": "str", "formatted": "str",
                  "line1": "str", "locality": "str", "postal_code": "str", "administrative_area": "str",
                  "country_code": "str", "normalization_state": "str"},
    "organizations": {"component_id": "reference", "organization_id": "reference", "role_code": "str"},
    "conditions": {"component_id": "reference", "condition_kind": "str", "requirement_state": "str", "details": "str"},
    "contact_links": {"component_id": "reference", "target_entity_id": "reference",
                      "target_contact_component_id": "reference", "purpose_code": "str", "label": "str"},
    "languages": {"language_code": "str", "availability_kind": "str", "note": "str"},
    "coverage": {"component_id": "reference", "territory_id": "reference", "geometry_wkt": "str", "description": "str"},
    "classifications": {"adoption_id": "reference", "term_id": "reference"},
    "place": {"component_id": "reference", "location_id": "reference", "territory_id": "reference", "area_description": "str"},
    "schedules": {"component_id": "reference", "scope": "str", "timezone": "str", "contact_component_id": "reference",
                  "valid_from": "date", "valid_until": "date", "completeness": "str", "days": "days[]"},
    "days": {"weekday": "int", "state": "str", "completeness": "str", "intervals": "intervals[]"},
    "intervals": {"component_id": "reference", "opens": "time", "closes": "time", "end_day_offset": "int"},
    "calendar_links": {"schedule_id": "reference", "calendar_id": "reference", "effects": "effects[]"},
    "effects": {"component_id": "reference", "event_version_id": "reference", "kind": "str", "intervals": "intervals[]"},
}
ENUMS = {
    "delivery_mode": {"in_person", "telephone", "online", "itinerant"},
    "operational_status": {"active", "inactive", "temporarily_closed", "defunct", "unknown"},
    "cost_state": {"free", "paid", "variable", "unknown"},
    "channel_type": {"phone", "email", "web", "whatsapp", "other"},
    "condition_kind": {"appointment", "referral", "document", "eligibility", "other"},
    "requirement_state": {"required", "not_required", "conditional", "unknown"},
    "normalization_state": {"raw", "normalized", "uncertain"},
    "coordinate_state": {"known", "unknown", "uncertain"},
    "availability_kind": {"spoken", "interpreted"},
    "scope": {"service", "intake", "contact"},
    "completeness": {"complete", "partial", "unknown"},
}


class ContractError(ValueError):
    """A safe catalogued code/path, without original text or provider error content."""

    def __init__(self, code: str = "invalid_shape", path: str = "") -> None:
        """Retain only machine identifiers that a caller can translate safely."""
        super().__init__(code)
        self.code, self.path = code, path


def closed(value: Any, keys: set[str], required: set[str], path: str = "") -> dict:
    """Require a JSON object with exactly its allowed and required key sets."""
    if not isinstance(value, dict) or not set(value) <= keys or not required <= set(value):
        raise ContractError("invalid_shape", path)
    return value


def pointer_part(value: str) -> str:
    """Escape one RFC6901 key for diagnostics and evidence field paths."""
    return value.replace("~", "~0").replace("/", "~1")


def _scalar(value: Any, descriptor: str, key: str, path: str) -> None:
    """Check one optional-but-present fact without fabricating defaults or IDs."""
    if descriptor in {"reference", "permission"}:
        raise ContractError("unresolved_reference" if descriptor == "reference" else "unsupported_field", path)
    if descriptor == "int":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif descriptor == "number":
        valid = (isinstance(value, int) and not isinstance(value, bool)
                 or isinstance(value, float) and math.isfinite(value))
    else:
        valid = isinstance(value, str) and len(value) <= 50000
    if not valid:
        raise ContractError("invalid_shape", path)
    if key in ENUMS and value not in ENUMS[key]:
        raise ContractError("unsupported_field", path)
    try:
        if descriptor == "date":
            date.fromisoformat(value)
        if descriptor == "time":
            parsed = time.fromisoformat(value)
            if parsed.tzinfo is not None:
                raise ValueError("local time required")
    except ValueError as error:
        raise ContractError("invalid_shape", path) from error
    if key == "weekday" and value not in range(1, 8):
        raise ContractError("invalid_shape", path)
    if key == "end_day_offset" and value not in (0, 1):
        raise ContractError("invalid_shape", path)
    if key == "latitude" and not -90 <= value <= 90 or key == "longitude" and not -180 <= value <= 180:
        raise ContractError("invalid_shape", path)


def _object(value: Any, fields: dict[str, str], path: str, *, location: bool) -> None:
    """Walk one closed body/component using the single frozen field dictionary."""
    closed(value, set(fields), set(), path)
    for key, item in value.items():
        descriptor = fields[key]
        here = f"{path}/{pointer_part(key)}"
        if descriptor.endswith("[]") or descriptor == "references":
            if not isinstance(item, list) or len(item) > 1000:
                raise ContractError("invalid_shape", here)
            if descriptor == "references":
                if item:
                    raise ContractError("unresolved_reference", here)
                continue
            child_fields = COMPONENTS[descriptor[:-2]]
            for index, child in enumerate(item):
                _object(child, child_fields, f"{here}/{index}", location=location)
        elif descriptor in COMPONENTS:
            _object(item, COMPONENTS[descriptor], here, location=location)
        else:
            _scalar(item, descriptor, key, here)
    if fields is COMPONENTS["intervals"] and "opens" in value and "closes" in value:
        opens, closes = time.fromisoformat(value["opens"]), time.fromisoformat(value["closes"])
        overnight = value.get("end_day_offset", 0)
        if not (overnight == 0 and closes > opens or overnight == 1 and closes <= opens):
            raise ContractError("invalid_shape", path)
    if fields is COMPONENTS["days"]:
        if value.get("state") not in (None, "intervals", "closed", "unknown"):
            raise ContractError("unsupported_field", path + "/state")
        if value.get("state") in ("closed", "unknown") and value.get("intervals"):
            raise ContractError("invalid_shape", path + "/intervals")
    if fields is COMPONENTS["effects"] and value.get("kind") not in (None, "closed", "replace", "add"):
        raise ContractError("unsupported_field", path + "/kind")
    if fields is COMPONENTS["schedules"]:
        if location and value.get("scope") not in (None, "contact"):
            raise ContractError("unsupported_field", path + "/scope")
        days = [day["weekday"] for day in value.get("days", []) if "weekday" in day]
        if len(days) != len(set(days)):
            raise ContractError("invalid_shape", path + "/days")


def validate_body(body: Any, kind: str, path: str) -> None:
    """Validate an incomplete proposed aggregate, with no provider-owned identities."""
    _object(body, SERVICE if kind == "service" else LOCATION, path, location=kind == "location")


def dictionary() -> dict:
    """Return an independent serializable copy of the versioned field vocabulary."""
    return {"version": VERSION, "service": dict(SERVICE), "location": dict(LOCATION),
            "components": {key: dict(value) for key, value in COMPONENTS.items()},
            "enums": {key: sorted(value) for key, value in ENUMS.items()}}
