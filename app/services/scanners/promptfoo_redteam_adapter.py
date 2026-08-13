"""ScannerPort adapter for Promptfoo (MIT, github.com/promptfoo/promptfoo) named-plugin
admission red-teaming — agentic:memory-poisoning and hijacking plugins.

Promptfoo splits red-teaming into two distinct steps, confirmed against the
installed package's own CLI help and source (main.js): `redteam generate`
produces attack probes via an LLM (its own internal call, default provider
openai:chat:gpt-5.5, never routed through app/services/ai_client.py — same
boundary skill_scanner_adapter.py draws around Cisco's own optional LLM
analysis engine, since this adapter's own code never calls an LLM directly),
and `eval --output <path>.json` deterministically evaluates the generated
probes against the target, writing the JSON this adapter parses.

`redteam run --output <path>` only controls where the *generated* test file
is written — it does not emit evaluation-result JSON — so this adapter chains
the two subprocess calls itself rather than relying on `redteam run` alone.
"""
import json
import os
import tempfile
from pathlib import Path

from app.core.logging import get_logger
from app.services.scanners.port import Finding
from app.services.scanners.subprocess_runner import ScannerTimeoutError, run_scanner_subprocess

logger = get_logger("promptfoo_redteam_adapter")

DEFAULT_TIMEOUT_S = 120.0


def _read_json_file(path: Path) -> dict:
    return json.loads(path.read_text())


class PromptfooRedteamAdapter:
    name = "promptfoo_redteam"

    def __init__(self, binary_path: str | None = None, timeout_s: float = DEFAULT_TIMEOUT_S):
        self.binary_path = binary_path or os.environ.get("PROMPTFOO_BINARY_PATH", "promptfoo")
        self.timeout_s = timeout_s

    async def scan(self, target: Path) -> list[Finding]:
        with tempfile.TemporaryDirectory() as tmpdir:
            generated_path = Path(tmpdir) / "generated-tests.yaml"
            results_path = Path(tmpdir) / "results.json"

            generate_cmd = [
                self.binary_path, "redteam", "generate",
                "--config", str(target),
                "--output", str(generated_path),
                "--no-progress-bar",
            ]

            try:
                exit_code, stdout, stderr = await run_scanner_subprocess(
                    generate_cmd, cwd=None, env=dict(os.environ), timeout_s=self.timeout_s
                )
            except ScannerTimeoutError as exc:
                logger.warning("promptfoo_redteam_generate_timeout", target=str(target))
                return [Finding(severity="info", rule_id="scanner_timeout", message=str(exc))]

            if exit_code != 0:
                logger.warning(
                    "promptfoo_redteam_generate_nonzero_exit",
                    target=str(target), exit_code=exit_code, stderr=stderr,
                )
                return [Finding(
                    severity="info", rule_id="scanner_error",
                    message=stderr.strip() or f"promptfoo redteam generate exited {exit_code}",
                    raw={"exit_code": exit_code, "step": "generate"},
                )]

            eval_cmd = [
                self.binary_path, "eval",
                "--config", str(generated_path),
                "--output", str(results_path),
                "--no-progress-bar",
            ]

            try:
                exit_code, stdout, stderr = await run_scanner_subprocess(
                    eval_cmd, cwd=None, env=dict(os.environ), timeout_s=self.timeout_s
                )
            except ScannerTimeoutError as exc:
                logger.warning("promptfoo_redteam_eval_timeout", target=str(target))
                return [Finding(severity="info", rule_id="scanner_timeout", message=str(exc))]

            if exit_code != 0:
                logger.warning(
                    "promptfoo_redteam_eval_nonzero_exit",
                    target=str(target), exit_code=exit_code, stderr=stderr,
                )
                return [Finding(
                    severity="info", rule_id="scanner_error",
                    message=stderr.strip() or f"promptfoo eval exited {exit_code}",
                    raw={"exit_code": exit_code, "step": "eval"},
                )]

            try:
                payload = _read_json_file(results_path)
            except (OSError, json.JSONDecodeError):
                logger.warning("promptfoo_redteam_malformed_output", target=str(target))
                return [Finding(severity="info", rule_id="scanner_error", message="promptfoo returned non-JSON output")]

            findings = []
            for result in payload.get("results", {}).get("results", []):
                if result.get("success"):
                    continue
                plugin_id = result.get("testCase", {}).get("metadata", {}).get("pluginId", "unknown")
                findings.append(Finding(
                    severity="high",
                    rule_id=f"promptfoo:{plugin_id}",
                    message=result.get("gradingResult", {}).get("reason", f"{plugin_id} attack succeeded"),
                    raw=result,
                ))
            return findings
