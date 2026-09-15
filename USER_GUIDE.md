# Colophon — User Guide

**Admin PIN:** set in `config/settings.yaml`.
Problems? Contact whoever administers this system for your shop.

> Colophon was originally built for and is used daily at the Yeats Society Bookshop, Sligo. This guide is written generically for any shop running it — screenshots and specific item names will differ from your own catalog.

---

## Overview

The system has three modes, all launched from the same startup screen:

| Mode | Who uses it | What it does |
|---|---|---|
| **Counter** | All staff | Scan books and items for sale, take payment |
| **Intake** | Stock volunteers | Scan in new deliveries, add books to the catalog |
| **Admin** | Managers | Change prices, correct stock, view sales, browse catalog, send reports |

---

## Starting the System

Double-click **launch.sh** on the desktop, or open a terminal and run:

```
./scripts/launch.sh
```

The launcher screen appears. Press **1**, **2**, or **3** to enter a mode, or click the button.

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

1. Press **Ctrl+P** (or click the green **Subtotal / Pay** button).
2. A box shows the number of items and the total amount.
3. Press **C** for cash or **K** for card.
4. The basket clears and the screen resets for the next customer.

> If the customer needs a moment (checking their wallet etc.), press **Esc** to close the payment box — the basket stays open.

### Undoing a mistake

Scanned the wrong book? Press **Ctrl+Z** immediately. This removes the last item from the basket and restores the stock count. You can press Ctrl+Z multiple times to remove more items.

Undo only works for sales made today.

### Leaving Counter mode

Press **Esc** or click **⌂ Home** to return to the launcher.

---

## Intake Mode — Receiving Stock

Use this mode when a delivery arrives or when adding books to the system for the first time.

### Scanning a delivery

1. Scan the barcode on the book.
2. **If the book is already in the system:** a quantity panel appears showing the current stock. Use **+** and **−** (or the buttons) to set how many copies arrived, then press **Enter** to confirm.
3. **If the book is new:** the system looks it up online (Open Library). If found, it shows the title, author, publisher and year, then a price entry box appears — type the price and press **Enter**. The book is added to the catalog.
4. **If not found online:** a message appears suggesting you add it via Admin mode (or try a different barcode orientation).

The session totals on the right keep a running count of books scanned and copies added.

Press **Esc** or **⌂ Home** when done.

---

## Admin Mode — Management Functions

Admin mode is PIN protected. The PIN is set in `config/settings.yaml`.

Press **1**, **2**, **3**, **4**, or **5** to navigate, or click the menu buttons.

### [1] Change a book price

1. Type part of the book title and press **Enter** to search.
2. The current price is shown.
3. Type the new price and press **Enter**.

### [2] Correct stock count

1. Search by title as above.
2. Type the correct number of copies in stock and press **Enter**.

Use this after a stocktake, or if you know a book has been misplaced.

### [3] View today's sales log

Shows every transaction from today in reverse order (most recent first), including:
- Time of sale
- Title
- Price
- Payment method (CASH / CARD / — if not recorded)

Voided sales are shown marked with ✗ and **[VOID]** — they remain in the log as an audit trail but are not counted in totals.

### [4] Send today's report to office

1. The screen shows whether the office share is connected or not.
2. Click **Send Report**.
3. Four CSV files are written:
   - `sales_YYYY-MM-DD.csv` — every transaction with price and payment method
   - `summary_YYYY-MM-DD.csv` — totals including cash vs. card breakdown
   - `catalog_YYYY-MM-DD.csv` — full inventory: every book with price and stock count
   - `low_stock_YYYY-MM-DD.csv` — items running low (if any)
4. If the office share is not available, files are saved locally to the `sync/` folder instead.

### [6] Add book manually

For books without a barcode (local publications, old books, self-published items):

1. Press **6** or click **Add book manually**.
2. Fill in the details — only **Title** is required. Press **Tab** to move between fields:
   - Title, Author, Publisher, Year, Price, Copies in stock
3. Click **✦ Save Book**.
4. The system assigns a scannable barcode automatically and shows it on screen.
5. To print a label, run `python scripts/gen_barcode.py --sheet` from the terminal — this produces a print sheet including the new book.

The book is immediately available in the catalog and can be sold at the counter once the label is printed and stuck on.

### [5] Browse catalog

Shows the full book catalog sorted A–Z. Use this to:
- See what's in the system and check stock levels
- Verify a book was added correctly after intake
- Check publisher and edition details for books with multiple editions

Type a title fragment in the search box and press **Enter** to filter. Press **Esc** to return to the menu.

Press **← Menu** or **Esc** to return to the menu from any section.

---

## In-House Barcodes (Postcards, Tour Tickets, etc.)

Items that don't have a commercial barcode can be given their own scannable barcode. This makes them work exactly like books at the counter — no number keys, just scan.

See the **Setup & Deployment** section below for how to create and print these.

---

## Setup & Deployment (Technical)

### First-time setup on a new machine

```bash
# Install the venv package if needed (Kubuntu/Ubuntu)
sudo apt install python3.14-venv

# From inside the bookshop_logger/ folder:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x scripts/*.sh
```

The database (`db/bookshop.db`) is created automatically on first run. No separate database setup is needed.

### Moving to a new machine

Copy the entire `bookshop_logger/` folder. If you want to bring the catalog and sales history:

- Copy `db/bookshop.db` — this contains the full catalog and all sales records.
- The database upgrades itself on startup; no manual migration needed.

If starting fresh (e.g. a clean go-live), just copy the code folder without the `db/` folder. A new empty database will be created on first run.

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
//server-name/share  /mnt/office  cifs  username=USER,password=PASS,uid=1000,gid=1000  0  0
```

**NFS:**
```
server-name:/share   /mnt/office  nfs   defaults  0  0
```

Then run `sudo mount -a` to mount immediately without rebooting.

If the mount is not available when a report is sent, files go to `sync/` locally and the Admin screen tells you so.

### Automating the daily report

The report can be sent manually via Admin → [4] at any time. To also run it automatically at 23:00 each night, add a cron job:

```bash
crontab -e
```

Add this line (adjust the path to match your installation):

```
0 23 * * * cd /path/to/Bookshop_App && .venv/bin/python -m app.summary
```

---

## Keyboard Reference

Every mode shows its own active keys at the bottom of the screen — this table is a complete reference, including keys that only apply inside a sub-screen (e.g. the payment popup).

### Counter mode

| Key | Action |
|---|---|
| Scan trigger | Log scanned book or in-house item |
| **1** – **4** | Log a non-ISBN item (items without barcodes, as configured in `settings.yaml`) |
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
| **4** | Fix orphaned — assign a missing cash/card payment method to old transactions |
| **C** / **K** | Cash / Card (when manually logging a sale, or fixing an orphaned transaction) |
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
A book was scanned but has no price set in the catalog. Go to Admin → [1] Change price and set it.

**In-house barcode not recognised at counter**
The item was not registered via `gen_barcode.py --add` or Admin → [6]. Register it first, then scan again.

**Need to add a book that has no barcode at all**
Use Admin → [6] Add book manually. The system will assign a barcode — print the label with `python scripts/gen_barcode.py --sheet`.
