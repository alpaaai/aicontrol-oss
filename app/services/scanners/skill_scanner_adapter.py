"""ScannerPort adapter for cisco-ai-skill-scanner (Apache-2.0, github.com/cisco-ai-defense/skill-scanner).

Runs only the default deterministic analyzers (static + bytecode + pipeline).
Never passes --use-llm / --use-aidefense / --use-virustotal / --use-behavioral —
those enable LLM analysis, a Cisco cloud call, or a third-party API call, all
of which would violate this project's "OPA/admission decisions always
deterministic, LLM calls only through app/services/ai_client.py" rule.

Installed in its own isolated venv (see scripts/provision_skill_scanner_venv.sh),
invoked as a subprocess — never imported in-process, since it depends on
fastapi>=0.115/pydantic>=2.10 which risk transitive version conflicts with
this app's own pins.
"""
import json
import os
from pathlib import Path

from app.core.logging import get_logger
from app.services.scanners.port import Finding
from app.services.scanners.subprocess_runner import ScannerTimeoutError, run_scanner_subprocess

logger = get_logger("skill_scanner_adapter")

_FORBIDDEN_ENV_VARS = ("SKILL_SCANNER_LLM_API_KEY", "AI_DEFENSE_API_KEY", "VIRUSTOTAL_API_KEY")

DEFAULT_TIMEOUT_S = 60.0


class SkillScannerAdapter:
    name = "skill_scanner"

    def __init__(self, binary_path: str | None = None, timeout_s: float = DEFAULT_TIMEOUT_S):
        self.binary_path = binary_path or os.environ.get(
            "SKILL_SCANNER_BINARY_PATH", "/opt/aicontrol/scanner-venvs/skill-scanner/bin/skill-scanner"
        )
        self.timeout_s = timeout_s

    def _clean_env(self) -> dict:
        env = dict(os.environ)
        for var in _FORBIDDEN_ENV_VARS:
            env.pop(var, None)
        return env

    async def scan(self, target: Path) -> list[Finding]:
        cmd = [self.binary_path, "scan", str(target), "--format", "json"]

        try:
            exit_code, stdout, stderr = await run_scanner_subprocess(
                cmd, cwd=None, env=self._clean_env(), timeout_s=self.timeout_s
            )
        except ScannerTimeoutError as exc:
            logger.warning("skill_scanner_timeout", target=str(target))
            return [Finding(severity="info", rule_id="scanner_timeout", message=str(exc))]

        if exit_code != 0:
            logger.warning("skill_scanner_nonzero_exit", target=str(target), exit_code=exit_code, stderr=stderr)
            return [Finding(
                severity="info", rule_id="scanner_error",
                message=stderr.strip() or f"skill-scanner exited {exit_code}",
                raw={"exit_code": exit_code},
            )]

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("skill_scanner_malformed_output", target=str(target))
            return [Finding(severity="info", rule_id="scanner_error", message="skill-scanner returned non-JSON output")]

        findings = []
        for raw_finding in payload.get("findings", []):
            location = raw_finding.get("file_path")
            if location and raw_finding.get("line_number") is not None:
                location = f"{location}:{raw_finding['line_number']}"
            findings.append(Finding(
                severity=raw_finding["severity"].lower(),
                rule_id=raw_finding["rule_id"],
                message=raw_finding.get("title", raw_finding["rule_id"]),
                location=location,
                raw=raw_finding,
            ))
        return findings
