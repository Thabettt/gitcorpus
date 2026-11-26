"""One-shot backfill: load Stage-2 thesis country data into owners.

CSV: /Users/mano/Desktop/me-thesis-coding-agent-adoption/data/stage2/owner_locations_all.csv
    cols: owner_login, location_raw, inferred_country, confidence, source

Writes to the owners table:
    location_raw, country_iso, geo_confidence, synced_at, geo_version
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine, text  # noqa: E402

CSV_PATH = Path(
    "/Users/mano/Desktop/me-thesis-coding-agent-adoption/data/stage2/owner_locations_all.csv"
)
CATALOGUE = Path(__file__).resolve().parents[1] / "src/serve/data/country_wealth.json"
GEO_VERSION = "stage2-2026-10-25"

CONFIDENCE_MAP = {
    "high": "name",
    "medium": "region",
    "low": "weak",
    "none": "unmatched",
}

# Common aliases for country names not in the catalogue verbatim.
# Only required where the CSV name differs from the catalogue's `name` field.
ALIASES = {
    "United States": "US",
    "USA": "US",
    "U.S.": "US",
    "United Kingdom": "GB",
    "UK": "GB",
    "Great Britain": "GB",
    "South Korea": "KR",
    "Korea, South": "KR",
    "North Korea": "KP",
    "Russia": "RU",
    "Russian Federation": "RU",
    "Vietnam": "VN",
    "Viet Nam": "VN",
    "Iran": "IR",
    "Syria": "SY",
    "Taiwan": "TW",
    "Hong Kong": "HK",
    "Czech Republic": "CZ",
    "Czechia": "CZ",
    "Tanzania": "TZ",
    "Venezuela": "VE",
    "Bolivia": "BO",
    "Moldova": "MD",
    "Macedonia": "MK",
    "North Macedonia": "MK",
    "Laos": "LA",
    "Brunei": "BN",
    "Cape Verde": "CV",
    "Ivory Coast": "CI",
    "Côte d'Ivoire": "CI",
    "Myanmar": "MM",
    "Burma": "MM",
    "East Timor": "TL",
    "Timor-Leste": "TL",
    "DR Congo": "CD",
    "Congo (Kinshasa)": "CD",
    "Congo (Brazzaville)": "CG",
    "Swaziland": "SZ",
    "Eswatini": "SZ",
    "Palestine": "PS",
    "Palestinian Territory": "PS",
    "Kosovo": "XK",
    "Vatican City": "VA",
    "Holy See": "VA",
    "Micronesia": "FM",
    # World Bank naming + native-language spellings seen in the thesis CSV
    "Turkey": "TR",
    "Türkiye": "TR",
    "Egypt": "EG",
    "Slovakia": "SK",
    "Slovak": "SK",
    "Yemen": "YE",
    "Belarus": "BY",
    "Беларусь": "BY",
    "Dominican Republic": "DO",
    "República Dominicana": "DO",
    "Estonia": "EE",
    "Eesti": "EE",
    "Slovenia": "SI",
    "Slovenija": "SI",
    "Benin": "BJ",
    "Bénin": "BJ",
    "Lithuania": "LT",
    "Lietuva": "LT",
    "Bosnia": "BA",
    "Bosnia and Herzegovina": "BA",
    "Paraguay / Paraguái": "PY",
    "Kosova / Kosovo": "XK",
    "Civitas Vaticana - Città del Vaticano": "VA",
    "Mozambique": "MZ",
    "Moçambique": "MZ",
    "Somalia": "SO",
    "Soomaaliya الصومال": "SO",
    "Côte d'Ivoire": "CI",
    "Côte d’Ivoire": "CI",
    "Cote d'Ivoire": "CI",
    "Cyprus": "CY",
    "Κύπρος - Kıbrıs": "CY",
    "Cameroon": "CM",
    "Cameroun": "CM",
    "Madagascar": "MG",
    "Madagasikara / Madagascar": "MG",
}


def load_name_to_iso() -> dict[str, str]:
    with CATALOGUE.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    out: dict[str, str] = {}
    for iso, entry in raw.items():
        name = (entry or {}).get("name")
        if isinstance(name, str) and name:
            out[name.strip().lower()] = iso.upper()
    for alias, iso in ALIASES.items():
        out[alias.strip().lower()] = iso.upper()
    return out


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found", file=sys.stderr)
        return 1
    name_to_iso = load_name_to_iso()
    engine = create_engine(os.environ["DATABASE_URL"])

    rows_read = 0
    matched = 0
    unresolved = Counter()
    not_in_db = 0
    updated = 0
    now = datetime.now(timezone.utc)

    with CSV_PATH.open(newline="", encoding="utf-8") as fh, engine.begin() as conn:
        reader = csv.DictReader(fh)
        batch: list[dict] = []
        for row in reader:
            rows_read += 1
            login = (row.get("owner_login") or "").strip()
            if not login:
                continue

            raw_country = (row.get("inferred_country") or "").strip()
            raw_conf = (row.get("confidence") or "").strip().lower()
            location_raw = (row.get("location_raw") or "").strip() or None

            confidence = CONFIDENCE_MAP.get(raw_conf, "unmatched")

            iso: str | None = None
            if raw_country and raw_country.lower() not in {"not_specified", "", "none"}:
                iso = name_to_iso.get(raw_country.lower())
                if iso:
                    matched += 1
                else:
                    unresolved[raw_country] += 1
                    confidence = "unmatched"

            batch.append(
                {
                    "login": login,
                    "location_raw": location_raw,
                    "country_iso": iso,
                    "geo_confidence": confidence,
                    "synced_at": now,
                    "geo_version": GEO_VERSION,
                }
            )

            if len(batch) >= 2000:
                res = conn.execute(
                    text(
                        """
                        UPDATE owners SET
                            location_raw   = :location_raw,
                            country_iso    = :country_iso,
                            geo_confidence = :geo_confidence,
                            synced_at      = :synced_at,
                            geo_version    = :geo_version
                        WHERE login = :login
                        """
                    ),
                    batch,
                )
                updated += res.rowcount or 0
                not_in_db += len(batch) - (res.rowcount or 0)
                batch.clear()

        if batch:
            res = conn.execute(
                text(
                    """
                    UPDATE owners SET
                        location_raw   = :location_raw,
                        country_iso    = :country_iso,
                        geo_confidence = :geo_confidence,
                        synced_at      = :synced_at,
                        geo_version    = :geo_version
                    WHERE login = :login
                    """
                ),
                batch,
            )
            updated += res.rowcount or 0
            not_in_db += len(batch) - (res.rowcount or 0)

    print(json.dumps(
        {
            "rows_read": rows_read,
            "matched_to_iso": matched,
            "db_rows_updated": updated,
            "csv_logins_not_in_db": not_in_db,
            "unresolved_country_names": sum(unresolved.values()),
            "unresolved_distinct": len(unresolved),
        },
        indent=2,
    ))
    if unresolved:
        print("\nTop unresolved country names (first 20):")
        for name, n in unresolved.most_common(20):
            print(f"  {name}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
