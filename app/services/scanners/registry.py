"""Maps scanner name -> ScannerPort instance, for the admission-scans router to dispatch by name.

CodeGuard is deferred (not yet built).
"""
from app.services.scanners.port import ScannerPort
from app.services.scanners.promptfoo_redteam_adapter import PromptfooRedteamAdapter
from app.services.scanners.skill_scanner_adapter import SkillScannerAdapter

SCANNER_REGISTRY: dict[str, ScannerPort] = {
    "skill_scanner": SkillScannerAdapter(),
    "promptfoo_redteam": PromptfooRedteamAdapter(),
}


def get_scanner(name: str) -> ScannerPort:
    return SCANNER_REGISTRY[name]
