#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# launch.sh - Colophon
# Place a shortcut to this on the desktop.
# README_LAUNCH.txt beside this file has the admin PIN.

cd "$(dirname "$0")/.." || exit 1

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python3 -m app.ui.launcher
