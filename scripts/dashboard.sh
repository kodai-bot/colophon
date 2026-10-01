#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# dashboard.sh - Start the read-only sales/stock dashboard (LAN only, no auth)
# Run from the colophon/ root directory

cd "$(dirname "$0")/.." || exit 1

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python -m app.dashboard
