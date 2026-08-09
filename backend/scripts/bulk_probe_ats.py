"""Large-batch Greenhouse/Ashby/Lever/SmartRecruiters/Recruitee slug probe."""

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
}

# Dense tech/product company slug guesses (many will 404; survivors are kept)
GH_SLUGS = """
stripe airbnb discord dropbox gitlab figma notion airtable asana doordash
coinbase robinhood square blockrivian lyft uber shopify snowflake datadog
cloudflare hashicorp elastic mongodb databricks nvidia openai anthropic
deepmind scaleai togetherai vercel linear ramp cursor perplexity sentry
exabyte hughesnet twilio sendgrid pagerduty hubspot salesforce zendesk
atlassian canva miro kalshi robinhood affirm chime sofi monzo revolut
n26 klarna wise transferwise intercom gongio segment amplitude mixpanel
braze Iterable mailchimp activecampaign hubspot crunchyroll roblox unity
epicgames riotgames valve blizzard activision ea electronicarts nvidia
intel amd qualcomm arm broadcom marvell micron appliedmaterials
autodesk adobe adobeexperiencecloud sap oracle ibm accenture capgemini
epam thoughtworks cognizant infosys wipro tcs accenturefederal
redfin zillow opendoor compass wework weworkcompanies
spotify netflix disney warnerbros paramount peacock hulu
tesla spacex blueorigin rocketlab anduril palantir andurilindustries
anduril lockheedmartin northropgrumman boeing raytheon
duolingo quizlet khanacademy coursera udemy pluralsight
github gitlab bitbucket sourcegraph replit codesandbox
hashicorp terraform vault consul nomad
elastic kibana logstash opensearch
databricks mosaicml huggingfacetco
reddit pinterest tumblr snap snapchat tiktok bytedance
alibaba tencent baidu meituan grab gojek sea shopee
mercari rakuten softbank sony panasonic hitachi
samsung lgelectronics skhynix
bookingcom expedia tripadvisor airbnbexpedia
deliveroo justeat doordashubereats grubhub
instacart ocado getir gorillas
figma sketch invision adobeacrobat
notion crockett notionlabs
1password lastpass dashlane bitwarden
okta auth0 pingidentity forgeRock
crowdstrike paloaltonetworks zscaler cloudflarefastly
fastly akamai cloudinary imgix
digitalocean linode vultr hetzner
heroku render flyio railway
supabase planetscale neon neontech cockroachlabs clickhouse
timescale influxdata mongodb atlas
snowflake dbtlabs fivetran airbyte stitch
looker tableau modeanalytics metabase
dbtlabs montecarlo great expectations
segment mparticle rudderstack
braze customerio iterable
zendesk intercom freshdesk frontapp
slack mattermost discord telegram
zoom webex microsoftteams
notion cursormicrosoft
openai anthropic cohereai mistralai
huggingface stabilityai midjourney runwayml
replicate falai fireworksai
togetherai anyscale modal
langchain llamaindex pinecone weaviate qdrant chroma
weightsandbiases neptuneai cometml
anyscale modal replicate
duolingo busuu babbel
grammarly duolingobusiness
coursera edx udacity
chegg coursehero
rippling gusto gusto-careers
deel remotecom remote
oysterhr papaya global
lattice cultureamp 15five
leverashby greenhouse
brex ramp mercurynovo
mercury amalgam
plaid stripe checkout
adyen checkoutcom worldpay
shopify bigcommerce woocommerce
magento salesforcecommerce
etsy ebid ebay
wayfair overstock
zalando asos farfetch
hellofresh factor75
peloton strava whoop
calm headspace betterhelp
oscarhealth cityblock
tempus colorgenomics
illumina 23andme
moderna biontech
gilead amgen genentech
roche novartis pfizer
jnj johnsonandjohnson
abbvie merck astrazeneca
""".split()

ASHBY_SLUGS = """
openai anthropic linear notion ramp cursor perplexity sentry exa
warp browserbase buffer ghost supabase posthog resend granola
vercel replit sourcegraph planetscale neon runwayml midjourney
stabilityai mistralai cohereai pinecone weaviate
brex mercury amalgam plaid
rippling gusto deel remote
lattice cultureamp
figma canva miro
datadog elastic
""".split()

