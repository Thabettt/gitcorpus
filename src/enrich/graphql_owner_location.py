from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from lib.graphql_batch import DEFAULT_BATCH_SIZE, ParsedBatch, rate_limit_from_payload


@dataclass(frozen=True)
class OwnerGeoProfile:
    location: str | None
    blog: str | None


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


class OwnerLocationAdapter:
    name = "owner_location"

    def __init__(self, owners: Mapping[str, str], *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self._owners = dict(owners)
        self.batch_size = batch_size

    def _field(self, alias: str, login: str) -> str:
        kind = "organization" if self._owners[login] == "Organization" else "user"
        return f"  {alias}: {kind}(login: {json.dumps(login)}) {{ location }}"

    def build_query(self, aliases: Mapping[str, str]) -> str:
        lines = ["query {"]
        lines.extend(self._field(alias, key) for alias, key in aliases.items())
        lines.append("  rateLimit { cost used remaining }")
        lines.append("}")
        return "\n".join(lines)

    def parse(self, payload: Mapping[str, object], aliases: Mapping[str, str]) -> ParsedBatch:
        data = payload.get("data")
        values: dict[str, str | None] = {}
        rate_limit = rate_limit_from_payload(payload)
        if not isinstance(data, dict):
            return ParsedBatch(values=values, rate_limit=rate_limit)
        for alias, key in aliases.items():
            node = data.get(alias)
            if not isinstance(node, dict):
                continue
            location = node.get("location")
            values[key] = location if isinstance(location, str) and location.strip() else None
        return ParsedBatch(values=values, rate_limit=rate_limit)


class OwnerGeoProfileAdapter:
    """Fetch every zero-extra-cost profile signal used by geo resolution."""

    name = "owner_geo_profile"

    def __init__(self, owners: Mapping[str, str], *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self._owners = dict(owners)
        self.batch_size = batch_size

    def _field(self, alias: str, login: str) -> str:
        kind = "organization" if self._owners[login] == "Organization" else "user"
        return f"  {alias}: {kind}(login: {json.dumps(login)}) " "{ location websiteUrl }"

    def build_query(self, aliases: Mapping[str, str]) -> str:
        lines = ["query {"]
        lines.extend(self._field(alias, key) for alias, key in aliases.items())
        lines.append("  rateLimit { cost used remaining }")
        lines.append("}")
        return "\n".join(lines)

    def parse(self, payload: Mapping[str, object], aliases: Mapping[str, str]) -> ParsedBatch:
        data = payload.get("data")
        values: dict[str, OwnerGeoProfile] = {}
        rate_limit = rate_limit_from_payload(payload)
        if not isinstance(data, dict):
            return ParsedBatch(values=values, rate_limit=rate_limit)
        for alias, key in aliases.items():
            node = data.get(alias)
            if not isinstance(node, dict):
                continue
            values[key] = OwnerGeoProfile(
                location=_optional_text(node.get("location")),
                blog=_optional_text(node.get("websiteUrl")),
            )
        return ParsedBatch(values=values, rate_limit=rate_limit)
