"""Expand companies.yaml with Personio/Teamtailor/SmartRecruiters + more GH/Ashby + PK focus."""

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
    "smartrecruiters": "https://jobs.smartrecruiters.com/{slug}",
    "recruitee": "https://{slug}.recruitee.com",
    "personio": "https://{slug}.jobs.personio.de",
    "teamtailor": "https://{slug}.teamtailor.com",
    "workable": "https://apply.workable.com/{slug}/",
}

PK_BOTH = {
    "careem",
    "motive",
    "gomotive",
    "afiniti",
    "securiti",
    "educative",
    "spglobal",
    "bazaar",
}

CANDIDATES: list[tuple[str, str, str, str]] = [
    # PK / regional
    ("greenhouse", "gomotive", "Motive", "https://gomotive.com"),
    ("greenhouse", "careem", "Careem", "https://www.careem.com"),
    ("greenhouse", "afiniti", "Afiniti", "https://www.afiniti.com"),
    ("greenhouse", "securiti", "Securiti", "https://www.securiti.ai"),
    ("greenhouse", "educative", "Educative", "https://www.educative.io"),
    ("greenhouse", "spglobal", "S&P Global", "https://www.spglobal.com"),
    ("ashby", "securiti", "Securiti", "https://www.securiti.ai"),
    # Personio (EU tech — public XML)
    ("personio", "personio", "Personio", "https://www.personio.com"),
    ("personio", "getyourguide", "GetYourGuide", "https://www.getyourguide.com"),
    ("personio", "contentful", "Contentful", "https://www.contentful.com"),
    ("personio", "adjust", "Adjust", "https://www.adjust.com"),
    ("personio", "sumup", "SumUp", "https://sumup.com"),
    ("personio", "taxfix", "Taxfix", "https://www.taxfix.de"),
    ("personio", "trade-republic", "Trade Republic", "https://traderepublic.com"),
    ("personio", "traderepublic", "Trade Republic", "https://traderepublic.com"),
    ("personio", "n26", "N26", "https://n26.com"),
    ("personio", "flink", "Flink", "https://www.goflink.com"),
    ("personio", "gorillas", "Gorillas", "https://gorillas.io"),
    ("personio", "tier", "TIER", "https://www.tier.app"),
    ("personio", "celonis", "Celonis", "https://www.celonis.com"),
    ("personio", "deepl", "DeepL", "https://www.deepl.com"),
    ("personio", "statista", "Statista", "https://www.statista.com"),
    ("personio", "zalando", "Zalando", "https://www.zalando.com"),
    ("personio", "hellofresh", "HelloFresh", "https://www.hellofresh.com"),
    ("personio", "deliveryhero", "Delivery Hero", "https://www.deliveryhero.com"),
    ("personio", "auto1", "AUTO1", "https://www.auto1-group.com"),
    ("personio", "auto1-group", "AUTO1", "https://www.auto1-group.com"),
    ("personio", "wefox", "wefox", "https://www.wefox.com"),
    ("personio", "raisin", "Raisin", "https://www.raisin.com"),
    ("personio", "solarisbank", "Solaris", "https://www.solarisgroup.com"),
    ("personio", "enpal", "Enpal", "https://www.enpal.de"),
    ("personio", "aboutyou", "ABOUT YOU", "https://corporate.aboutyou.de"),
    ("personio", "home24", "Home24", "https://www.home24.com"),
    ("personio", "otto", "OTTO", "https://www.otto.de"),
    ("personio", "check24", "CHECK24", "https://www.check24.de"),
    ("personio", "idealo", "idealo", "https://www.idealo.de"),
    ("personio", "flaschenpost", "Flaschenpost", "https://www.flaschenpost.de"),
    ("personio", "bike-discount", "Bike Discount", "https://www.bike-discount.de"),
    # Teamtailor
    ("teamtailor", "templafy", "Templafy", "https://www.templafy.com"),
    ("teamtailor", "career", "Teamtailor", "https://www.teamtailor.com"),
    # More Greenhouse tech
    ("greenhouse", "stripe", "Stripe", "https://stripe.com"),
    ("greenhouse", "airbnb", "Airbnb", "https://airbnb.com"),
    ("greenhouse", "discord", "Discord", "https://discord.com"),
    ("greenhouse", "figma", "Figma", "https://figma.com"),
    ("greenhouse", "notion", "Notion", "https://notion.so"),
    ("greenhouse", "cloudflare", "Cloudflare", "https://cloudflare.com"),
    ("greenhouse", "datadog", "Datadog", "https://datadoghq.com"),
    ("greenhouse", "hashicorp", "HashiCorp", "https://hashicorp.com"),
    ("greenhouse", "gitlab", "GitLab", "https://gitlab.com"),
    ("greenhouse", "github", "GitHub", "https://github.com"),
    ("greenhouse", "reddit", "Reddit", "https://reddit.com"),
    ("greenhouse", "pinterest", "Pinterest", "https://pinterest.com"),
    ("greenhouse", "snapchat", "Snap", "https://snap.com"),
    ("greenhouse", "snap", "Snap", "https://snap.com"),
    ("greenhouse", "nvidia", "NVIDIA", "https://nvidia.com"),
    ("greenhouse", "amd", "AMD", "https://amd.com"),
    ("greenhouse", "intel", "Intel", "https://intel.com"),
    ("greenhouse", "qualcomm", "Qualcomm", "https://qualcomm.com"),
    ("greenhouse", "adobe", "Adobe", "https://adobe.com"),
    ("greenhouse", "salesforce", "Salesforce", "https://salesforce.com"),
    ("greenhouse", "servicenow", "ServiceNow", "https://servicenow.com"),
    ("greenhouse", "splunk", "Splunk", "https://splunk.com"),
    ("greenhouse", "duo", "Cisco Duo", "https://duo.com"),
    ("greenhouse", "duo_security", "Cisco Duo", "https://duo.com"),
    ("greenhouse", "anduril", "Anduril", "https://anduril.com"),
    ("greenhouse", "andurilindustries", "Anduril", "https://anduril.com"),
    ("greenhouse", "relativityspace", "Relativity Space", "https://relativityspace.com"),
    ("greenhouse", "rocketlab", "Rocket Lab", "https://rocketlabusa.com"),
    ("greenhouse", "jobber", "Jobber", "https://getjobber.com"),
    ("greenhouse", "wealthsimple", "Wealthsimple", "https://wealthsimple.com"),
    ("greenhouse", "shopify", "Shopify", "https://shopify.com"),
    ("greenhouse", "faire", "Faire", "https://faire.com"),
    ("greenhouse", "instacart", "Instacart", "https://instacart.com"),
    ("greenhouse", "doordash", "DoorDash", "https://doordash.com"),
    ("greenhouse", "uber", "Uber", "https://uber.com"),
    ("greenhouse", "lyft", "Lyft", "https://lyft.com"),
    ("greenhouse", "coinbase", "Coinbase", "https://coinbase.com"),
    ("greenhouse", "robinhood", "Robinhood", "https://robinhood.com"),
    ("greenhouse", "affirm", "Affirm", "https://affirm.com"),
    ("greenhouse", "brex", "Brex", "https://brex.com"),
    ("greenhouse", "rippling", "Rippling", "https://rippling.com"),
    ("greenhouse", "gusto", "Gusto", "https://gusto.com"),
    ("greenhouse", "deel", "Deel", "https://deel.com"),
    ("greenhouse", "remotecom", "Remote", "https://remote.com"),
    ("greenhouse", "oysterhr", "Oyster", "https://oysterhr.com"),
    ("greenhouse", "lattice", "Lattice", "https://lattice.com"),
    ("greenhouse", "cultureamp", "Culture Amp", "https://cultureamp.com"),
    ("greenhouse", "asana", "Asana", "https://asana.com"),
    ("greenhouse", "dropbox", "Dropbox", "https://dropbox.com"),
    ("greenhouse", "box", "Box", "https://box.com"),
    ("greenhouse", "zendesk", "Zendesk", "https://zendesk.com"),
    ("greenhouse", "hubspot", "HubSpot", "https://hubspot.com"),
    ("greenhouse", "twilio", "Twilio", "https://twilio.com"),
    ("greenhouse", "sendgrid", "SendGrid", "https://sendgrid.com"),
    ("greenhouse", "okta", "Okta", "https://okta.com"),
    ("greenhouse", "auth0", "Auth0", "https://auth0.com"),
    ("greenhouse", "crowdstrike", "CrowdStrike", "https://crowdstrike.com"),
    ("greenhouse", "zscaler", "Zscaler", "https://zscaler.com"),
    ("greenhouse", "paloaltonetworks", "Palo Alto Networks", "https://paloaltonetworks.com"),
    ("greenhouse", "fastly", "Fastly", "https://fastly.com"),
    ("greenhouse", "digitalocean", "DigitalOcean", "https://digitalocean.com"),
    ("greenhouse", "heroku", "Heroku", "https://heroku.com"),
    ("greenhouse", "mongodb", "MongoDB", "https://mongodb.com"),
    ("greenhouse", "elastic", "Elastic", "https://elastic.co"),
    ("greenhouse", "snowflake", "Snowflake", "https://snowflake.com"),
    ("greenhouse", "databricks", "Databricks", "https://databricks.com"),
    ("greenhouse", "dbtlabs", "dbt Labs", "https://getdbt.com"),
    ("greenhouse", "fivetran", "Fivetran", "https://fivetran.com"),
    ("greenhouse", "airbyte", "Airbyte", "https://airbyte.com"),
    ("greenhouse", "segment", "Segment", "https://segment.com"),
    ("greenhouse", "amplitude", "Amplitude", "https://amplitude.com"),
    ("greenhouse", "mixpanel", "Mixpanel", "https://mixpanel.com"),
    ("greenhouse", "braze", "Braze", "https://braze.com"),
    ("greenhouse", "iterable", "Iterable", "https://iterable.com"),
    ("greenhouse", "duolingo", "Duolingo", "https://duolingo.com"),
    ("greenhouse", "coursera", "Coursera", "https://coursera.org"),
    ("greenhouse", "udemy", "Udemy", "https://udemy.com"),
    ("greenhouse", "khanacademy", "Khan Academy", "https://khanacademy.org"),
    ("greenhouse", "grammarly", "Grammarly", "https://grammarly.com"),
    ("greenhouse", "canva", "Canva", "https://canva.com"),
    ("greenhouse", "miro", "Miro", "https://miro.com"),
    ("greenhouse", "atlassian", "Atlassian", "https://atlassian.com"),
    ("greenhouse", "jetbrains", "JetBrains", "https://jetbrains.com"),
    ("greenhouse", "unity", "Unity", "https://unity.com"),
    ("greenhouse", "epicgames", "Epic Games", "https://epicgames.com"),
    ("greenhouse", "roblox", "Roblox", "https://roblox.com"),
    ("greenhouse", "riotgames", "Riot Games", "https://riotgames.com"),
    ("greenhouse", "activision", "Activision", "https://activision.com"),
    ("greenhouse", "ea", "Electronic Arts", "https://ea.com"),
    ("greenhouse", "electronicarts", "Electronic Arts", "https://ea.com"),
    ("greenhouse", "netflix", "Netflix", "https://netflix.com"),
    ("greenhouse", "spotify", "Spotify", "https://spotify.com"),
    ("greenhouse", "disney", "Disney", "https://disney.com"),
    ("greenhouse", "warnerbros", "Warner Bros", "https://warnerbros.com"),
    ("greenhouse", "paramount", "Paramount", "https://paramount.com"),
    ("greenhouse", "hulu", "Hulu", "https://hulu.com"),
    ("greenhouse", "peacock", "Peacock", "https://peacocktv.com"),
    ("greenhouse", "tesla", "Tesla", "https://tesla.com"),
    ("greenhouse", "spacex", "SpaceX", "https://spacex.com"),
    ("greenhouse", "openai", "OpenAI", "https://openai.com"),
    ("greenhouse", "anthropic", "Anthropic", "https://anthropic.com"),
    ("greenhouse", "deepmind", "DeepMind", "https://deepmind.google"),
    ("greenhouse", "scaleai", "Scale AI", "https://scale.com"),
    ("greenhouse", "togetherai", "Together AI", "https://together.ai"),
    ("greenhouse", "vercel", "Vercel", "https://vercel.com"),
    ("ashby", "openai", "OpenAI", "https://openai.com"),
    ("ashby", "anthropic", "Anthropic", "https://anthropic.com"),
    ("ashby", "cursor", "Cursor", "https://cursor.com"),
    ("ashby", "linear", "Linear", "https://linear.app"),
    ("ashby", "notion", "Notion", "https://notion.so"),
    ("ashby", "ramp", "Ramp", "https://ramp.com"),
    ("ashby", "supabase", "Supabase", "https://supabase.com"),
    ("ashby", "vercel", "Vercel", "https://vercel.com"),
    ("ashby", "replit", "Replit", "https://replit.com"),
    ("ashby", "sourcegraph", "Sourcegraph", "https://sourcegraph.com"),
    ("ashby", "planetscale", "PlanetScale", "https://planetscale.com"),
    ("ashby", "neon", "Neon", "https://neon.tech"),
    ("ashby", "pinecone", "Pinecone", "https://pinecone.io"),
    ("ashby", "weaviate", "Weaviate", "https://weaviate.io"),
    ("ashby", "plaid", "Plaid", "https://plaid.com"),
    ("ashby", "miro", "Miro", "https://miro.com"),
    ("ashby", "perplexity", "Perplexity", "https://perplexity.ai"),
    ("ashby", "sentry", "Sentry", "https://sentry.io"),
    ("ashby", "exa", "Exa", "https://exa.ai"),
    ("lever", "palantir", "Palantir", "https://palantir.com"),
    ("lever", "spotify", "Spotify", "https://spotify.com"),
    ("lever", "netflix", "Netflix", "https://netflix.com"),
    ("smartrecruiters", "Canva", "Canva", "https://canva.com"),
    ("smartrecruiters", "Visa", "Visa", "https://visa.com"),
    ("smartrecruiters", "Uber", "Uber", "https://uber.com"),
    ("smartrecruiters", "Siemens", "Siemens", "https://siemens.com"),
    ("smartrecruiters", "EPAM", "EPAM", "https://epam.com"),
    ("smartrecruiters", "Thoughtworks", "Thoughtworks", "https://thoughtworks.com"),
    ("smartrecruiters", "Capgemini", "Capgemini", "https://capgemini.com"),
    ("smartrecruiters", "Accenture", "Accenture", "https://accenture.com"),
    ("smartrecruiters", "Nvidia", "NVIDIA", "https://nvidia.com"),
    ("smartrecruiters", "Adobe", "Adobe", "https://adobe.com"),
    ("smartrecruiters", "Shopify", "Shopify", "https://shopify.com"),
    ("recruitee", "bunq", "bunq", "https://bunq.com"),
    ("recruitee", "personio", "Personio", "https://personio.com"),
]


