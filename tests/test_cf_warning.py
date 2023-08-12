"""Tests for CondaForgeWarning."""

from cf_warning import CondaForgeWarning


def test_cfwarning():
    """Test CondaForgeWarning."""
    report = CondaForgeWarning()
    report.run()
