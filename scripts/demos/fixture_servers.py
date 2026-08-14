"""Start/stop helper for the three local demo MCP servers admission_scanning
and mcp_gateway scenarios (scripts/demos/scenarios.py) point at:
vendor-invoice-mcp (:8901, poisoned tool), claims-status-mcp (:8902, clean),
claims-tool-server (:8903, the MCP gateway's downstream target)."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ServerSpec:
    name: str
    script_path: Path
    port: int


SERVERS: list[ServerSpec] = [
    ServerSpec("vendor-invoice-mcp", _HERE / "fixture_mcp_servers" / "vendor_invoice_server.py", 8901),
    ServerSpec("claims-status-mcp", _HERE / "fixture_mcp_servers" / "claims_status_server.py", 8902),
    ServerSpec("claims-tool-server", _HERE / "fixture_mcp_servers" / "claims_tool_server.py", 8903),
]


def wait_for_port(host: str, port: int, timeout_s: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def start_all() -> list[subprocess.Popen]:
    procs = []
    for spec in SERVERS:
        proc = subprocess.Popen([sys.executable, str(spec.script_path)])
        procs.append(proc)
    for spec in SERVERS:
        if not wait_for_port("127.0.0.1", spec.port, timeout_s=15.0):
            stop_all(procs)
            raise RuntimeError(f"{spec.name} did not come up on port {spec.port}")
    return procs


def stop_all(procs: list[subprocess.Popen]) -> None:
    for proc in procs:
        proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    if action == "start":
        procs = start_all()
        print("fixture servers up: " + ", ".join(f"{s.name}:{s.port}" for s in SERVERS))
        for proc in procs:
            proc.wait()
    else:
        print(
            "stop is only meaningful within the same process that started them; "
            "use `pkill -f scripts/demos/fixture_mcp_servers` instead",
            file=sys.stderr,
        )
        sys.exit(1)
