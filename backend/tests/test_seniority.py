"""Seniority classifier — junior-eligible is a search flag, not a stage rewrite."""

from app.collectors.tech_filter import looks_like_software_role
from app.pipeline.seniority import classify_job, infer_career_stage, parse_years_required_min
from app.search.intent import parse_intent


def test_unlabeled_software_engineer_stays_unknown():
    result = classify_job("Software Engineer", "Build APIs in Python.")
    assert result.career_stage == "unknown"
    assert result.junior_eligible is True  # years unknown, not senior-coded
    assert result.years_required_min is None


def test_years_five_plus_not_junior_eligible():
    result = classify_job(
        "Software Engineer",
        "You will have 5+ years of professional software experience.",
    )
    assert result.career_stage == "unknown"
    assert result.years_required_min == 5
    assert result.junior_eligible is False


def test_title_junior_jd_five_years_contradiction():
    result = classify_job(
        "Junior Software Engineer",
        "Minimum 5 years of experience required.",
    )
    assert result.career_stage == "junior"
    assert result.junior_eligible is False
    assert result.signals.get("title_jd_contradiction") is True


def test_intern_title():
    assert infer_career_stage("Software Engineering Intern") == "internship"
    result = classify_job("Engineering Intern", "Write Python services.")
    assert result.career_stage == "internship"
    assert result.junior_eligible is True
    assert result.employment_type == "internship"


def test_new_grad_distinct_from_junior():
    assert infer_career_stage("Software Engineer, New Grad 2026") == "new_grad"
    result = classify_job("University Graduate Software Engineer")
    assert result.career_stage == "new_grad"
    assert result.junior_eligible is True


def test_engineer_i_and_early_career():
    assert infer_career_stage("Software Engineer I") == "junior"
    assert infer_career_stage("Early Career Backend Engineer") == "junior"


def test_senior_title_wins():
    assert infer_career_stage("Senior Software Engineer") == "senior"
    result = classify_job("Staff Engineer", "0-2 years")
    assert result.career_stage == "senior"
    assert result.junior_eligible is False


def test_source_level_internship():
    result = classify_job("Product Role", source_level="Internship")
    assert result.career_stage == "internship"


def test_parse_years_range():
    assert parse_years_required_min("Eng", "3-5 years of experience") == 3
    assert parse_years_required_min("Eng", "0-2 years including internships") == 0


def test_honesty_flags():
    result = classify_job(
        "Backend Engineer",
        "Must be authorized to work in the US without sponsorship. Bootcamp grads welcome.",
    )
    assert result.signals.get("no_sponsorship") is True
    assert result.signals.get("equivalent_ok") is True


def test_engineering_intern_passes_software_role_filter():
    assert looks_like_software_role("Engineering Intern", None) is True
    assert looks_like_software_role("Software Engineering Intern", None) is True


def test_intent_does_not_map_bare_associate():
    hints = parse_intent("associate product manager remote")
    assert hints.career_stage != "junior"


def test_intent_intern_before_other():
    hints = parse_intent("summer intern python")
    assert hints.career_stage == "internship"


def test_seniority_query_junior_is_eligible_set():
    from app.pipeline.seniority import seniority_query

    assert seniority_query("junior") == (True, None)
    assert seniority_query("entry") == (True, None)
    assert seniority_query(None, junior_eligible=True) == (True, None)
    assert seniority_query("internship") == (False, "internship")
    assert seniority_query("new_grad") == (False, "new_grad")
    assert seniority_query("senior") == (False, "senior")


def test_exclude_senior_from_junior_profile():
    from types import SimpleNamespace

    from app.pipeline.seniority import exclude_for_junior_profile

    senior = SimpleNamespace(career_stage="senior", years_required_min=None, junior_eligible=False)
    intern = SimpleNamespace(career_stage="internship", years_required_min=0, junior_eligible=True)
    years = SimpleNamespace(career_stage="unknown", years_required_min=5, junior_eligible=False)
    assert exclude_for_junior_profile(senior, "junior") is True
    assert exclude_for_junior_profile(intern, "junior") is False
    assert exclude_for_junior_profile(years, "junior") is True
    assert exclude_for_junior_profile(senior, "senior") is False
