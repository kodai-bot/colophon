#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# daily_summary.sh - Generate daily report and sync to office share
# Intended to be run via cron at 23:00 each night
# Cron entry: 0 23 * * * /path/to/colophon/scripts/daily_summary.sh >> logs/summary_cron.log 2>&1

cd "$(dirname "$0")/.." || exit 1

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python -m app.summary --date "$(date +%Y-%m-%d)"
