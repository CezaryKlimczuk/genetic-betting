"""Smoke tests for T1 package layout and pytest pythonpath."""

import subprocess
import sys


def test_import_app_package() -> None:
    import app  # noqa: F401
    import app.cli  # noqa: F401
    import app.config  # noqa: F401


def test_cli_help_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Two-player betting game" in result.stdout
