#!/usr/bin/env bash
# one2one -- single package, native install.
#
# Installs the one2one CLI plus every tool payload in one shot, so a fresh
# Kali/Ubuntu box ends up with the complete environment. Best-effort: each
# tool's failure is recorded in the report, never fatal.
#
# Requirements: Python >= 3.10, git, sudo (for system packages).
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 (>= 3.10) is required" >&2
    exit 1
fi

echo "==> [1/2] installing one2one package"
if command -v uv >/dev/null 2>&1; then
    uv pip install --system .
elif command -v pipx >/dev/null 2>&1; then
    pipx install .
else
    python3 -m pip install .
fi

echo "==> [2/2] installing every tool payload (best-effort)"
echo "    report -> ~/.one2one/install-report.md"
one2one --install-all

echo
echo "Done. Run any tool with:  one2one"
echo "See the report at:        ~/.one2one/install-report.md"
