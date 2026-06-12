"""本番相当の import 経路の単体テスト。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_quote0_vendor_client_importable() -> None:
    from quote0.vendor import quote0_client  # noqa: F401


def test_python_m_quote0_runs_without_extra_pythonpath() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTEST_CURRENT_TEST", None)

    result = subprocess.run(
        [sys.executable, "-m", "quote0"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stderr + result.stdout
    assert "No module named 'quote0.vendor'" not in output
    assert "ModuleNotFoundError" not in output or "quote0.vendor" not in output


def test_python_m_send_ical_runs_without_extra_pythonpath() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTEST_CURRENT_TEST", None)

    result = subprocess.run(
        [sys.executable, "-m", "quote0.commands.send_ical"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stderr + result.stdout
    assert "No module named 'quote0.vendor'" not in output
    assert "ModuleNotFoundError" not in output or "quote0.vendor" not in output
