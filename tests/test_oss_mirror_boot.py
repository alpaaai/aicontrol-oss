"""app/main.py must be importable when enterprise/ is physically absent.

.github/workflows/mirror-oss.yml runs `rm -rf enterprise/` before pushing
this repo to the public github.com/alpaaai/aicontrol-oss mirror. Any
unconditional `from enterprise... import ...` at module scope in app/main.py
means every OSS deployment crashes on boot with ModuleNotFoundError, since
that directory never exists there.
"""
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_app_main_boots_without_enterprise_package():
    with tempfile.TemporaryDirectory() as tmp:
        os.symlink(os.path.join(REPO_ROOT, "app"), os.path.join(tmp, "app"))
        # Deliberately no enterprise/ symlink — simulates the stripped OSS mirror.
        result = subprocess.run(
            [sys.executable, "-c", "import app.main"],
            cwd=tmp,
            env={
                **os.environ,
                "PYTHONPATH": tmp,
                "DATABASE_URL": "postgresql+asyncpg://x:x@localhost:5432/x",
            },
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert result.returncode == 0, result.stderr
    assert "enterprise" not in result.stderr.lower()
