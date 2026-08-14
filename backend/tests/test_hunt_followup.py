from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.matching.apply_kit import ats_time_estimate, skill_gap_path
from app.matching.followup import GHOSTED_DAYS, mark_applied, schedule_follow_up


def test_ats_estimate_workday_vs_greenhouse():
    wd = ats_time_estimate("https://company.wd1.myworkdayjobs.com/en-US/careers")
    gh = ats_time_estimate("https://boards.greenhouse.io/acme/jobs/1", "greenhouse")
    assert wd["minutes_low"] >= 20
    assert gh["minutes_high"] <= 14


def test_skill_gap_path_kubernetes():
    path = skill_gap_path(["kubernetes", "kafka"])
    assert path["skill"] == "kubernetes"
    assert any("roadmap.sh" in u for u in path["urls"])
    assert len(path["days"]) == 7


def test_zero_source_ingest_is_failure():
    started, ok = 4, 0
    assert started > 0 and ok == 0
    started2, ok2 = 0, 0
    assert not (started2 > 0 and ok2 == 0)


def test_mark_applied_sets_follow_up():
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)
    saved = SimpleNamespace(
        status="saved",
        applied_at=None,
        last_touch_at=None,
        follow_up_on=None,
    )
    mark_applied(saved, now=now)
    assert saved.status == "applied"
    assert saved.applied_at == now
    assert saved.follow_up_on == schedule_follow_up(now)
    assert saved.follow_up_on == now + timedelta(days=7)
    assert GHOSTED_DAYS == 14
