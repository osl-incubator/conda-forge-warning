from pathlib import Path

from cf_warning import CondaForgeWarning


def test_cfwarning():
    report = CondaForgeWarning()
    report.run()
