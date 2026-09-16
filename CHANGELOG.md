# Changelog

## v1.2.1 — 2026-09-16

- Added `AGENTS.md`: instructions for AI agents installing, verifying, or
  changing this project — field-tested behaviour not to simplify away,
  setup/verification checklists, and workflow rules. Reflects how this
  project has actually been built: human director, AI agents, shop staff
  as field testers. Fixed one factual error before merging (DB connection
  setup is in `app/catalog.py`, not `app/utils.py`).

## v1.2.0 — 2026-09-16

Response to an external documentation-only review (`COLOPHON_REVIEW_BRIEF.md`). Every finding was verified against the actual code first; several were already stale from prior fixes or simply incorrect (noted below). The brief's three proposed large structural rewrites — a stock event ledger, money as integer cents, and VAT support — were deliberately deferred: no evidence of stock drift, rounding, or VAT issues in production, and each is an invasive schema change not worth making without cause.

**Fixed for real (security/data-integrity):**
- S-30: `get_db()` now sets `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON` — prevents "database is locked" errors between the TUI and the nightly cron report.
- S-31: added `app/backup.py` — nightly database backup via SQLite's online backup API (safe while the app is open), rolling 14-day retention, documented cron entry.
- S-34: added `normalize_barcode()` in `app/catalog.py` — handles 18-digit scans (EAN-13 + 5-digit price add-on) and converts ISBN-10 to ISBN-13. Wired into both Counter and Intake scan handling.
- S-36: `write_csv()` now writes to a temp file and `os.replace()`s it into place, instead of writing the target path directly.
- S-33: the Open Library lookup in Intake mode now runs in a Textual worker thread instead of blocking the UI for up to 5 seconds.
- S-35 (partial): added `validate_inhouse_prefix()` — refuses to generate an in-house barcode outside the GS1 restricted-circulation range (20-29). (Not doing the transaction-locking half — negligible real risk for how this shop operates.)
- S-22: PIN comparison now uses `hmac.compare_digest` instead of `==`.
- S-23 (partial): Intake price/stock changes now log the old value alongside the new one. Left PIN-free by default per the brief's own guidance — a volunteer shop must not be locked out.
- S-21: the launcher shows a non-blocking warning if the admin PIN is still the example default (`0000`); Admin mode is never blocked over this.
- S-24: documented cron lines now redirect output to a log file, so a failure stops being silently invisible.
- S-20: replaced the plaintext-password fstab example with a credentials-file reference (chmod 600, root-owned) and added `_netdev,nofail,x-systemd.automount` — without `nofail`, a down NAS can hang the machine at boot.

**Fixed for real (documentation):**
- S-01, S-02, S-14: fixed remaining stale key/mode-count references in `USER_GUIDE.md` prose (tables were already correct from a prior pass; `app/ui/launcher.py`'s own docstring still said "three modes" too).
- S-03: documented the 4-key hard cap on non-ISBN item shortcuts.
- S-04: fixed README's report file list (was missing `payments_*.csv`, invented a nonexistent low-stock file, omitted the `YYYY/MM/` subfolder).
- S-05: replaced remaining `bookshop_logger`/`Bookshop_App` legacy names throughout code comments and docs.
- S-06: added a full Payments Mode section to `USER_GUIDE.md` (previously keys-only).
- S-07: documented the discount feature (per-basket, fixed euro amount, recorded as a synthetic negative-price line).
- S-08: fixed the Admin keyboard table (C/K cash-card keys don't exist in Admin; the real manual-sale-logging feature is in Intake mode) and removed a fully unused, never-instantiated `SalePaymentScreen` class from `app/ui/admin.py` — dead code from before manual sale logging moved to Intake.
- S-09: added the missing `app/ui/payments.py` and `app/barcode.py` to the README project tree.
- S-10: propagated the "adjust version to match your Python" caveat to the actual setup command blocks (previously only in Troubleshooting).
- S-11: explained what `README_LAUNCH.example.txt` is for, and fixed its own content (was missing Payments mode).
- S-12: documented that all timestamps/day-boundaries are local time, not UTC (verified already consistent — not a bug, just undocumented).

**Confirmed not real bugs, no change needed:** S-13 (undo already preserves the audit trail correctly), S-22's gitignore claim (README was already correct), S-24's "doesn't signal failure" claim (Python's default exit-code behavior already handles this), S-33's "no timeout/ungraceful failure" claim (already handled), S-35's "duplicate allocator" claim (both call sites already share one function).

**Explicitly deferred:** Task A (stock event ledger), Task B (money as integer cents) and S-32, Task C (VAT support), Task D (full prescribed test suite — added only targeted tests for what changed here), Task E (packaging/demo mode/CONTRIBUTING.md), and the transaction-locking half of S-35.

## v1.1.4 — 2026-09-16

- Broadened the rotating footer quotes from 54 to 93, adding to every
  existing category plus two new ones (Irish literary voices beyond
  Yeats/Beckett, and Books & Libraries).

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
