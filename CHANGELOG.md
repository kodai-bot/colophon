# Changelog

## v1.1.0 — 2026-09-15

Renamed and prepared for public release as **Colophon**.

- Relicensed from MIT to AGPL-3.0.
- Removed hardcoded shop-specific branding, PIN, and barcode-prefix defaults from code and docs — shop identity now flows entirely from `config/settings.yaml`.
- Added `config/settings.example.yaml` and `README_LAUNCH.example.txt` as generic templates; the real, instance-specific `config/settings.yaml` and `README_LAUNCH.txt` are no longer tracked in git.
- Removed a stray internal work-order note and two generated HTML files containing live catalog data that had been accidentally committed.
- Added SPDX license headers to all source files.

## v1.0.0 — 2026-06-10

Initial release.

- Counter mode: barcode scanning, non-ISBN items, basket/subtotal, cash/card payment
- Intake mode: catalog browsing, stock management, price editing, label printing
- Payments mode: sundry payment entry (room hire, memberships, events, etc.)
- Admin mode: daily sales log, void transactions, generate and send reports
- Daily CSV reports with transaction grouping (`transaction_id`)
- Automated nightly report via cron
- SQLite database with auto-migration
- In-house barcode generation for unlisted items
