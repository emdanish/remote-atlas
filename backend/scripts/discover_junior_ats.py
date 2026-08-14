"""Discover junior-hiring ATS slugs from public GitHub URL indexes.

cvrve/New-Grad listings.json is MIT. We extract Greenhouse/Lever/Ashby slugs
and official apply hosts only — we do not ingest listing JSON as job records.

Simplify / Pitt CSC lists have no LICENSE in-repo; do not scrape simplify.jobs
and do not copy their JSON into our jobs table.
"""

from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "data" / "companies.yaml"

CVRVE_LISTINGS = (
    "https://raw.githubusercontent.com/cvrve/New-Grad/main/.github/scripts/listings.json"
)

CAREER = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
}

_GH = re.compile(
    r"(?:job-boards|boards)\.greenhouse\.io/([a-zA-Z0-9_-]+)",
    re.I,
)
_LEVER = re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)", re.I)
_ASHBY = re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)", re.I)


def _slug_from_url(url: str) -> tuple[str, str] | None:
    raw = (url or "").strip()
    if not raw:
        return None
    m = _GH.search(raw)
    if m:
        return "greenhouse", m.group(1).lower()
    m = _LEVER.search(raw)
    if m:
        return "lever", m.group(1).lower()
    m = _ASHBY.search(raw)
    if m:
        return "ashby", m.group(1).lower()
    host = urlparse(raw).netloc.lower()
    if "greenhouse.io" in host:
        parts = [p for p in urlparse(raw).path.split("/") if p]
        if parts:
            return "greenhouse", parts[0].lower()
    return None


def extract_boards(listings: list) -> dict[tuple[str, str], dict]:
    found: dict[tuple[str, str], dict] = {}
    for item in listings:
        if not isinstance(item, dict):
            continue
        url = (
            item.get("url")
            or item.get("application_url")
            or item.get("apply_url")
            or ""
        )
        parsed = _slug_from_url(str(url))
        if not parsed:
            continue
        ats, slug = parsed
        name = (item.get("company_name") or item.get("company") or slug).strip()
        found[(ats, slug)] = {
            "name": name,
            "website": item.get("company_url") or item.get("source") or None,
            "ats_type": ats,
            "ats_slug": slug,
            "career_page_url": CAREER[ats].format(slug=slug),
            "region_focus": "global",
            "is_enabled": True,
            "hires_juniors": True,
        }
    return found


async def probe_one(client: httpx.AsyncClient, ats: str, slug: str) -> bool:
    try:
        if ats == "greenhouse":
            r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
            return r.status_code == 200 and bool((r.json() or {}).get("jobs"))
        if ats == "lever":
            r = await client.get(
                f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}
            )
            data = r.json() if r.status_code == 200 else []
            return r.status_code == 200 and isinstance(data, list) and len(data) > 0
        if ats == "ashby":
            r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            return r.status_code == 200 and bool((r.json() or {}).get("jobs"))
    except Exception:  # noqa: BLE001
        return False
    return False


async def main() -> None:
    parser = argparse.ArgumentParser(description="Discover junior ATS slugs (not job ingest).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=80, help="Max new boards to probe")
    args = parser.parse_args()

    headers = {"User-Agent": "RemoteAtlas/0.1 (+junior-ats-discovery)", "Accept": "application/json"}
    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(CVRVE_LISTINGS)
        if resp.status_code != 200:
            print(f"FAIL fetch listings {resp.status_code}")
            return
        payload = resp.json()
        listings = payload if isinstance(payload, list) else payload.get("listings") or []
        discovered = extract_boards(listings)

    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
    companies: list[dict] = data.get("companies") or []
    by_key: dict[tuple[str, str], dict] = {
        (c.get("ats_type"), c.get("ats_slug")): c for c in companies if c.get("ats_slug")
    }

    new_keys = [k for k in discovered if k not in by_key][: args.limit]
    existing_hits = [k for k in discovered if k in by_key]
    for key in existing_hits:
        by_key[key]["hires_juniors"] = True

    print(f"DISCOVERED {len(discovered)} EXISTING_FLAGGED {len(existing_hits)} NEW_CANDIDATES {len(new_keys)}")
    if args.dry_run:
        for ats, slug in new_keys[:30]:
            print(f"CANDIDATE {ats} {slug}")
        return

    headers = {"User-Agent": "RemoteAtlas/0.1 (+company-probe)", "Accept": "application/json"}
    sem = asyncio.Semaphore(10)
    added = 0
    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:

        async def run(key: tuple[str, str]) -> None:
            nonlocal added
            ats, slug = key
            async with sem:
                alive = await probe_one(client, ats, slug)
            if not alive:
                print(f"SKIP {ats} {slug}")
                return
            by_key[key] = discovered[key]
            added += 1
            print(f"OK new {ats} {slug}")

        await asyncio.gather(*(run(k) for k in new_keys))

    merged = sorted(by_key.values(), key=lambda c: (c.get("ats_type") or "", c.get("name") or ""))
    YAML_PATH.write_text(
        yaml.safe_dump({"companies": merged}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    juniors = sum(1 for c in merged if c.get("hires_juniors"))
    print(f"WROTE {len(merged)} HIRES_JUNIORS {juniors} ADDED {added}")


if __name__ == "__main__":
    asyncio.run(main())
