# SPDX-License-Identifier: AGPL-3.0-or-later
"""
logger.py - Main scanner input loop and sale recording.

Run this at the shop counter. The barcode scanner acts as a keyboard —
each scan sends the barcode as a string followed by Enter.

Usage:
    python -m app.logger
"""

import sys
import sqlite3
from datetime import datetime
from app.utils import load_config, get_logger, timestamp_now
from app.catalog import get_db, resolve_barcode, decrement_stock


def record_sale(barcode: str, title: str, price: float | None,
                conn: sqlite3.Connection,
                transaction_id: str | None = None) -> int:
    """Write a sale record. Returns the new row ID."""
    cur = conn.execute("""
        INSERT INTO sales (barcode, title, quantity, price, sold_at, transaction_id)
        VALUES (?, ?, 1, ?, ?, ?)
    """, (barcode, title, price, timestamp_now(), transaction_id))
    conn.commit()
    return cur.lastrowid


def void_last_sale(conn: sqlite3.Connection, logger=None) -> dict | None:
    """
    Void the most recent non-voided sale from today.
    Restores stock for barcode items. Returns the voided sale dict, or None
    if there is nothing to undo.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute("""
        SELECT * FROM sales
        WHERE DATE(sold_at) = ? AND voided = 0
        ORDER BY sold_at DESC LIMIT 1
    """, (today,)).fetchone()

    if not row:
        return None

    sale = dict(row)
    conn.execute("UPDATE sales SET voided = 1 WHERE id = ?", (sale["id"],))

    if sale.get("barcode"):
        qty = sale.get("quantity") or 1
        conn.execute("""
            UPDATE catalog SET stock = stock + ?, updated_at = ?
            WHERE barcode = ?
        """, (qty, timestamp_now(), sale["barcode"]))

    conn.commit()

    if logger:
        logger.info(f"Voided sale: id={sale['id']} '{sale.get('title')}'")

    return sale


def prompt_price(title: str) -> float | None:
    """Ask staff to enter price if not in catalog."""
    try:
        val = input(f"  Enter price for '{title}' (or Enter to skip): ").strip()
        return float(val) if val else None
    except ValueError:
        return None


def handle_unknown_barcode(barcode: str, conn: sqlite3.Connection, logger) -> dict | None:
    """
    Barcode not found anywhere — offer manual entry.
    Returns a minimal item dict or None if skipped.
    """
    print(f"\n  ⚠  Barcode {barcode} not found in catalog.")
    print("  Options:")
    print("  [m] Enter details manually")
    print("  [s] Skip this scan")
    choice = input("  Choice: ").strip().lower()

    if choice != "m":
        logger.info(f"Skipped unknown barcode: {barcode}")
        return None

    title = input("  Title: ").strip() or "Unknown Title"
    author = input("  Author / Creator: ").strip()
    year = input("  Year: ").strip()
    price_str = input("  Price: ").strip()
    price = float(price_str) if price_str else None

    item = {
        "barcode": barcode,
        "title": title,
        "author": author,
        "publisher": "",
        "year": year,
        "price": price,
        "stock": 1,
        "manual": 1,
    }
    return item


def run_logger():
    """Main loop — listen for scanner input and process sales."""
    config = load_config()
    logger = get_logger("logger", config)
    conn = get_db(config)
    low_threshold = config["stock"]["low_stock_threshold"]

    print("\n📦 Logger — ready to scan")
    print("   Scan a barcode, or type 'q' to quit\n")

    while True:
        try:
            raw = input("Scan: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Exiting logger.")
            break

        if raw.lower() == "q":
            print("  Goodbye.")
            break

        if not raw:
            continue

        barcode = raw

        item = resolve_barcode(barcode, conn, config, logger)

        if item is None:
            item = handle_unknown_barcode(barcode, conn, logger)
            if item is None:
                continue
            from app.catalog import add_item
            add_item(item, conn)

        title = item["title"]
        price = item.get("price")

        if price is None:
            price = prompt_price(title)

        print(f"\n  ✓  {title}")
        if item.get("author"):
            print(f"     {item['author']}")
        print(f"     Price: {'€{:.2f}'.format(price) if price else 'not recorded'}")
        confirm = input("  Log sale? [Y/n]: ").strip().lower()

        if confirm in ("", "y"):
            record_sale(barcode, title, price, conn)
            new_stock = decrement_stock(barcode, conn)
            logger.info(f"Sale recorded: {barcode} '{title}' — stock now {new_stock}")
            print(f"  Sale logged. Stock remaining: {new_stock}")
            if new_stock <= low_threshold:
                print(f"  ⚠  Low stock alert: only {new_stock} left!")
        else:
            print("  Sale cancelled.")

        print()


if __name__ == "__main__":
    run_logger()
