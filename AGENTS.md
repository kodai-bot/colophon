# AGENTS.md

Instructions for AI agents working with Colophon: whether you are setting it up for a shop, verifying an install, or changing the code.

Humans should start with `README.md` (what it is, who it suits) and `USER_GUIDE.md` (how to use it). This file is for you, the agent.

---

## 1. What this project is, and how it was made

Colophon is a terminal point-of-sale system for small, low-volume counters: a single Python process with a Textual UI, a SQLite database, and daily CSV reports. It has been in daily use at the Yeats Society Bookshop in Sligo, Ireland, since June 2026.

It was built by a human and AI agents working together, in fixed roles:

| Role | Who | Responsibility |
|---|---|---|
| **Director** | The human maintainer | Sets the goals and constraints, approves every change that reaches `master` |
| **Planner** | A chat agent | Works out the overall picture with the Director and writes briefs for the Builder |
| **Builder** | A coding agent on the shop machine | Implements briefs, verifies them against the code, and reports back |
| **Reviewer** | A chat agent, separate from the Builder's session | Checks the Builder's output before the Director approves it |
| **Field testers** | Shop staff and volunteers | Use the system for real and report what goes wrong |

**The field testers matter most, and they never see the code.** Staff with no knowledge of the system used it on real trading days. Each time something went wrong (a wrong scan, an interrupted sale, a missing step), the Director took the problem to the Builder, it was fixed, and staff had the fix the next time they used the till. Much of the code exists because of those incidents.

If you are an agent reading this, you are joining that process. Follow the rules below so the next agent can too.

---

## 2. Field-tested behaviour: do not simplify it away

Some features look redundant or over-careful. They are not. They record things that went wrong in a real shop. **Do not remove, merge or "simplify" any of the following without explicit approval from the Director:**

- **Voids are kept, not deleted.** Voided sales stay in the log marked `[VOID]`, are excluded from totals, and return their stock. The audit trail is the point.
- **Fix orphaned (Admin → 4).** Sales can be recorded without a payment method when the till is interrupted mid-sale. This screen lets someone assign cash or card afterwards.
- **Undo (Ctrl+Z) preserves the audit trail** and only works for today's sales.
- **Ctrl+Q quits the whole program from any mode**, not just the current mode. This was a real bug, fixed in v1.1.1.
- **Variable-price items prompt at the counter**, one entry per person (e.g. tour admission).
- **Multi-mark receive in Intake** (M, then +) applies one quantity to many titles, for mixed delivery boxes.
- **Bad-scan checksum rejection**, and normalisation of 18-digit scans (EAN-13 plus a 5-digit price add-on) and of ISBN-10.
- **Reports fall back to `sync/`** when the office share isn't mounted, and are written atomically.
- **Day boundaries use local time**, not UTC.
- **Intake has no PIN by default.** This is deliberate: a volunteer shop must never be locked out of receiving stock. Price and stock changes are logged with old and new values instead.

Treat these the way an archaeologist treats a feature in section: before removing anything, find out what put it there. If you can't tell why something exists, ask. Don't assume.

---

## 3. Before installing: is this the right software for the shop?

Check fit honestly and tell the human if it isn't right. Installing the wrong tool helps nobody.

**Good fit:**
- a small, low-volume counter, often volunteer-run or nonprofit;
- sells books (ISBN) alongside odds and ends (postcards, prints, tickets);
- doesn't want subscriptions or cloud accounts;
- has, or can have, a Linux machine at the counter.

