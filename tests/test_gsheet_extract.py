"""Tests for Google Sheets URL helpers."""

from app.gsheet import extract_spreadsheet_id, spreadsheet_editor_url


def test_extract_spreadsheet_id_from_standard_url() -> None:
    """Standard docs URL yields the embedded spreadsheet id."""
    url = "https://docs.google.com/spreadsheets/d/abc123XYZ/edit#gid=0"
    assert extract_spreadsheet_id(url) == "abc123XYZ"


def test_extract_spreadsheet_id_bare_id() -> None:
    """Bare id without slashes is returned trimmed."""
    assert extract_spreadsheet_id("  abc123  ") == "abc123"


def test_extract_spreadsheet_id_rejects_non_matching_url() -> None:
    """Arbitrary URL without a recognizable id must not become a fake id."""
    bad = "https://example.com/not-a-sheet"
    assert extract_spreadsheet_id(bad) == ""


def test_spreadsheet_editor_url() -> None:
    """Editor URL uses canonical path for a valid id."""
    assert spreadsheet_editor_url("abc") == "https://docs.google.com/spreadsheets/d/abc"