async def probe(client: httpx.AsyncClient, ats: str, slug: str) -> int:
    try:
        if ats == "greenhouse":
            r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
            return len((r.json() or {}).get("jobs") or []) if r.status_code == 200 else 0
        if ats == "ashby":
            r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            return len((r.json() or {}).get("jobs") or []) if r.status_code == 200 else 0
        if ats == "lever":
            r = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
            if r.status_code != 200:
                return 0
            data = r.json()
            return len(data) if isinstance(data, list) else 0
        if ats == "smartrecruiters":
            r = await client.get(
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                params={"limit": 5},
            )
            if r.status_code != 200:
                return 0
            data = r.json() or {}
            return int(data.get("totalFound") or len(data.get("content") or []))
        if ats == "recruitee":
            r = await client.get(f"https://{slug}.recruitee.com/api/offers/")
            return len((r.json() or {}).get("offers") or []) if r.status_code == 200 else 0
        if ats == "personio":
            for host in (
                f"https://{slug}.jobs.personio.de/xml",
                f"https://{slug}.jobs.personio.com/xml",
            ):
                r = await client.get(host, params={"language": "en"})
                if r.status_code == 200 and "<position" in r.text.lower():
                    return max(1, r.text.lower().count("<position"))
            return 0
        if ats == "teamtailor":
            r = await client.get(f"https://{slug}.teamtailor.com/jobs.json")
            if r.status_code != 200:
                return 0
            return len((r.json() or {}).get("items") or [])
        if ats == "workable":
            r = await client.get(f"https://www.workable.com/api/accounts/{slug}")
            return len((r.json() or {}).get("jobs") or []) if r.status_code == 200 else 0
    except Exception:
        return 0
    return 0


