"""Tests for canonical job description normalization."""

from app.pipeline.description import (
    canonicalize_description,
    looks_like_encoded_html,
    normalize_job_description_fields,
)


def test_proper_html_preserved_as_structure():
    html_in = "<p>Hello <strong>world</strong></p><ul><li>One</li><li>Two</li></ul>"
    html_out, text = canonicalize_description(html_in, None)
    assert html_out is not None
    assert "<p>" in html_out
    assert "<li>" in html_out
    assert "Hello" in (text or "")
    assert "<" not in (text or "")


def test_escaped_html_decoded():
    raw = "&lt;p&gt;Hudson River Trading&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Ship code&lt;/li&gt;&lt;/ul&gt;"
    assert looks_like_encoded_html(raw)
    html_out, text = canonicalize_description(raw, None)
    assert html_out is not None
    assert "<p>" in html_out
    assert "&lt;p&gt;" not in html_out
    assert "Hudson River Trading" in (text or "")
    assert "Ship code" in (text or "")


def test_plain_text_to_paragraphs():
    html_out, text = canonicalize_description(None, "Line one.\n\nLine two.")
    assert html_out is not None
    assert "<p>" in html_out
    assert "Line one" in (text or "")


def test_markdown_links_become_anchors():
    html_out, _ = canonicalize_description(
        None,
        "Visit [our site](https://example.com/careers) for more.",
    )
    assert html_out is not None
    assert 'href="https://example.com/careers"' in html_out
    assert "[our site]" not in html_out


def test_sheets_metadata_stripped():
    raw = (
        '<p data-sheets-value="1" data-sheets-userformat="2" style="font-size:14px">'
        'Hello <a class="c-link" data-stringify-link="x" href="https://example.com">link</a>'
        "</p>"
    )
    html_out, text = canonicalize_description(raw, None)
    assert html_out is not None
    assert "data-sheets" not in html_out
    assert "style=" not in html_out
    assert "c-link" not in html_out
    assert "https://example.com" in html_out
    assert "Hello" in (text or "")


def test_unsafe_html_removed():
    raw = '<p>Hi</p><script>alert(1)</script><a href="javascript:alert(1)">x</a><img src=x onerror=alert(1)>'
    html_out, text = canonicalize_description(raw, None)
    assert html_out is not None
    assert "script" not in html_out.lower()
    assert "javascript:" not in html_out.lower()
    assert "onerror" not in html_out.lower()
    assert "Hi" in (text or "")


def test_do_not_concatenate_html_and_text_duplicates():
    html_in = "<p>Same company culture paragraph content that appears once.</p>"
    text_in = "Same company culture paragraph content that appears once."
    html_out, text = normalize_job_description_fields(html_in, text_in)
    assert html_out is not None
    # Prefer HTML, not text+html mash
    assert (html_out or "").count("Same company") == 1


def test_himalayas_style_real_html_still_works():
    raw = """
    <p>Himalayas is hiring a designer.</p>
    <h3>Responsibilities</h3>
    <ul><li>Own the design system</li><li>Ship iterations weekly</li></ul>
    """
    html_out, text = canonicalize_description(raw, None)
    assert html_out is not None
    assert "<ul>" in html_out
    assert "Responsibilities" in (text or "")
    assert "design system" in (text or "")


def test_bullet_plain_list():
    html_out, text = canonicalize_description(
        None,
        "Roles:\n\n- Ship features\n- Review PRs\n- Mentor juniors",
    )
    assert html_out is not None
    assert "<li>" in html_out
    assert "Ship features" in (text or "")
