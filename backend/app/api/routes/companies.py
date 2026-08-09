"""Detect ATS type from an official careers URL (no HTML scrape of job content)."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, HttpUrl

from app.security import enforce_rate_limit

router = APIRouter(prefix="/companies", tags=["companies"])


class DetectRequest(BaseModel):
    url: HttpUrl


class DetectResponse(BaseModel):
    input_url: str
    ats_type: str | None
    ats_slug: str | None
    board_url: str | None
    jobs_count: int | None = None
    note: str


def _is_public_hostname(host: str) -> bool:
    """Reject private / link-local / metadata targets to reduce SSRF risk."""
    host = (host or "").strip().lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        # Literal IP in host
        ip = ipaddress.ip_address(host)
        return ip.is_global
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if not ip.is_global:
            return False
    return True


def _assert_safe_workday_host(host: str) -> None:
    host = (host or "").lower()
    if not host.endswith(".myworkdayjobs.com"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workday host must be *.myworkdayjobs.com",
        )
    if not _is_public_hostname(host):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Host resolves to a non-public address",
        )


@router.post("/detect-ats", response_model=DetectResponse)
async def detect_ats(body: DetectRequest, request: Request) -> DetectResponse:
    await enforce_rate_limit(request, "detect-ats", limit=10, period_seconds=300)
    url = str(body.url)
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    # Strip credentials / ports for classification
    if "@" in host:
        host = host.split("@", 1)[-1]
    host = host.split(":")[0]
    path = parsed.path or ""

    if host and not any(
        h in host
        for h in (
            "greenhouse.io",
            "lever.co",
            "ashbyhq.com",
            "workable.com",
            "smartrecruiters.com",
            "personio.",
            "teamtailor.com",
            "recruitee.com",
            "breezy.hr",
            "bamboohr.com",
            "myworkdayjobs.com",
        )
    ):
        # Unknown career host — only probe fixed ATS APIs with slug guesses; never fetch user's URL
        if not _is_public_hostname(host):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or non-public host",
            )

    ats_type = None
    slug = None
    if "greenhouse.io" in host or "boards.greenhouse.io" in host:
        ats_type = "greenhouse"
        m = re.search(r"/([^/]+)/?", path)
        slug = m.group(1) if m else None
    elif "lever.co" in host:
        ats_type = "lever"
        m = re.search(r"/([^/]+)/?", path)
        slug = m.group(1) if m else None
    elif "ashbyhq.com" in host:
        ats_type = "ashby"
        m = re.search(r"/([^/]+)/?", path)
        slug = m.group(1) if m else None
    elif "workable.com" in host:
        ats_type = "workable"
        m = re.search(r"/([^/]+)/?", path)
        slug = m.group(1) if m else None
    elif "smartrecruiters.com" in host:
        ats_type = "smartrecruiters"
        m = re.search(r"/([^/]+)/?", path)
        slug = m.group(1) if m else None
    elif "personio." in host or "jobs.personio." in host:
        ats_type = "personio"
        m = re.match(r"^([^.]+)\.jobs\.personio\.", host)
        slug = m.group(1) if m else host.split(".")[0]
    elif "teamtailor.com" in host:
        ats_type = "teamtailor"
        slug = host.split(".")[0]
    elif "recruitee.com" in host:
        ats_type = "recruitee"
        slug = host.split(".")[0]
    elif "breezy.hr" in host:
        ats_type = "breezy"
        slug = host.split(".")[0]
    elif "bamboohr.com" in host:
        ats_type = "bamboohr"
        slug = host.split(".")[0]
    elif host.endswith(".myworkdayjobs.com"):
        _assert_safe_workday_host(host)
        ats_type = "workday"
        path_parts = [part for part in path.split("/") if part]
        site = path_parts[1] if len(path_parts) > 1 and path_parts[0].lower() in {"en-us", "en-gb"} else None
        tenant = host.split(".")[0]
        slug = f"{host}|{tenant}|{site}" if site else None
    else:
        company = host.replace("www.", "").split(".")[0]
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,64}", company or ""):
            return DetectResponse(
                input_url=url,
                ats_type=None,
                ats_slug=None,
                board_url=None,
                note="Could not derive a safe board slug from this URL.",
            )
        guesses = [company, company.replace("-", ""), f"{company}hq"]
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for guess in guesses:
                for kind, probe in [
                    ("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{guess}/jobs"),
                    ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{guess}"),
                    ("lever", f"https://api.lever.co/v0/postings/{guess}?mode=json&limit=1"),
                ]:
                    try:
                        r = await client.get(probe)
                        if r.status_code != 200:
                            continue
                        data = r.json()
                        count = 0
                        if kind == "lever" and isinstance(data, list):
                            count = len(data)
                        else:
                            count = len((data or {}).get("jobs") or [])
                        board = {
                            "greenhouse": f"https://boards.greenhouse.io/{guess}",
                            "ashby": f"https://jobs.ashbyhq.com/{guess}",
                            "lever": f"https://jobs.lever.co/{guess}",
                        }[kind]
                        return DetectResponse(
                            input_url=url,
                            ats_type=kind,
                            ats_slug=guess,
                            board_url=board,
                            jobs_count=count,
                            note="Detected via slug probe against public ATS JSON APIs (no page scrape).",
                        )
                    except Exception:
                        continue
        return DetectResponse(
            input_url=url,
            ats_type=None,
            ats_slug=None,
            board_url=None,
            note="No public Greenhouse/Lever/Ashby board detected. Custom career portals are skipped.",
        )

    board_url = None
    jobs_count = None
    if ats_type and slug:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            if ats_type == "greenhouse":
                board_url = f"https://boards.greenhouse.io/{slug}"
                r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
                if r.status_code == 200:
                    jobs_count = len((r.json() or {}).get("jobs") or [])
            elif ats_type == "ashby":
                board_url = f"https://jobs.ashbyhq.com/{slug}"
                r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
                if r.status_code == 200:
                    jobs_count = len((r.json() or {}).get("jobs") or [])
            elif ats_type == "lever":
                board_url = f"https://jobs.lever.co/{slug}"
                r = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json", "limit": 100})
                if r.status_code == 200 and isinstance(r.json(), list):
                    jobs_count = len(r.json())
            elif ats_type == "workable":
                board_url = f"https://apply.workable.com/{slug}/"
                r = await client.get(f"https://www.workable.com/api/accounts/{slug}", params={"details": "true"})
                if r.status_code == 200:
                    jobs_count = len((r.json() or {}).get("jobs") or [])
            elif ats_type == "bamboohr":
                board_url = f"https://{slug}.bamboohr.com/careers"
                r = await client.get(f"https://{slug}.bamboohr.com/careers/list")
                if r.status_code == 200 and "json" in (r.headers.get("content-type") or "").lower():
                    data = r.json() or {}
                    jobs_count = int(data.get("meta", {}).get("totalCount") or len(data.get("result") or []))
            elif ats_type == "workday":
                board_url = url
                workday_parts = slug.split("|")
                if len(workday_parts) == 3:
                    wd_host, tenant, site = workday_parts
                    _assert_safe_workday_host(wd_host)
                    r = await client.post(
                        f"https://{wd_host}/wday/cxs/{tenant}/{site}/jobs",
                        json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""},
                    )
                    if r.status_code == 200:
                        jobs_count = int((r.json() or {}).get("total") or 0)

    return DetectResponse(
        input_url=url,
        ats_type=ats_type,
        ats_slug=slug,
        board_url=board_url,
        jobs_count=jobs_count,
        note="Parsed from official ATS career URL.",
    )
