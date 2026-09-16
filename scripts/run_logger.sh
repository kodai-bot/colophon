#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# run_logger.sh - Start the bookshop scanner logger
# Run from the colophon/ root directory

cd "$(dirname "$0")/.." || exit 1

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python -m app.ui.counter
