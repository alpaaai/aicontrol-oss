"""run_demo.sh is a thin wrapper -- test its structure and failure behavior,
not a live end-to-end run (that needs a real server, covered by Task 5's
manual smoke test and this plan's final verification task)."""
import os
import stat
import subprocess

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "demos", "run_demo.sh")


def test_script_exists_and_is_executable():
    assert os.path.exists(SCRIPT)
    mode = os.stat(SCRIPT).st_mode
    assert mode & stat.S_IXUSR


def test_script_fails_clearly_when_api_is_unreachable():
    env = {**os.environ, "AICONTROL_API_URL": "http://localhost:59999"}
    result = subprocess.run(
        [SCRIPT, "--scenario", "insurance", "--mode", "fast"],
        capture_output=True, text=True, timeout=15, env=env,
    )
    assert result.returncode != 0
    assert "not reachable" in (result.stdout + result.stderr).lower()
