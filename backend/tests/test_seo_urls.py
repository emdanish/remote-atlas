"""SEO URL / matcher contracts used by frontend + backend."""

from app.seo.taxonomy import skill_href


def test_public_skill_url_shape():
    assert skill_href("sql") == "/remote-sql-jobs"
    assert skill_href("next-js") == "/remote-next-js-jobs"
    assert skill_href("python") == "/remote-python-jobs"


def test_skill_public_path_regex_aligns_with_middleware():
    import re

    # Must match middleware.py skillMatch
    pattern = re.compile(r"^/remote-([a-z0-9]+(?:-[a-z0-9]+)*)-jobs/?$", re.I)
    assert pattern.match("/remote-sql-jobs").group(1) == "sql"
    assert pattern.match("/remote-next-js-jobs").group(1) == "next-js"
    assert pattern.match("/remote-typescript-jobs").group(1) == "typescript"
    # Country routes must NOT match (different path shape)
    assert pattern.match("/remote-jobs/pakistan") is None
    assert pattern.match("/remote-jobs") is None
