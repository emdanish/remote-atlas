"""Freshness window + purge safety (unit tests, no live DB)."""

from datetime import datetime, timedelta, timezone

from app.pipeline.freshness import freshness_cutoff, is_fresh, job_age_anchor


class _FakeJob:
    def __init__(
        self,
        *,
        is_active=True,
        posted_at=None,
        first_seen_at=None,
    ):
        self.is_active = is_active
        self.posted_at = posted_at
        self.first_seen_at = first_seen_at


def test_freshness_cutoff_roughly_n_days():
    now = datetime.now(timezone.utc)
    cutoff = freshness_cutoff(30)
    assert (now - cutoff).days in {29, 30}


def test_is_fresh_inside_window():
    now = datetime.now(timezone.utc)
    job = _FakeJob(posted_at=now - timedelta(days=5), first_seen_at=now - timedelta(days=5))
    assert is_fresh(job, 30) is True


def test_is_fresh_outside_window():
    now = datetime.now(timezone.utc)
    job = _FakeJob(posted_at=now - timedelta(days=45), first_seen_at=now - timedelta(days=45))
    assert is_fresh(job, 30) is False


def test_is_fresh_uses_first_seen_when_posted_null():
    now = datetime.now(timezone.utc)
    fresh = _FakeJob(posted_at=None, first_seen_at=now - timedelta(days=2))
    stale = _FakeJob(posted_at=None, first_seen_at=now - timedelta(days=40))
    assert is_fresh(fresh, 30) is True
    assert is_fresh(stale, 30) is False


def test_inactive_never_fresh():
    now = datetime.now(timezone.utc)
    job = _FakeJob(
        is_active=False,
        posted_at=now - timedelta(days=1),
        first_seen_at=now - timedelta(days=1),
    )
    assert is_fresh(job, 30) is False


def test_job_age_anchor_prefers_posted_at():
    now = datetime.now(timezone.utc)
    posted = now - timedelta(days=3)
    first = now - timedelta(days=10)
    job = _FakeJob(posted_at=posted, first_seen_at=first)
    assert job_age_anchor(job) == posted
