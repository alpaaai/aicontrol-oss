"""Maps scanner name -> ScannerPort instance, for the admission-scans router to dispatch by name.

CodeGuard is deferred (not yet built) — only skill_scanner is registered today.
"""
from app.services.scanners.port import ScannerPort
from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

SCANNER_REGISTRY: dict[str, ScannerPort] = {
    "skill_scanner": SkillScannerAdapter(),
}


def get_scanner(name: str) -> ScannerPort:
    return SCANNER_REGISTRY[name]
