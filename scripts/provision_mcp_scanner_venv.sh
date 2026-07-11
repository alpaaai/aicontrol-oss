#!/usr/bin/env bash
# Provisions an isolated venv for cisco-ai-mcp-scanner (Apache-2.0), pinned,
# run as a subprocess (app/services/scanners/subprocess_runner.py) rather
# than imported in-process. This is a case-specific call, not a blanket
# policy: mcp-scanner's own dependency tree (YARA bindings, optional LLM/
# provider client libraries, its own MCP client SDK) is heavy enough to risk
# real conflicts with this app's fastapi/pydantic pins — the same concrete
# reason skill-scanner (app/services/scanners/skill_scanner_adapter.py) is
# also subprocess-isolated. Default to direct import for vendored code;
# subprocess is the exception here because of this specific dependency risk.
set -euo pipefail

VENV_DIR="${MCP_SCANNER_VENV_DIR:-/opt/aicontrol/scanner-venvs/mcp-scanner}"
PINNED_VERSION="4.7.5"

python3 -m venv "$VENV_DIR"
# mcp-scanner pulls in yara-python, which builds from source (no prebuilt
# wheel on some platforms/Python versions). setuptools sometimes detects a
# versioned compiler binary (e.g. gcc-12) that doesn't exist even when a
# working gcc is installed under the unversioned name — pin CC/CXX
# explicitly to whatever this host actually has.
CC="$(command -v gcc || command -v cc)" CXX="$(command -v g++ || command -v c++)" \
    "$VENV_DIR/bin/pip" install --quiet "cisco-ai-mcp-scanner==${PINNED_VERSION}"

echo "mcp-scanner ${PINNED_VERSION} installed at ${VENV_DIR}/bin/mcp-scanner"
