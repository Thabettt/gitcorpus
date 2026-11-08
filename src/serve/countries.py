from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_FILE = Path(__file__).with_name("data") / "country_wealth.json"
UNKNOWN_COUNTRY = "??"


@lru_cache(maxsize=1)
def _catalogue() -> dict[str, dict[str, Any]]:
    with _DATA_FILE.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    return {
        str(iso).upper(): dict(values)
        for iso, values in raw.items()
        if isinstance(iso, str) and len(iso) == 2 and isinstance(values, dict)
    }


def country_name(iso: str | None) -> str | None:
    """Human name for an ISO 3166-1 alpha-2 code, or the code when unknown."""
    if not iso:
        return None
    code = str(iso).strip().upper()
    if not code:
        return None
    entry = _catalogue().get(code)
    if entry and entry.get("name"):
        return str(entry["name"])
    return code


def country_wealth(iso: str | None) -> dict[str, Any] | None:
    if not iso:
        return None
    return _catalogue().get(str(iso).strip().upper())


def gdp_per_capita(iso: str | None) -> float | None:
    entry = country_wealth(iso)
    value = entry.get("gdp_pc") if entry else None
    return float(value) if isinstance(value, (int, float)) else None


def income_group(iso: str | None) -> str | None:
    entry = country_wealth(iso)
    value = entry.get("income_group") if entry else None
    return str(value) if value else None


def wealth_source() -> str:
    return (
        "World Bank: GDP per capita (current US$, latest available year) and "
        "income group (FY2025 classification)."
    )
