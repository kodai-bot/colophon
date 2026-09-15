# Changelog

## v1.1.3 — 2026-09-16

- Rewrote the Overview table and the Intake Mode / Admin Mode walkthrough
  sections in `USER_GUIDE.md`. They still described an old layout where
  Admin owned price changes, stock corrections, catalog browsing, and
  adding items — all of that lives in Intake mode now, and Admin covers
  sales log/void, reports, sales tally, and fixing orphaned transactions.
  Also fixed three stale "Admin → [N]" cross-references in Troubleshooting.

## v1.1.2 — 2026-09-16

- Rewrote the Keyboard Reference in `USER_GUIDE.md` against the actual current
  bindings — it still described an old key layout (Ctrl+P for pay, Admin mode
  owning price/stock/add-item) from before those moved to Intake mode. Now
  covers all four modes, including sub-screen keys (payment popup, void
  confirmation).

## v1.1.1 — 2026-09-16

- Fixed: Ctrl+Q inside Counter/Intake/Payments/Admin mode only returned to the
  launcher instead of quitting the program (the launcher's mode-switch loop
  never checked why a mode had exited). Each mode now signals a distinct
  "quit" result, and Ctrl+Q is shown as a visible hint in every mode.
- Added README screenshots.

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
