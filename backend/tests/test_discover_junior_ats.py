from scripts.discover_junior_ats import extract_boards, _slug_from_url


def test_slug_from_greenhouse_and_lever():
    assert _slug_from_url("https://boards.greenhouse.io/acme/jobs/123") == (
        "greenhouse",
        "acme",
    )
    assert _slug_from_url("https://jobs.lever.co/stripe/abc") == ("lever", "stripe")
    assert _slug_from_url("https://jobs.ashbyhq.com/notion") == ("ashby", "notion")


def test_extract_boards_does_not_use_listing_as_job():
    listings = [
        {
            "company_name": "Acme",
            "url": "https://boards.greenhouse.io/acme/jobs/99",
            "title": "New Grad SWE",
        }
    ]
    boards = extract_boards(listings)
    assert ("greenhouse", "acme") in boards
    assert boards[("greenhouse", "acme")]["hires_juniors"] is True
    assert "New Grad SWE" not in str(boards)
