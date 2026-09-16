# Colophon — User Guide

**Admin PIN:** set in `config/settings.yaml`.
Problems? Contact whoever administers this system for your shop.

> Colophon was originally built for and is used daily at the Yeats Society Bookshop, Sligo. This guide is written generically for any shop running it — screenshots and specific item names will differ from your own catalog.

---

## Overview

The system has four modes, all launched from the same startup screen:

| Mode | Who uses it | What it does |
|---|---|---|
| **Counter** | All staff | Scan items for sale, take payment |
| **Intake** | Stock volunteers / managers | Browse the catalog, receive deliveries, correct prices and stock, add new items |
| **Payments** | Anyone | Log sundry payments — room hire, memberships, event bookings, etc. |
| **Admin** | Managers | Sales log and voids, send reports, sales tally, fix orphaned transactions |

---

## Starting the System

Double-click **launch.sh** on the desktop, or open a terminal and run:

```
./scripts/launch.sh
```

The launcher screen appears. Press **1**, **2**, **3**, or **4** to enter a mode, or click the button.

---

## Counter Mode — Daily Sales

This is the screen staff use all day. The barcode scanner works like a keyboard — just point and scan, no clicking needed.

### Scanning a book

1. Point the scanner at the barcode on the back of the book and pull the trigger.
2. The title, author, publisher, and price appear in the display panel.
3. The item is added to the **basket** on the right side of the screen.
4. Scan the next item, or press **Subtotal / Pay** when the customer is ready.

### Non-ISBN items (postcards, tours)

Items with in-house barcodes (postcards, tour tickets, etc.) are scanned exactly like books — just point and scan. They are registered in the catalog and tracked the same way.

Items without barcodes can be selected by pressing a number key or clicking the button on the left panel:

| Key | Item | Price |
|---|---|---|
| **1** | Postcard | €4.00 — logs immediately |
| **2** | Postcard (large) | €6.00 — logs immediately |
| **3** | Tour admission | Variable — a price prompt appears |

For **Tour admission**: a box appears asking for the amount. Type the price for one person and press **Enter**. Repeat for each person in the group (press **3** again for each).

### Taking payment (Subtotal)

When all items are scanned:

1. Press **Ctrl+T** (or click the green **Subtotal / Pay** button).
2. A box shows the number of items and the total amount.
3. Press **C** for cash or **K** for card.
4. The basket clears and the screen resets for the next customer.

> If the customer needs a moment (checking their wallet etc.), press **Esc** to close the payment box — the basket stays open.

### Undoing a mistake

Scanned the wrong book? Press **Ctrl+Z** immediately. This removes the last item from the basket and restores the stock count. You can press Ctrl+Z multiple times to remove more items.

Undo only works for sales made today. All timestamps and "today" boundaries throughout Colophon use the machine's local time, not UTC — set your system timezone correctly and this handles daylight saving automatically.

### Applying a discount

Press **Ctrl+D** to open the discount box. A discount is applied to the whole basket as a fixed euro amount (not a percentage), capped at the basket total — it isn't per item. It's recorded as its own "Discount" line with a negative price, tied to the same transaction, so it appears in `sales_*.csv` and is already reflected in the totals in `summary_*.csv`.

### Leaving Counter mode

Press **Esc** or click **⌂ Home** to return to the launcher.

---

## Intake Mode — Catalog, Stock, and Deliveries

Intake mode is the working home for the catalog: browsing it, receiving deliveries, correcting prices and stock, and adding new items. No PIN required.

### Browsing and searching the catalog

The main screen shows the full catalog in a table. Type part of a title into the search box and press **Enter** to filter it — or scan a barcode to jump straight to that item.

### Scanning a delivery

1. Scan the barcode on the item.
2. **If it's already in the system:** a quantity panel appears showing the current stock. Set how many copies arrived and press **Enter** to confirm.
3. **If it's new:** the system looks it up online (Open Library). If found, it shows the title, author, publisher and year, then a price entry box appears — type the price and press **Enter**. The item is added to the catalog.
4. **If not found online:** a message appears suggesting you add it manually (press **A**), or try a different barcode orientation.

### Receiving several different items at once

