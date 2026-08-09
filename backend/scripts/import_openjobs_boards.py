"""Import verified ATS boards from OpenJobs dataset + live probe.

Only enables boards that return structured job JSON/XML with >=1 opening.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "data" / "companies.yaml"
OPENJOBS = ROOT / "data" / "openjobs_companies.json"

CAREER = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{slug}",
    "recruitee": "https://{slug}.recruitee.com",
    "personio": "https://{slug}.jobs.personio.de",
    "teamtailor": "https://{slug}.teamtailor.com",
    "workable": "https://apply.workable.com/{slug}/",
    "breezy": "https://{slug}.breezy.hr",
    "bamboohr": "https://{slug}.bamboohr.com/careers",
}

# Extra Pakistani / regional tech targets to probe even if absent from OpenJobs
PK_EXTRA: list[tuple[str, str, str, str]] = [
    ("greenhouse", "careem", "Careem", "https://www.careem.com"),
    ("greenhouse", "motive", "Motive", "https://gomotive.com"),
    ("greenhouse", "gomotive", "Motive", "https://gomotive.com"),
    ("greenhouse", "afiniti", "Afiniti", "https://www.afiniti.com"),
    ("greenhouse", "spglobal", "S&P Global", "https://www.spglobal.com"),
    ("greenhouse", "educative", "Educative", "https://www.educative.io"),
    ("greenhouse", "veeamsoftware", "Veeam / Securiti", "https://www.veeam.com"),
    ("greenhouse", "beyondone", "Beyond ONE", "https://beyond.one"),
    ("ashby", "educative", "Educative", "https://www.educative.io"),
    ("smartrecruiters", "SystemsLimited", "Systems Limited", "https://www.systemsltd.com"),
    ("breezy", "10pearls", "10Pearls", "https://10pearls.com"),
    ("personio", "personio", "Personio", "https://www.personio.com"),
    ("lever", "venturedive", "VentureDive", "https://venturedive.com"),
    ("greenhouse", "confiz", "Confiz", "https://www.confiz.com"),
    ("greenhouse", "tintash", "Tintash", "https://www.tintash.com"),
    ("greenhouse", "folio3", "Folio3", "https://www.folio3.com"),
    ("bamboohr", "10pearls", "10Pearls", "https://10pearls.com"),
]

PK_SLUGS = {
    "careem",
    "motive",
    "gomotive",
    "afiniti",
    "spglobal",
    "educative",
    "systemslimited",
    "10pearls",
    "bazaar",
    "bykea",
    "daraz",
    "jazz",
    "jazzcash",
    "keenu",
    "securiti",
    "veeamsoftware",
    "beyondone",
    "venturedive",
    "confiz",
    "tintash",
    "folio3",
    "arbisoft",
    "emumba",
    "cubix",
    "teradata",
    "ibex",
    "retailo",
    "breathehr",
}


EXTRACTORS = [
    ("greenhouse", re.compile(r"boards(?:-api)?\.greenhouse\.io/(?:embed/job_board/js\?for=)?([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"job-boards(?:\.eu)?\.greenhouse\.io/([A-Za-z0-9_-]+)", re.I)),
    ("greenhouse", re.compile(r"https?://([A-Za-z0-9_-]+)\.greenhouse\.io", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([A-Za-z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)", re.I)),
    ("recruitee", re.compile(r"https?://([A-Za-z0-9_-]+)\.recruitee\.com", re.I)),
    ("personio", re.compile(r"https?://([A-Za-z0-9_-]+)\.jobs\.personio\.(?:de|com)", re.I)),
    ("teamtailor", re.compile(r"https?://([A-Za-z0-9_-]+)\.teamtailor\.com", re.I)),
    ("breezy", re.compile(r"https?://([A-Za-z0-9_-]+)\.breezy\.hr", re.I)),
    ("bamboohr", re.compile(r"https?://([A-Za-z0-9_-]+)\.bamboohr\.com", re.I)),
]

SKIP_SLUGS = {
    "www",
    "jobs",
    "careers",
    "boards",
    "api",
    "embed",
    "en-us",
    "job-boards",
    "apply",
}


def extract(url: str) -> tuple[str, str] | None:
    for ats, pat in EXTRACTORS:
        m = pat.search(url or "")
        if not m:
            continue
        slug = m.group(1)
        if slug.lower() in SKIP_SLUGS:
            continue
        return ats, slug
    return None


def probe_url(ats: str, slug: str) -> str:
    if ats == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    if ats == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    if ats == "lever":
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"
    if ats == "smartrecruiters":
        return f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=10"
    if ats == "workable":
        return f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    if ats == "recruitee":
        return f"https://{slug}.recruitee.com/api/offers/"
    if ats == "personio":
        return f"https://{slug}.jobs.personio.de/xml"
    if ats == "teamtailor":
        return f"https://{slug}.teamtailor.com/jobs.json"
    if ats == "breezy":
        return f"https://{slug}.breezy.hr/json"
    if ats == "bamboohr":
        return f"https://{slug}.bamboohr.com/careers/list"
    raise ValueError(ats)


def count_jobs(ats: str, resp: httpx.Response) -> int:
    if resp.status_code != 200:
        return 0
    text = resp.text or ""
    if ats == "personio":
        return text.lower().count("<position")
    if ats == "bamboohr":
        ctype = (resp.headers.get("content-type") or "").lower()
        if "json" not in ctype:
            return 0
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return 0
    if ats == "greenhouse":
        return len((data or {}).get("jobs") or [])
    if ats == "ashby":
        return len((data or {}).get("jobs") or [])
    if ats == "lever":
        return len(data) if isinstance(data, list) else 0
    if ats == "smartrecruiters":
        return int((data or {}).get("totalFound") or len((data or {}).get("content") or []))
    if ats == "workable":
        return len((data or {}).get("jobs") or [])
    if ats == "recruitee":
        return len((data or {}).get("offers") or [])
    if ats == "teamtailor":
        return len((data or {}).get("items") or [])
    if ats == "breezy":
        return len(data) if isinstance(data, list) else 0
    if ats == "bamboohr":
        return int((data or {}).get("meta", {}).get("totalCount") or len((data or {}).get("result") or []))
    return 0


async def live_ok(client: httpx.AsyncClient, ats: str, slug: str) -> int:
    try:
        r = await client.get(probe_url(ats, slug))
        if ats == "personio" and r.status_code == 404:
            r = await client.get(f"https://{slug}.jobs.personio.com/xml")
        return count_jobs(ats, r)
    except Exception:  # noqa: BLE001
        return 0


def load_candidates() -> dict[tuple[str, str], tuple[str, str]]:
    """(ats, slug_lower) -> (display_name, website_hint)"""
    out: dict[tuple[str, str], tuple[str, str]] = {}
    if OPENJOBS.exists():
        data = json.loads(OPENJOBS.read_text(encoding="utf-8"))
        for c in data:
            name = (c.get("name") or "").strip() or "Unknown"
            website = (c.get("website") or "").strip() or None
            for u in (c.get("ats_links") or []) + (c.get("list_urls") or []):
                hit = extract(u)
                if not hit:
                    continue
                ats, slug = hit
                key = (ats, slug.lower())
                out.setdefault(key, (name, website or ""))
    for ats, slug, name, website in PK_EXTRA:
        out[(ats, slug.lower())] = (name, website)
    return out


async def main() -> None:
    raw = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
    if isinstance(raw, list):
        existing = raw
        wrap = False
    else:
        existing = raw.get("companies") or []
        wrap = True
    by_key = {(r.get("ats_type"), (r.get("ats_slug") or "").lower()): r for r in existing}

    candidates = load_candidates()
    print(f"Candidates to probe: {len(candidates)}")

    sem = asyncio.Semaphore(24)
    results: list[tuple[str, str, str, str, int]] = []

    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": "RemoteAtlas/1.0 (+https://github.com/remote-atlas)"},
    ) as client:

        async def one(ats: str, slug: str, name: str, website: str):
            async with sem:
                n = await live_ok(client, ats, slug)
                if n > 0:
                    results.append((ats, slug, name, website, n))
                    print(f"OK {ats} {slug} {n}")

        await asyncio.gather(
            *(one(ats, slug, name, website) for (ats, slug), (name, website) in candidates.items())
        )

    added = 0
    for ats, slug, name, website, n in results:
        key = (ats, slug.lower())
        region = "both" if slug.lower() in PK_SLUGS else "global"
        career = CAREER[ats].format(slug=slug)
        if key in by_key:
            row = by_key[key]
            row["is_enabled"] = True
            if slug.lower() in PK_SLUGS:
                row["region_focus"] = "both"
            continue
        existing.append(
            {
                "name": name,
                "website": website or None,
                "career_page_url": career,
                "ats_type": ats,
                "ats_slug": slug,
                "region_focus": region,
                "is_enabled": True,
            }
        )
        by_key[key] = existing[-1]
        added += 1

    payload = {"companies": existing} if wrap else existing
    YAML_PATH.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    enabled = sum(1 for r in existing if r.get("is_enabled", True))
    pk = sum(1 for r in existing if r.get("region_focus") in ("pakistan", "both"))
    print(f"LIVE_OK {len(results)} ADDED {added} TOTAL {len(existing)} ENABLED {enabled} PK {pk}")


if __name__ == "__main__":
    asyncio.run(main())
