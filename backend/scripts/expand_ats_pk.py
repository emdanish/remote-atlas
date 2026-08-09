"""Probe & merge additional ATS boards (PK + SmartRecruiters + Recruitee + extras)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "data" / "companies.yaml"

CAREER = {
    "greenhouse": "https://boards.greenhouse.io/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "workable": "https://apply.workable.com/{slug}/",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{slug}",
    "recruitee": "https://{slug}.recruitee.com",
}

# Pakistani / PK-hiring companies to probe across ATS types
PK_PROBES: list[tuple[str, str, str, str]] = [
    # (ats_type, slug, name, website)
    ("greenhouse", "careem", "Careem", "https://www.careem.com"),
    ("greenhouse", "gomotive", "Motive", "https://gomotive.com"),
    ("greenhouse", "motive", "Motive", "https://gomotive.com"),
    ("greenhouse", "afiniti", "Afiniti", "https://www.afiniti.com"),
    ("greenhouse", "spglobal", "S&P Global", "https://www.spglobal.com"),
    ("greenhouse", "securiti", "Securiti", "https://securiti.ai"),
    ("greenhouse", "educative", "Educative", "https://www.educative.io"),
    ("greenhouse", "bazaartechnologies", "Bazaar Technologies", "https://bazaar.tech"),
    ("greenhouse", "bazaar", "Bazaar Technologies", "https://bazaar.tech"),
    ("greenhouse", "systemsltd", "Systems Limited", "https://www.systemsltd.com"),
    ("greenhouse", "systemslimited", "Systems Limited", "https://www.systemsltd.com"),
    ("greenhouse", "arbisoft", "Arbisoft", "https://arbisoft.com"),
    ("greenhouse", "10pearls", "10Pearls", "https://10pearls.com"),
    ("greenhouse", "netsol", "NETSOL", "https://www.netsoltech.com"),
    ("greenhouse", "netsoltechnologies", "NETSOL", "https://www.netsoltech.com"),
    ("greenhouse", "contoursoftware", "Contour Software", "https://www.contour-software.com"),
    ("greenhouse", "venturedive", "VentureDive", "https://venturedive.com"),
    ("greenhouse", "folio3", "Folio3", "https://folio3.com"),
    ("greenhouse", "confiz", "Confiz", "https://www.confiz.com"),
    ("greenhouse", "devsinc", "Devsinc", "https://devsinc.com"),
    ("greenhouse", "i2c", "i2c", "https://www.i2cinc.com"),
    ("greenhouse", "i2cinc", "i2c", "https://www.i2cinc.com"),
    ("greenhouse", "techlogix", "Techlogix", "https://www.techlogix.com"),
    ("greenhouse", "curemd", "CureMD", "https://www.curemd.com"),
    ("greenhouse", "tkxel", "Tkxel", "https://www.tkxel.com"),
    ("greenhouse", "cubix", "Cubix", "https://www.cubix.co"),
    ("ashby", "securiti", "Securiti", "https://securiti.ai"),
    ("ashby", "educative", "Educative", "https://www.educative.io"),
    ("ashby", "careem", "Careem", "https://www.careem.com"),
    ("lever", "careem", "Careem", "https://www.careem.com"),
    ("lever", "afiniti", "Afiniti", "https://www.afiniti.com"),
    ("smartrecruiters", "SystemsLimited", "Systems Limited", "https://www.systemsltd.com"),
    ("smartrecruiters", "Careem", "Careem", "https://www.careem.com"),
    ("smartrecruiters", "NETSOL", "NETSOL", "https://www.netsoltech.com"),
    ("recruitee", "arbisoft", "Arbisoft", "https://arbisoft.com"),
    ("recruitee", "10pearls", "10Pearls", "https://10pearls.com"),
    ("recruitee", "venturedive", "VentureDive", "https://venturedive.com"),
    ("recruitee", "folio3", "Folio3", "https://folio3.com"),
]

# Global SmartRecruiters / Recruitee tech boards (common public slugs)
GLOBAL_EXTRA: list[tuple[str, str, str, str]] = [
    ("smartrecruiters", "Visa", "Visa", "https://www.visa.com"),
    ("smartrecruiters", "Siemens", "Siemens", "https://www.siemens.com"),
    ("smartrecruiters", "SchneiderElectric", "Schneider Electric", "https://www.se.com"),
    ("smartrecruiters", "Autodesk", "Autodesk", "https://www.autodesk.com"),
    ("smartrecruiters", "ElectronicArts", "Electronic Arts", "https://www.ea.com"),
    ("smartrecruiters", "Uber", "Uber", "https://www.uber.com"),
    ("smartrecruiters", "Deliveroo", "Deliveroo", "https://deliveroo.co.uk"),
    ("smartrecruiters", "Bookingcom", "Booking.com", "https://www.booking.com"),
    ("smartrecruiters", "Spotify", "Spotify", "https://www.spotify.com"),
    ("smartrecruiters", "Klarna", "Klarna", "https://www.klarna.com"),
    ("smartrecruiters", "N26", "N26", "https://n26.com"),
    ("smartrecruiters", "Revolut", "Revolut", "https://www.revolut.com"),
    ("smartrecruiters", "Miro", "Miro", "https://miro.com"),
    ("smartrecruiters", "Elastic", "Elastic", "https://www.elastic.co"),
    ("smartrecruiters", "GitLab", "GitLab", "https://about.gitlab.com"),
    ("smartrecruiters", "HashiCorp", "HashiCorp", "https://www.hashicorp.com"),
    ("smartrecruiters", "Datadog", "Datadog", "https://www.datadoghq.com"),
    ("smartrecruiters", "Snowflake", "Snowflake", "https://www.snowflake.com"),
    ("smartrecruiters", "CrowdStrike", "CrowdStrike", "https://www.crowdstrike.com"),
    ("smartrecruiters", "Okta", "Okta", "https://www.okta.com"),
    ("smartrecruiters", "Twilio", "Twilio", "https://www.twilio.com"),
    ("smartrecruiters", "Shopify", "Shopify", "https://www.shopify.com"),
    ("smartrecruiters", "Adobe", "Adobe", "https://www.adobe.com"),
    ("smartrecruiters", "Nvidia", "NVIDIA", "https://www.nvidia.com"),
    ("smartrecruiters", "Intel", "Intel", "https://www.intel.com"),
    ("smartrecruiters", "AMD", "AMD", "https://www.amd.com"),
    ("smartrecruiters", "Qualcomm", "Qualcomm", "https://www.qualcomm.com"),
    ("smartrecruiters", "SAP", "SAP", "https://www.sap.com"),
    ("smartrecruiters", "Oracle", "Oracle", "https://www.oracle.com"),
    ("smartrecruiters", "Capgemini", "Capgemini", "https://www.capgemini.com"),
    ("smartrecruiters", "Accenture", "Accenture", "https://www.accenture.com"),
    ("smartrecruiters", "EPAM", "EPAM", "https://www.epam.com"),
    ("smartrecruiters", "Thoughtworks", "Thoughtworks", "https://www.thoughtworks.com"),
    ("smartrecruiters", "Zendesk", "Zendesk", "https://www.zendesk.com"),
    ("smartrecruiters", "Atlassian", "Atlassian", "https://www.atlassian.com"),
    ("smartrecruiters", "Canva", "Canva", "https://www.canva.com"),
    ("smartrecruiters", "Figma", "Figma", "https://www.figma.com"),
    ("smartrecruiters", "Notion", "Notion", "https://www.notion.so"),
    ("smartrecruiters", "Airtable", "Airtable", "https://airtable.com"),
    ("smartrecruiters", "Asana", "Asana", "https://asana.com"),
    ("smartrecruiters", "Dropbox", "Dropbox", "https://www.dropbox.com"),
    ("smartrecruiters", "Box", "Box", "https://www.box.com"),
    ("smartrecruiters", "Pinterest", "Pinterest", "https://www.pinterest.com"),
    ("smartrecruiters", "Reddit", "Reddit", "https://www.reddit.com"),
    ("smartrecruiters", "Roblox", "Roblox", "https://www.roblox.com"),
    ("smartrecruiters", "Unity", "Unity", "https://unity.com"),
    ("smartrecruiters", "EpicGames", "Epic Games", "https://www.epicgames.com"),
    ("recruitee", "miro", "Miro", "https://miro.com"),
    ("recruitee", "n26", "N26", "https://n26.com"),
    ("recruitee", "klarna", "Klarna", "https://www.klarna.com"),
    ("recruitee", "typeform", "Typeform", "https://www.typeform.com"),
    ("recruitee", "personio", "Personio", "https://www.personio.com"),
    ("recruitee", "contentful", "Contentful", "https://www.contentful.com"),
    ("recruitee", "sumup", "SumUp", "https://sumup.com"),
    ("recruitee", "getyourguide", "GetYourGuide", "https://www.getyourguide.com"),
    ("recruitee", "deliveryhero", "Delivery Hero", "https://www.deliveryhero.com"),
    ("recruitee", "hellofresh", "HelloFresh", "https://www.hellofresh.com"),
    ("recruitee", "zalando", "Zalando", "https://www.zalando.com"),
    ("recruitee", "bol", "bol.com", "https://www.bol.com"),
    ("recruitee", "coolblue", "Coolblue", "https://www.coolblue.nl"),
    ("recruitee", "tomtom", "TomTom", "https://www.tomtom.com"),
    ("recruitee", "booking", "Booking.com", "https://www.booking.com"),
    ("recruitee", "adyen", "Adyen", "https://www.adyen.com"),
    ("recruitee", "mollie", "Mollie", "https://www.mollie.com"),
    ("recruitee", "messagebird", "MessageBird", "https://messagebird.com"),
    ("recruitee", "picnic", "Picnic", "https://picnic.app"),
    ("recruitee", "bunq", "bunq", "https://www.bunq.com"),
    ("recruitee", "backbase", "Backbase", "https://www.backbase.com"),
    ("recruitee", "mollie", "Mollie", "https://www.mollie.com"),
    ("greenhouse", "anthropic", "Anthropic", "https://www.anthropic.com"),
    ("greenhouse", "openai", "OpenAI", "https://openai.com"),
    ("greenhouse", "deepmind", "Google DeepMind", "https://deepmind.google"),
    ("greenhouse", "scaleai", "Scale AI", "https://scale.com"),
    ("greenhouse", "huggingface", "Hugging Face", "https://huggingface.co"),
    ("greenhouse", "cohere", "Cohere", "https://cohere.com"),
    ("greenhouse", "togetherai", "Together AI", "https://www.together.ai"),
    ("greenhouse", "replicate", "Replicate", "https://replicate.com"),
    ("greenhouse", "vercel", "Vercel", "https://vercel.com"),
    ("greenhouse", "supabase", "Supabase", "https://supabase.com"),
    ("ashby", "openai", "OpenAI", "https://openai.com"),
    ("ashby", "anthropic", "Anthropic", "https://www.anthropic.com"),
    ("ashby", "vercel", "Vercel", "https://vercel.com"),
    ("ashby", "supabase", "Supabase", "https://supabase.com"),
    ("ashby", "linear", "Linear", "https://linear.app"),
    ("ashby", "notion", "Notion", "https://www.notion.so"),
    ("ashby", "ramp", "Ramp", "https://ramp.com"),
    ("ashby", "cursor", "Cursor", "https://cursor.com"),
    ("lever", "netflix", "Netflix", "https://jobs.netflix.com"),
    ("lever", "palantir", "Palantir", "https://www.palantir.com"),
]

PK_NAMES = {
    "careem",
    "motive",
    "gomotive",
    "afiniti",
    "securiti",
    "educative",
    "bazaar",
    "bazaartechnologies",
    "systemsltd",
    "systemslimited",
    "systems limited",
    "arbisoft",
    "10pearls",
    "netsol",
    "netsoltechnologies",
    "contoursoftware",
    "contour software",
    "venturedive",
    "folio3",
    "confiz",
    "devsinc",
    "i2c",
    "i2cinc",
    "techlogix",
    "curemd",
    "tkxel",
    "cubix",
    "s&p global",
    "spglobal",
}


async def probe_one(client: httpx.AsyncClient, ats: str, slug: str) -> tuple[bool, int]:
    try:
        if ats == "greenhouse":
            r = await client.get(
                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                params={"content": "false"},
            )
            if r.status_code != 200:
                return False, 0
            return True, len((r.json() or {}).get("jobs") or [])
        if ats == "lever":
            r = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
            if r.status_code != 200:
                return False, 0
            data = r.json()
            return True, len(data) if isinstance(data, list) else 0
        if ats == "ashby":
            r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            if r.status_code != 200:
                return False, 0
            return True, len((r.json() or {}).get("jobs") or [])
        if ats == "workable":
            r = await client.get(f"https://www.workable.com/api/accounts/{slug}")
            if r.status_code != 200:
                return False, 0
            return True, len((r.json() or {}).get("jobs") or [])
        if ats == "smartrecruiters":
            r = await client.get(
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                params={"limit": 10, "offset": 0},
            )
            if r.status_code != 200:
                return False, 0
            data = r.json() or {}
            return True, int(data.get("totalFound") or len(data.get("content") or []))
        if ats == "recruitee":
            r = await client.get(f"https://{slug}.recruitee.com/api/offers/")
            if r.status_code != 200:
                return False, 0
            return True, len((r.json() or {}).get("offers") or [])
    except Exception:  # noqa: BLE001
        return False, 0
    return False, 0


def region_for(name: str, slug: str) -> str:
    key = f"{name} {slug}".lower()
    if any(p in key for p in PK_NAMES):
        return "both"
    return "global"


async def main() -> None:
    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
    companies: list[dict] = data.get("companies") or []
    by_key: dict[tuple[str, str], dict] = {
        (c.get("ats_type"), c.get("ats_slug")): c for c in companies if c.get("ats_slug")
    }

    candidates = PK_PROBES + GLOBAL_EXTRA
    headers = {"User-Agent": "RemoteAtlas/0.1 (+company-probe)", "Accept": "application/json"}
    sem = asyncio.Semaphore(12)
    ok_new = 0
    ok_existing = 0

    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:

        async def run(item: tuple[str, str, str, str]) -> None:
            nonlocal ok_new, ok_existing
            ats, slug, name, website = item
            async with sem:
                await asyncio.sleep(0.05)
                alive, count = await probe_one(client, ats, slug)
            if not alive or count <= 0:
                print(f"SKIP {ats} {slug}")
                return
            key = (ats, slug)
            region = region_for(name, slug)
            if ats == "recruitee":
                career = CAREER[ats].format(slug=slug)
            else:
                career = CAREER[ats].format(slug=slug)
            if key in by_key:
                by_key[key]["is_enabled"] = True
                if region == "both":
                    by_key[key]["region_focus"] = "both"
                ok_existing += 1
                print(f"OK existing {ats} {slug} {count}")
                return
            by_key[key] = {
                "name": name,
                "website": website,
                "ats_type": ats,
                "ats_slug": slug,
                "career_page_url": career,
                "region_focus": region,
                "is_enabled": True,
            }
            ok_new += 1
            print(f"OK new {ats} {slug} {count}")

        await asyncio.gather(*(run(c) for c in candidates))

    # Fix known Motive slug preference
    if ("greenhouse", "gomotive") in by_key:
        by_key[("greenhouse", "gomotive")]["name"] = "Motive"
        by_key[("greenhouse", "gomotive")]["region_focus"] = "both"
        by_key[("greenhouse", "gomotive")]["is_enabled"] = True
        if ("greenhouse", "motive") in by_key and by_key[("greenhouse", "motive")].get("ats_slug") == "motive":
            # keep motive if it works; both can coexist
            by_key[("greenhouse", "motive")]["region_focus"] = "both"

    merged = sorted(by_key.values(), key=lambda c: (c.get("ats_type") or "", c.get("name") or ""))
    YAML_PATH.write_text(
        yaml.safe_dump({"companies": merged}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    enabled = sum(1 for c in merged if c.get("is_enabled"))
    pk = sum(1 for c in merged if c.get("region_focus") in {"pakistan", "both"})
    print(f"TOTAL {len(merged)} ENABLED {enabled} PK_FOCUS {pk} NEW {ok_new} UPDATED {ok_existing}")


if __name__ == "__main__":
    asyncio.run(main())
