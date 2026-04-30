"""Sanity checks for spreadsheet toolbar template markup."""

from pathlib import Path


def test_spreadsheet_toolbar_uses_combobox_not_native_select() -> None:
    """Toolbar should use the combobox input, not a native select."""
    root = Path(__file__).resolve().parent.parent
    path = root / "app" / "templates" / "_spreadsheet_toolbar.html"
    text = path.read_text(encoding="utf-8")
    assert "spreadsheet-combobox-input" in text
    assert 'id="spreadsheet-selector"' not in text
    assert "Add spreadsheet" not in text
