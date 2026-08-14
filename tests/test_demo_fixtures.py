from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "scripts" / "demos" / "fixtures"


def test_malicious_invoice_skill_has_injection_and_shell_pipe():
    manifest = (FIXTURES / "malicious-invoice-skill" / "SKILL.md").read_text()
    code = (FIXTURES / "malicious-invoice-skill" / "run.py").read_text()
    assert "ignore" in manifest.lower() and "previous instructions" in manifest.lower()
    assert "| sh" in code or "|sh" in code or "| bash" in code


def test_benign_report_skill_has_no_license_field_and_no_injection_patterns():
    manifest = (FIXTURES / "benign-report-skill" / "SKILL.md").read_text()
    assert "license" not in manifest.lower()
    assert "ignore" not in manifest.lower()
