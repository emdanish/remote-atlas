"""In-batch apply-URL dedup helpers."""

from app.pipeline.normalize import NormalizedJob
from app.pipeline.upsert import _apply_key, _prefer_job


def test_apply_key_strips_noise():
    a = _apply_key("https://www.example.com/jobs/1?utm_source=x")
    b = _apply_key("https://example.com/jobs/1")
    assert a == b


def test_prefer_ats_over_aggregator():
    ats = NormalizedJob(
        source="greenhouse",
        external_id="1",
        title="Engineer",
        company_name="Acme",
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        description_text="long description for ats board role",
    )
    agg = NormalizedJob(
        source="themuse",
        external_id="9",
        title="Engineer",
        company_name="Acme",
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        description_text="short",
    )
    assert _prefer_job(ats, agg) is True
    assert _prefer_job(agg, ats) is False