async def main() -> None:
    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
    companies = data.get("companies") or []
    by_key = {(c.get("ats_type"), c.get("ats_slug")): c for c in companies if c.get("ats_slug")}
    headers = {"User-Agent": "RemoteAtlas/0.1 (+expand)", "Accept": "*/*"}
    sem = asyncio.Semaphore(14)
    added = 0

    async with httpx.AsyncClient(headers=headers, timeout=25.0, follow_redirects=True) as client:

        async def run(item: tuple[str, str, str, str]) -> None:
            nonlocal added
            ats, slug, name, website = item
            async with sem:
                count = await probe(client, ats, slug)
            if count <= 0:
                print(f"SKIP {ats} {slug}")
                return
            key = (ats, slug)
            region = "both" if slug.lower() in PK_BOTH or name.lower() in PK_BOTH else "global"
            career = CAREER[ats].format(slug=slug)
            if key in by_key:
                by_key[key]["is_enabled"] = True
                if region == "both":
                    by_key[key]["region_focus"] = "both"
                print(f"OK {ats} {slug} {count}")
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
            added += 1
            print(f"NEW {ats} {slug} {count}")

        await asyncio.gather(*(run(c) for c in CANDIDATES))

    merged = sorted(by_key.values(), key=lambda c: (c.get("ats_type") or "", c.get("name") or ""))
    YAML_PATH.write_text(
        yaml.safe_dump({"companies": merged}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    enabled = sum(1 for c in merged if c.get("is_enabled"))
    pk = sum(1 for c in merged if c.get("region_focus") in {"pakistan", "both"})
    print(f"TOTAL {len(merged)} ENABLED {enabled} PK {pk} ADDED {added}")


if __name__ == "__main__":
    asyncio.run(main())
