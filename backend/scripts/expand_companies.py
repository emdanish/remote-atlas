"""Expand companies.yaml from hire-signal catalog + probed boards."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HIRE_PATH = Path(
    r"C:\Users\Danish\.cursor\projects\d-GitHub-remote-atlas\agent-tools\e9ba2a41-2f7a-4639-ad32-01f86cdd6e0e.txt"
)

CAREER = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "workable": "https://apply.workable.com/{slug}/",
}

EXTRA_OK = [
    ("greenhouse", "airtable", "Airtable", "https://airtable.com"),
    ("greenhouse", "clickhouse", "ClickHouse", "https://clickhouse.com"),
    ("greenhouse", "cockroachlabs", "Cockroach Labs", "https://www.cockroachlabs.com"),
    ("greenhouse", "databricks", "Databricks", "https://www.databricks.com"),
    ("greenhouse", "elastic", "Elastic", "https://www.elastic.co"),
    ("greenhouse", "fireblocks", "Fireblocks", "https://www.fireblocks.com"),
    ("greenhouse", "formlabs", "Formlabs", "https://formlabs.com"),
    ("greenhouse", "intercom", "Intercom", "https://www.intercom.com"),
    ("greenhouse", "kalshi", "Kalshi", "https://kalshi.com"),
    ("greenhouse", "mongodb", "MongoDB", "https://www.mongodb.com"),
    ("greenhouse", "okta", "Okta", "https://www.okta.com"),
    ("greenhouse", "pagerduty", "PagerDuty", "https://www.pagerduty.com"),
    ("greenhouse", "postman", "Postman", "https://www.postman.com"),
    ("greenhouse", "roblox", "Roblox", "https://www.roblox.com"),
    ("greenhouse", "spacex", "SpaceX", "https://www.spacex.com"),
    ("greenhouse", "twilio", "Twilio", "https://www.twilio.com"),
    ("greenhouse", "typeform", "Typeform", "https://www.typeform.com"),
    ("greenhouse", "chime", "Chime", "https://www.chime.com"),
    ("greenhouse", "sofi", "SoFi", "https://www.sofi.com"),
    ("greenhouse", "monzo", "Monzo", "https://monzo.com"),
    ("greenhouse", "gongio", "Gong", "https://www.gong.io"),
    ("ashby", "perplexity", "Perplexity", "https://www.perplexity.ai"),
    ("ashby", "sentry", "Sentry", "https://sentry.io"),
    ("ashby", "exa", "Exa", "https://exa.ai"),
    ("ashby", "warp", "Warp", "https://www.warp.dev"),
    ("ashby", "browserbase", "Browserbase", "https://www.browserbase.com"),
    ("ashby", "buffer", "Buffer", "https://buffer.com"),
    ("lever", "spotify", "Spotify", "https://www.spotify.com"),
    ("lever", "activecampaign", "ActiveCampaign", "https://www.activecampaign.com"),
]


def main() -> None:
    hire = json.loads(HIRE_PATH.read_text(encoding="utf-8"))
    existing = yaml.safe_load((ROOT / "data" / "companies.yaml").read_text(encoding="utf-8"))["companies"]
    by_key: dict[tuple[str, str], dict] = {}
    for c in existing:
        by_key[(c.get("ats_type"), c.get("ats_slug"))] = c

    priority_sectors = {
        "ai",
        "infra",
        "infrastructure",
        "developer-tools",
        "devtools",
        "saas",
        "fintech",
        "security",
        "data",
        "crypto",
        "consumer",
    }
    hire_sorted = sorted(
        hire,
        key=lambda c: (0 if (c.get("sector") or "") in priority_sectors else 1, c.get("name") or ""),
    )
    added = 0
    for c in hire_sorted:
        src = c.get("source")
        slug = c.get("id")
        name = c.get("name")
        if not src or not slug or not name or src not in CAREER:
            continue
        key = (src, slug)
        if key in by_key:
            by_key[key]["is_enabled"] = True
            continue
        by_key[key] = {
            "name": name,
            "website": f"https://{slug.replace('_', '-')}.com",
            "ats_type": src,
            "ats_slug": slug,
            "career_page_url": CAREER[src].format(slug=slug),
            "region_focus": "global",
            "is_enabled": True,
        }
        added += 1
        if added >= 200:
            break

    for ats, slug, name, website in EXTRA_OK:
        by_key[(ats, slug)] = {
            "name": name,
            "website": website,
            "ats_type": ats,
            "ats_slug": slug,
            "career_page_url": CAREER[ats].format(slug=slug),
            "region_focus": "global",
            "is_enabled": True,
        }

    for name, ats, slug, website in [
        ("Motive", "greenhouse", "motive", "https://gomotive.com"),
        ("Careem", "greenhouse", "careem", "https://www.careem.com"),
    ]:
        by_key[(ats, slug)] = {
            "name": name,
            "website": website,
            "ats_type": ats,
            "ats_slug": slug,
            "career_page_url": CAREER[ats].format(slug=slug),
            "region_focus": "both",
            "is_enabled": True,
        }

    companies = sorted(by_key.values(), key=lambda c: (c["ats_type"], c["name"].lower()))
    enabled = sum(1 for c in companies if c.get("is_enabled"))
    (ROOT / "data" / "companies.yaml").write_text(
        yaml.safe_dump({"companies": companies}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"companies={len(companies)} enabled={enabled} newly_added_from_hire={added}")


if __name__ == "__main__":
    main()
