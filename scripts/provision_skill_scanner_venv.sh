#!/usr/bin/env bash
# Provisions an isolated venv for cisco-ai-skill-scanner (Apache-2.0), pinned,
# run as a subprocess (app/services/scanners/subprocess_runner.py) rather than
# imported in-process — same dependency-conflict rationale as
# scripts/provision_mcp_scanner_venv.sh (this package pins fastapi>=0.115/
# pydantic>=2.10, which risk transitive conflicts with this app's own pins).
#
# Pinned to 2.0.4, not the latest 2.0.12: confirmed via a real install attempt
# that 2.0.12 requires litellm>=1.84.0, and no litellm release in that range
# supports Python 3.14 (this image's Python version) -- pip's resolver
# exhausts every 1.84.x-1.93.x candidate and fails outright. 2.0.4 has a
# looser litellm>=1.77.0 bound, so litellm is pinned explicitly here to
# 1.83.7 (confirmed via pypi.org/pypi/litellm/1.83.7/json: requires_python
# "<4.0,>=3.9", no 3.14 exclusion, unlike 1.83.8+) to avoid a slow resolver
# backtrack across litellm's several hundred releases.
set -euo pipefail

VENV_DIR="${SKILL_SCANNER_VENV_DIR:-/opt/aicontrol/scanner-venvs/skill-scanner}"
PINNED_VERSION="2.0.4"
PINNED_LITELLM_VERSION="1.83.7"

python3 -m venv "$VENV_DIR"
CC="$(command -v gcc || command -v cc)" CXX="$(command -v g++ || command -v c++)" \
    "$VENV_DIR/bin/pip" install --quiet "litellm==${PINNED_LITELLM_VERSION}" "cisco-ai-skill-scanner==${PINNED_VERSION}"

echo "skill-scanner ${PINNED_VERSION} installed at ${VENV_DIR}/bin/skill-scanner"