**Poor fit. Say so and suggest alternatives:**
- needs integrated card processing (Colophon records card sales but doesn't process them);
- multiple tills or locations, or high transaction volume;
- must run on Windows or macOS;
- needs VAT reporting now (not yet supported; see section 8);
- needs online or e-commerce sales.

---

## 4. Setting it up for a shop

### Ask the human; never guess

Before configuring, get these from the human:

1. **Shop name.**
2. **Admin PIN.** Never leave the example `0000`, and never make one up without telling the human what it is.
3. **Non-barcoded counter items**, with prices (up to 4 shortcut keys; a blank price means "ask at counter").
4. **Low-stock warning threshold.**
5. **Office share**, if any: server, share name, and who will supply the credentials. You don't need to see the password; the human can type it into the credentials file.
6. **In-house barcode prefix**, which must be within the GS1 in-store range. The code refuses anything else.
7. **Whether staff want the nightly report and backup automated.**

### Steps

Follow `README.md` → "Setup (new machine)". In short:

```bash
sudo apt install python3.X-venv          # match the installed Python (3.11+)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x scripts/*.sh
cp config/settings.example.yaml config/settings.yaml   # then edit with the human's answers
```

Setup must be safe to repeat. Never overwrite an existing `config/settings.yaml` or `db/bookshop.db`. If either exists, stop and ask.

### Scanner

The scanner must be a USB barcode scanner in HID keyboard mode. To test it, open any text editor and scan a book: a 13-digit number followed by Enter should appear. If extra digits appear (a 5-digit add-on), Colophon handles that, but note it for the human.

### Office share

Use the credentials-file form from the README: root-owned, mode 600, mount options `_netdev,nofail,x-systemd.automount`. **Never put a password directly in `/etc/fstab`.** Without `nofail`, a down NAS can hang the machine at boot.

### Automation

Add the cron lines documented in the README for the nightly report and the database backup (`app.backup`, which uses SQLite's online backup API). Keep the log redirection so failures leave a trace.

---

## 5. Verifying an install

There is no single health-check command yet. Until there is, confirm each of these and report what you saw:

1. `pytest tests/ -v` passes.
2. `./scripts/launch.sh` opens the launcher showing four modes (Counter, Intake, Payments, Admin), and the default-PIN warning is **not** showing.
3. In Intake, scanning a known ISBN finds it via Open Library. If the machine is offline, the app should offer manual add, not freeze.
4. In Counter, scan a test item, pay cash, then void it in Admin. The void shows as `[VOID]` and stock returns.
5. `.venv/bin/python -m app.summary` writes the report files to the office share, or to `sync/` if the share isn't mounted.
6. The backup module runs and produces a backup file.
7. `crontab -l` shows the expected entries.

Leave the database clean: void any test sales, or do the test run before the shop's real catalog is loaded, and tell the human which you did.

---

## 6. Changing the code

### Hard rules

- **This is a live till.** Don't restart the app, pull updates or run migrations during opening hours unless the human says so.
- **Protect the database.** Back it up before any change that touches the schema. Schema changes go through the app's startup auto-migration, must be safe to repeat, and must lose no data.
- **Keep CSV reports stable.** Filenames and column order don't change. New columns may only be appended at the end.
- **Offline first.** Add no new network dependencies and no cloud services. Open Library lookup is the only online call, and it must stay optional.
- **Keep the stack**: Python, stdlib `sqlite3`, Textual. No ORM.
- **Never commit** `config/settings.yaml`, `db/`, `sync/`, `logs/`, or generated barcode sheets. Generated files can contain live catalog data; this happened once and was cleaned up in v1.1.0.
- **Keep the SPDX licence headers** (AGPL-3.0) on source files.

### Workflow

1. **Verify before you act.** When given a brief or bug report, confirm each point against the actual code first. If a finding is wrong or already handled, say so and skip it. Pushing back with evidence is expected.
2. **Work on a branch**, one logical change per commit, and reference the issue or finding in the commit message.
3. **Show the diff.** The Reviewer and the Director review the actual changes, not your summary of them.
4. **Update `CHANGELOG.md`** with a version bump. Say in plain words what problem was fixed and, for field-reported issues, what staff experienced.
5. **Merge to `master` only after the Director approves.**
6. **Report back** per item: DONE, NOT REPRODUCED, DEFERRED or NEEDS DECISION, with commit hashes.

### When staff report a problem

This is the main way Colophon improves:

1. Get the concrete details: what they did, what they saw, when it happened.
2. Reproduce it, or find it in `logs/` or the sales log.
3. Make the smallest fix that resolves it, and add a test for it.
4. Record it in the changelog in terms a staff member would recognise.
5. Deploy outside opening hours, and tell the human so staff know it's fixed.

---

## 7. Key files

```
app/catalog.py        ISBN lookup, barcode normalisation, stock, DB schema, DB connection (WAL, busy timeout)
app/logger.py         sale recording, void, undo
app/summary.py        daily CSV reports, office share / sync fallback
app/backup.py         online database backup with retention
app/barcode.py        in-house EAN-13 handling
app/utils.py          config, paths, atomic CSV writes
app/ui/               launcher, counter, intake, payments, admin, shared widgets
scripts/launch.sh     entry point for staff
scripts/gen_barcode.py  register in-house items, print barcode sheets
config/settings.example.yaml  template; the real settings.yaml is never committed
```

If this list and the code disagree, the code is right. Fix this file.

---

## 8. Deliberately deferred

These were considered and set aside in v1.2.0 because production gave no evidence they were needed. **Don't implement them unless the Director asks:**

- **Stock as an event ledger.** Stock is currently a stored count.
- **Money as integer cents.**
- **VAT support.**
- **A full test suite**, packaging (`pyproject.toml`), demo mode, and CONTRIBUTING.md.

If you see evidence that one of them is now needed (stock drift, rounding errors, a VAT-registered shop adopting Colophon), report it with that evidence. That's how they get scheduled.

---

## 9. Sharing back

If you install Colophon for another shop and fix something, or find something that shop needs, please open an issue or pull request at `github.com/kodai-bot/colophon`, with the same plain-language description of what happened.

Every shop that uses this adds field experience. Sharing it back means the next shop, and the next agent, starts from tested software instead of rebuilding it from scratch.
