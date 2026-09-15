#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p db logs export sync
echo "Ready. Run: ./scripts/launch.sh"