LEVER_SLUGS = """
netflix palantir spotify activecampaign wealthfront
anduril rivian lyft twilio
duolingo quizlet
plaid stripe
""".split()

SR_SLUGS = """
Visa Siemens SchneiderElectric Autodesk ElectronicArts Uber Deliveroo
Bookingcom Spotify Klarna N26 Revolut Miro Elastic GitLab HashiCorp
Datadog Snowflake CrowdStrike Okta Twilio Shopify Adobe Nvidia Intel
AMD Qualcomm SAP Oracle Capgemini Accenture EPAM Thoughtworks Zendesk
Atlassian Canva Figma Notion Airtable Asana Dropbox Box Pinterest
Reddit Roblox Unity EpicGames IBM Dell HP Cisco Juniper
Nokia Ericsson Philips Bosch
Unilever Nestle PepsiCo CocaCola
Marriott Hilton Hyatt
""".split()

RECRUITEE_SLUGS = """
miro n26 klarna typeform personio contentful sumup getyourguide
deliveryhero hellofresh bunq adyen mollie coolblue tomtom
backbase messagebird picnic bol
""".split()


async def probe(client: httpx.AsyncClient, ats: str, slug: str) -> int:
    try:
        if ats == "greenhouse":
            r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
            if r.status_code != 200:
                return 0
            return len((r.json() or {}).get("jobs") or [])
        if ats == "ashby":
            r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            if r.status_code != 200:
                return 0
            return len((r.json() or {}).get("jobs") or [])
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
            if r.status_code != 200:
                return 0
            return len((r.json() or {}).get("offers") or [])
    except Exception:
        return 0
    return 0


async def main() -> None:
    data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
    companies = data.get("companies") or []
    by_key = {(c.get("ats_type"), c.get("ats_slug")): c for c in companies if c.get("ats_slug")}

    candidates: list[tuple[str, str]] = []
    for s in GH_SLUGS:
        candidates.append(("greenhouse", s.lower().strip()))
    for s in ASHBY_SLUGS:
        candidates.append(("ashby", s.lower().strip()))
    for s in LEVER_SLUGS:
        candidates.append(("lever", s.lower().strip()))
    for s in SR_SLUGS:
        candidates.append(("smartrecruiters", s.strip()))
    for s in RECRUITEE_SLUGS:
        candidates.append(("recruitee", s.lower().strip()))

    # de-dupe
    seen = set()
    uniq = []
    for ats, slug in candidates:
        if not slug or (ats, slug) in seen:
            continue
        seen.add((ats, slug))
        uniq.append((ats, slug))

    headers = {"User-Agent": "RemoteAtlas/0.1 (+bulk-probe)", "Accept": "application/json"}
    sem = asyncio.Semaphore(16)
    added = 0

    async with httpx.AsyncClient(headers=headers, timeout=25.0, follow_redirects=True) as client:

        async def run(ats: str, slug: str) -> None:
            nonlocal added
            async with sem:
                await asyncio.sleep(0.04)
                count = await probe(client, ats, slug)
            if count <= 0:
                return
            key = (ats, slug)
            if key in by_key:
                by_key[key]["is_enabled"] = True
                print(f"OK {ats} {slug} {count}")
                return
            name = slug.replace("-", " ").replace("_", " ").title()
            career = CAREER[ats].format(slug=slug)
            by_key[key] = {
                "name": name,
                "website": f"https://{slug.replace('_', '-')}.com",
                "ats_type": ats,
                "ats_slug": slug,
                "career_page_url": career,
                "region_focus": "global",
                "is_enabled": True,
            }
            added += 1
            print(f"NEW {ats} {slug} {count}")

        await asyncio.gather(*(run(a, s) for a, s in uniq))

    merged = sorted(by_key.values(), key=lambda c: (c.get("ats_type") or "", c.get("name") or ""))
    YAML_PATH.write_text(
        yaml.safe_dump({"companies": merged}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    enabled = sum(1 for c in merged if c.get("is_enabled"))
    print(f"TOTAL {len(merged)} ENABLED {enabled} ADDED {added}")


if __name__ == "__main__":
    asyncio.run(main())