Highlight each item in the catalog table and press **M** to mark it (a ✓ appears). Once you have marked everything from the delivery, press **+**: instead of asking for a quantity per item, it applies the same quantity to every marked item in one step — useful when a box contains several copies each of several different titles.

### Correcting a price or stock count

1. Search for the item and highlight it in the table.
2. Press **P** to change its price, or **S** to correct its stock count, and press **Enter** to confirm.

Use stock correction after a stocktake, or if an item has been misplaced.

### Adding an item manually

For items without a barcode (local publications, old books, self-published items, or anything the online lookup can't find):

1. Press **A**.
2. Fill in the details — only **Title** is required. Press **Tab** to move between fields: Title, Author, Publisher, Year, Price, Copies in stock.
3. Save. The system assigns a scannable barcode automatically and shows it on screen.
4. To print a label, run `python scripts/gen_barcode.py --sheet` from the terminal — this produces a print sheet including the new item.

The item is immediately available in the catalog and can be sold at the counter once the label is printed and stuck on.

### Logging a sale directly from the catalog

Selecting a single item and clicking **Log Sale** records one sale for that item without going through Counter mode — useful for a quick manual sale while you're already looking an item up. It opens the same Cash/Card choice as the counter (**C** / **K**, or **Esc** to cancel).

Press **Esc** to cancel the current entry, or to return to the launcher from the main catalog screen.

---

## Payments Mode — Sundry Payments

No PIN required. Use this for anything that isn't a counter sale — room hire, memberships, event bookings, and similar one-off payments.

1. Select a **Type** from the list (configured in `settings.yaml` under `payment_types`).
2. Enter the payer's **Name** (required) and the **Amount** in euros (required).
3. Choose **Cash** or **Card**.
4. Optionally add a **Reference** (a booking or membership number) and **Notes**.
5. Press **Record Payment**, or **Esc** to cancel.

Each entry is timestamped and appears in that day's `payments_YYYY-MM-DD.csv` report — it does not affect the book/item sales totals.

---

## Admin Mode — Sales, Reports, and Reconciliation

Admin mode is PIN protected. The PIN is set in `config/settings.yaml`.

Price changes, stock corrections, catalog browsing, and adding items live in **Intake Mode** (see above) — Admin mode is for sales history, reporting, and fixing data issues.

Press **1**, **2**, **3**, or **4** to navigate, or click the menu buttons.

### [1] Sales log

Shows every transaction from today in reverse order (most recent first), including:
- Time of sale
- Title
- Price
- Payment method (CASH / CARD / — if not recorded)

Highlight a sale and press **V** (with confirmation) to void it — voided sales are shown marked with ✗ and **[VOID]**. They remain in the log as an audit trail but are not counted in totals, and voiding a sale returns its stock to the catalog.

### [2] Send report

1. The screen shows whether the office share is connected, and where the report for the selected date will be written.
2. Pick **Today**, **Yesterday**, or type a date (`YYYY-MM-DD`) and press Enter.
3. Send the report. Four CSV files are written into a `YYYY/MM/` folder under the office share (or `sync/` locally if the share isn't available):
   - `sales_YYYY-MM-DD.csv` — every transaction with price and payment method
   - `payments_YYYY-MM-DD.csv` — sundry payments logged that day (room hire, memberships, etc.)
   - `summary_YYYY-MM-DD.csv` — totals including cash vs. card breakdown
   - `catalog_YYYY-MM-DD.csv` — full inventory: every item with price and stock count

### [3] Sales tally

Item-by-item sales totals — quantity, revenue, and cash/card split — for **today**, **this month**, or **all time**. Use this to see what's actually selling. Export the current view to CSV from the same screen.

### [4] Fix orphaned

Lists transactions that were recorded without a payment method (for example, if the till was interrupted mid-sale). Select one and assign **Cash** or **Card** to correct it retroactively.

Press **Esc** to return to the menu, or to the launcher from the main menu.

---

## In-House Barcodes (Postcards, Tour Tickets, etc.)

Items that don't have a commercial barcode can be given their own scannable barcode. This makes them work exactly like books at the counter — no number keys, just scan.

See the **Setup & Deployment** section below for how to create and print these.

---

## Setup & Deployment (Technical)

### First-time setup on a new machine

```bash
# Install the venv package if needed (Kubuntu/Ubuntu) — adjust the version to match your Python
sudo apt install python3.14-venv

# From inside the colophon/ folder:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x scripts/*.sh
```

The database (`db/bookshop.db`) is created automatically on first run. No separate database setup is needed.

### Moving to a new machine

Copy the entire `colophon/` folder. If you want to bring the catalog and sales history:

- Copy `db/bookshop.db` — this contains the full catalog and all sales records.
- The database upgrades itself on startup; no manual migration needed.

If starting fresh (e.g. a clean go-live), just copy the code folder without the `db/` folder. A new empty database will be created on first run.

### Quick-reference card

`README_LAUNCH.example.txt` is a short, printable cheat sheet meant to be copied to `README_LAUNCH.txt`, filled in with your shop's real PIN and contact details, and kept by the till for staff — it's not meant to be read as documentation on its own.

### Configuration

All settings are in `config/settings.yaml`. Open it in any text editor.

Key settings:

```yaml
admin:
  pin: "0000"                  # Change this

stock:
  low_stock_threshold: 2       # Warn when copies drop to this

office_sync:
  mount_path: "/mnt/office"    # Where the office share is mounted
  report_subdir: "bookshop_reports"

non_isbn_items:
  - name: "Postcard"
    price: 4.00
  - name: "Postcard (large)"
    price: 6.00
  - name: "Tour admission"
    price:                     # Leave blank = ask at counter
```

### In-house barcode generation

Items without commercial barcodes (postcards, tour tickets, prints, etc.) can be given their own scannable EAN-13 barcodes using the included script.

```bash
# Add an item and generate its barcode image
python scripts/gen_barcode.py --add "Postcard — example" --price 4.00

# Variable-price item (will prompt at counter)
python scripts/gen_barcode.py --add "Tour admission"

# List all registered in-house items
python scripts/gen_barcode.py --list

# Generate a printable A4 sheet of all barcodes
python scripts/gen_barcode.py --sheet
# → opens as barcodes/print_sheet.html — open in browser, Ctrl+P to print

# Reprint a single barcode (if label is lost)
python scripts/gen_barcode.py --regenerate 2
```

The `--sheet` command produces a self-contained HTML file. Open it in Firefox or Chrome and print at 100% scale on A4. Each barcode prints large enough to scan from the sheet — useful for testing before labels are cut and attached to items.

Barcodes use the `inhouse_prefix` set in `config/settings.yaml`, drawn from the GS1 in-store range — never conflicts with real ISBNs. Items are registered in the catalog automatically and tracked like any book.

### Office share (network mount)

The report system writes CSVs to a network share if one is mounted at `/mnt/office`. Configure it in `/etc/fstab` for automatic mounting:

**Samba (Windows share / NAS):**
```
//server-name/share  /mnt/office  cifs  credentials=/etc/colophon/smb-credentials,uid=1000,gid=1000,_netdev,nofail,x-systemd.automount  0  0
```

Put the username/password in `/etc/colophon/smb-credentials` instead of the fstab line itself (`username=... password=...` in fstab is world-readable by default):

```
username=your-username
password=your-password
```

```bash
sudo chmod 600 /etc/colophon/smb-credentials
sudo chown root:root /etc/colophon/smb-credentials
```

`nofail` matters: without it, a laptop can hang at boot when the NAS happens to be off or unreachable, which defeats the whole point of the `sync/` local fallback.

**NFS:**
```
server-name:/share   /mnt/office  nfs   defaults,_netdev,nofail  0  0
```

Then run `sudo mount -a` to mount immediately without rebooting.

If the mount is not available when a report is sent, files go to `sync/` locally and the Admin screen tells you so.

### Automating the daily report

The report can be sent manually via Admin → [2] Send report at any time. To also run it automatically at 23:00 each night, add a cron job:

```bash
crontab -e
```

Add these lines (adjust the path to match your installation):

```
0 23 * * * cd /path/to/colophon && .venv/bin/python -m app.summary >> logs/summary_cron.log 2>&1
5 23 * * * cd /path/to/colophon && .venv/bin/python -m app.backup  >> logs/backup_cron.log 2>&1
```

Redirecting output to a log file matters — cron discards stdout/stderr by default, so without this, a failure (e.g. a bad path, a missing dependency) fails silently every night with no record anywhere.

The second line runs a nightly database backup — see "Database backups" below.

### Database backups

`python -m app.backup` copies the live database using SQLite's own online backup API, which is safe to run even while the app is open (a plain file copy is not, and can silently produce a corrupt backup). It writes to `backups/` on the office share, or `sync/backups/` locally if the share isn't available, and automatically keeps only the most recent 14 daily backups. Before this existed, there was no backup of the shop's catalog and sales data at all beyond whatever CSV reports had already been sent.

---

## Keyboard Reference

Every mode shows its own active keys at the bottom of the screen — this table is a complete reference, including keys that only apply inside a sub-screen (e.g. the payment popup).

### Counter mode

| Key | Action |
|---|---|
| Scan trigger | Log scanned book or in-house item |
| **1** – **4** | Log a non-ISBN item (items without barcodes, as configured in `settings.yaml` — capped at 4 keyboard slots; the on-screen buttons support more) |
| **Ctrl+T** | Open Subtotal / Pay |
| **C** / **K** | Cash / Card (in the payment popup) |
| **Esc** | Skip / cancel the payment popup, or go back to the launcher |
| **Ctrl+Z** | Undo last item |
| **Ctrl+D** | Apply a discount |
| **Ctrl+Q** | Quit the whole program (from any mode) |

### Intake mode

Intake also handles catalog browsing and price/stock corrections — not just receiving deliveries.

| Key | Action |
|---|---|
| Scan trigger | Receive a delivery, or look up an item to select it |
| **P** | Set price for the selected item |
| **S** | Set stock count for the selected item |
| **+** / **=** | Receive additional stock for the selected item |
| **M** | Toggle mark on the selected item |
| **A** | Add an item manually |
| **C** / **K** | Cash / Card (in the Log Sale popup, after clicking Log Sale) |
| **Esc** | Cancel the current entry, or go back to the launcher |
| **Ctrl+Q** | Quit the whole program (from any mode) |

### Payments mode

| Key | Action |
|---|---|
| **Esc** | Back to launcher |
| **Ctrl+Q** | Quit the whole program (from any mode) |

### Admin mode

PIN protected. Price changes, stock corrections, and adding items now live in **Intake mode** — Admin mode covers sales history, reporting, and reconciliation.

| Key | Action |
|---|---|
| **1** | Sales log — view and void today's transactions |
| **2** | Send report — generate and send CSV reports to the office share |
| **3** | Sales tally — totals by item for today / this month / all time, with export |
| **4** | Fix orphaned — assign a missing cash/card payment method to old transactions (Cash/Card are buttons here, not keys) |
| **V** | Confirm void (in the void-confirmation popup) |
| **Esc** | Back to menu / launcher, or cancel the current popup |
| **Ctrl+Q** | Quit the whole program (from any mode) |

---

## Troubleshooting

**"command not found" when running launch.sh**
Run `chmod +x scripts/launch.sh` first.

**"python3-venv not available"**
Run `sudo apt install python3.14-venv` (adjust version number to match your Python).

**Book not found after scanning**
The system checks the local catalog first, then Open Library online. If it fails:
- Check the internet connection.
- Try scanning from a different angle (some barcodes scan better at an angle).
- If the book is a local/Irish publication it may not be in Open Library — add it via Intake mode (it will prompt for details if not found online).

**"Bad scan" message**
The barcode didn't pass checksum validation — the scan was incomplete or corrupted. Try again.

**Office share not connecting**
Check that the share is mounted (`ls /mnt/office`). If not, run `sudo mount -a` or reboot. Reports will save to `sync/` locally in the meantime.

**Prices missing in sales log**
A book was scanned but has no price set in the catalog. Go to Intake mode, find it, and press **P** to set a price.

**In-house barcode not recognised at counter**
The item was not registered via `gen_barcode.py --add` or Intake mode's **A** (Add Item). Register it first, then scan again.

**Need to add a book that has no barcode at all**
In Intake mode, press **A** to add it manually. The system will assign a barcode — print the label with `python scripts/gen_barcode.py --sheet`.
