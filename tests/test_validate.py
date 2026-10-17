"""case/validate.py must keep passing."""

import subprocess
import sys

from src.config import CASE_DIR


def test_validate_py_passes():
    proc = subprocess.run(
        [sys.executable, "validate.py"], cwd=CASE_DIR, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 failed" in proc.stdout
