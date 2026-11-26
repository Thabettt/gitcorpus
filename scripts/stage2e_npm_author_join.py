#!/usr/bin/env python3
"""
Stage 2e -- npm author join
===========================
Attempts to resolve owner country via the npm registry. For each unresolved
owner (country_iso blank in the integrated CSV), we:

  1. Query npm's search API for packages where the GitHub login is a
     maintainer: https://registry.npmjs.org/-/v1/search?text=maintainer:<login>
  2. For the top matching package(s), fetch registry metadata and read the
     maintainer email that corresponds to the GitHub login.
  3. Map the email domain's country-code TLD to a country ISO2.

This is a prototype -- it only exercises a single, well-defined signal
(maintainer email TLD). No scraping, no authentication, no GitHub API.

Inputs
------
  integrated_datasets/corpus_integrated_js-ts_run4_20261119_170535.csv
  src/serve/data/country_wealth.json         (ISO2 -> metadata)

Outputs
-------
  scripts/out/stage2e_npm_resolutions.csv
    owner_login, package_name, maintainer_email, email_domain,
    inferred_country, country_iso, source

  scripts/out/stage2e_npm_cache.json
    per-owner cache so the run is resumable

Usage
-----
  python3 scripts/stage2e_npm_author_join.py \
      [--limit N]           # cap owners processed (prototype runs)
      [--workers K]         # parallel HTTP workers (default 8)
      [--min-sleep 0.05]    # politeness delay per request
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests

ROOT   = Path(__file__).resolve().parents[1]
MAIN   = ROOT / "integrated_datasets" / "corpus_integrated_js-ts_run4_20261119_170535.csv"
WEALTH = ROOT / "src" / "serve" / "data" / "country_wealth.json"
OUT_DIR = ROOT / "scripts" / "out"
OUT_CSV   = OUT_DIR / "stage2e_npm_resolutions.csv"
OUT_CACHE = OUT_DIR / "stage2e_npm_cache.json"

NPM_SEARCH = "https://registry.npmjs.org/-/v1/search"
NPM_PKG    = "https://registry.npmjs.org/{pkg}"

# TLD -> ISO2 (reuses stage2b map, converted to ISO)
TLD_TO_ISO = {
    ".eg":"EG",".ng":"NG",".za":"ZA",".ke":"KE",".gh":"GH",".et":"ET",
    ".ma":"MA",".tn":"TN",".dz":"DZ",".sa":"SA",".ae":"AE",".qa":"QA",
    ".kw":"KW",".bh":"BH",".om":"OM",".jo":"JO",".lb":"LB",".iq":"IQ",
    ".ir":"IR",".il":"IL",".tr":"TR",".pk":"PK",".in":"IN",".cn":"CN",
    ".jp":"JP",".kr":"KR",".id":"ID",".vn":"VN",".th":"TH",".my":"MY",
    ".sg":"SG",".ph":"PH",".tw":"TW",".bd":"BD",".hk":"HK",".gb":"GB",
    ".uk":"GB",".de":"DE",".fr":"FR",".es":"ES",".it":"IT",".nl":"NL",
    ".se":"SE",".no":"NO",".dk":"DK",".fi":"FI",".ch":"CH",".at":"AT",
    ".be":"BE",".pt":"PT",".pl":"PL",".ua":"UA",".ru":"RU",".cz":"CZ",
    ".ro":"RO",".hu":"HU",".gr":"GR",".ie":"IE",".us":"US",".ca":"CA",
    ".br":"BR",".mx":"MX",".ar":"AR",".co":"CO",".cl":"CL",".pe":"PE",
    ".au":"AU",".nz":"NZ",
}

# Email providers whose TLD is meaningless for country inference
GENERIC_PROVIDERS = {
    "gmail.com","googlemail.com","yahoo.com","hotmail.com","outlook.com",
    "live.com","icloud.com","me.com","mac.com","aol.com","protonmail.com",
    "proton.me","pm.me","mail.com","gmx.com","gmx.net","fastmail.com",
    "zoho.com","yandex.com","ymail.com","rocketmail.com","inbox.com",
    "msn.com","users.noreply.github.com","noreply.github.com","example.com",
}


def tld_to_iso(email_or_domain: str) -> str | None:
    if not email_or_domain:
        return None
    s = email_or_domain.strip().lower()
    if "@" in s:
        s = s.rsplit("@", 1)[-1]
    if s in GENERIC_PROVIDERS:
        return None
    for tld, iso in TLD_TO_ISO.items():
        if s.endswith(tld):
            return iso
    return None


def load_unresolved_owners(main_csv: Path) -> list[str]:
    """Owners where country_iso is blank in the integrated CSV, deduped."""
    seen: set[str] = set()
    with main_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            iso = (r.get("country_iso") or "").strip()
            if iso:
                continue
            ol = (r.get("owner_login") or "").strip()
            if ol and ol not in seen:
                seen.add(ol)
    return sorted(seen)


def load_cache() -> dict:
    if OUT_CACHE.exists():
        return json.loads(OUT_CACHE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    OUT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUT_CACHE)


def npm_search_maintainer(session: requests.Session, login: str) -> list[str]:
    """Return up to 5 package names where <login> is a listed maintainer."""
    params = {"text": f"maintainer:{login}", "size": 5}
    try:
        r = session.get(NPM_SEARCH, params=params, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json() or {}
        return [obj.get("package", {}).get("name") for obj in (data.get("objects") or []) if obj.get("package", {}).get("name")]
    except Exception:
        return []


def npm_package_maintainers(session: requests.Session, pkg: str) -> list[dict]:
    """Return [{name, email}, ...] for a package's maintainers."""
    url = NPM_PKG.format(pkg=quote(pkg, safe="@/"))
    try:
        r = session.get(url, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json() or {}
        return data.get("maintainers") or []
    except Exception:
        return []


def resolve_owner(session: requests.Session, login: str, min_sleep: float) -> dict:
    """Return a resolution record (country_iso may be empty)."""
    out = {
        "owner_login": login,
        "package_name": "",
        "maintainer_email": "",
        "email_domain": "",
        "country_iso": "",
        "source": "",
    }

    pkgs = npm_search_maintainer(session, login)
    time.sleep(min_sleep)
    if not pkgs:
        return out

    for pkg in pkgs:
        maints = npm_package_maintainers(session, pkg)
        time.sleep(min_sleep)
        for m in maints:
            name = (m.get("name") or "").strip().lower()
            email = (m.get("email") or "").strip()
            if name == login.lower() and email:
                iso = tld_to_iso(email)
                out["package_name"] = pkg
                out["maintainer_email"] = email
                out["email_domain"] = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
                if iso:
                    out["country_iso"] = iso
                    out["source"] = "npm_maintainer_email_tld"
                    return out
    # Found an npm identity but no country-mappable email
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cap owners processed (0 = all)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--min-sleep", type=float, default=0.05)
    ap.add_argument("--flush-every", type=int, default=250)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading unresolved owners...")
    owners = load_unresolved_owners(MAIN)
    print(f"  {len(owners)} unresolved owners in integrated CSV")

    cache = load_cache()
    print(f"  {len(cache)} already cached from previous run")

    todo = [o for o in owners if o not in cache]
    if args.limit > 0:
        todo = todo[:args.limit]
    print(f"  {len(todo)} to process this run")

    if not todo:
        print("Nothing to do.")
        return _write_csv(cache)

    session = requests.Session()
    session.headers["User-Agent"] = "e2e-tool stage2e npm author join (research)"

    processed = 0
    with_match = 0
    with_iso   = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(resolve_owner, session, o, args.min_sleep): o for o in todo}
        for fut in as_completed(futs):
            owner = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"owner_login": owner, "error": str(e)}
            cache[owner] = rec
            processed += 1
            if rec.get("package_name"): with_match += 1
            if rec.get("country_iso"):  with_iso += 1

            if processed % args.flush_every == 0:
                save_cache(cache)
                dt = time.time() - t0
                rate = processed / dt if dt > 0 else 0
                print(f"  {processed:>5}/{len(todo)}  npm_match={with_match}  country={with_iso}  rate={rate:.1f}/s")

    save_cache(cache)
    print(f"\nRun complete: processed={processed} npm_match={with_match} country_resolved={with_iso}")
    return _write_csv(cache)


def _write_csv(cache: dict) -> int:
    """Write the per-owner resolution table, plus a summary."""
    fields = ["owner_login", "package_name", "maintainer_email", "email_domain",
              "country_iso", "source"]
    n_total = len(cache)
    n_pkg   = 0
    n_iso   = 0
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for owner, rec in sorted(cache.items()):
            if rec.get("package_name"): n_pkg += 1
            if rec.get("country_iso"):  n_iso += 1
            w.writerow({k: rec.get(k, "") for k in fields})
    print(f"\nWrote {OUT_CSV}")
    print(f"  owners in cache:            {n_total}")
    print(f"  with npm maintainer match:  {n_pkg} ({100*n_pkg/n_total:.1f}% of cache)")
    print(f"  with country-mappable TLD:  {n_iso} ({100*n_iso/n_total:.1f}% of cache)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
