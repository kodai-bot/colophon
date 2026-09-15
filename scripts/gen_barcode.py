# SPDX-License-Identifier: AGPL-3.0-or-later
"""
gen_barcode.py — Generate in-house EAN-13 barcodes for shop items.

Barcode schema:  2  00  SSSS  XXXXX  C
                 │   │    │     │    └─ check digit (auto-calculated)
                 │   │    │     └─ 5-digit item number
                 │   │    └─ SSSS: your shop's identifier (inhouse_prefix in settings.yaml)
                 │   └─ 00 (category, reserved for future use)
                 └─ GS1 in-store prefix (never conflicts with real ISBNs)

Usage:
    # List all registered in-house items:
    python scripts/gen_barcode.py --list

    # Add a new item and generate its barcode image:
    python scripts/gen_barcode.py --add "Postcard — example" --price 4.00

    # Re-generate the barcode image for an existing item number:
    python scripts/gen_barcode.py --regenerate 1

    # Specify item number explicitly (instead of auto-incrementing):
    python scripts/gen_barcode.py --add "Tour Programme" --price 3.50 --number 10

Output:  barcodes/<item_number>_<name>.svg   (print-ready SVG)
"""

import argparse
import sys
import os

# Allow running as `python scripts/gen_barcode.py` from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from app.utils import load_config, timestamp_now
from app.catalog import (
    get_db, make_inhouse_barcode, next_inhouse_number, INHOUSE_PREFIX
)
from app.barcode import generate_svg, generate_sheet as _generate_sheet

OUTPUT_DIR = Path("barcodes")


def make_barcode_number(item_number: int) -> str:
    return make_inhouse_barcode(item_number)


def next_item_number(conn) -> int:
    return next_inhouse_number(conn)


def cmd_list(conn) -> None:
    rows = conn.execute(
        "SELECT barcode, title, price, stock FROM catalog WHERE barcode LIKE ? ORDER BY barcode",
        (INHOUSE_PREFIX + "%",)
    ).fetchall()
    if not rows:
        print("No in-house items registered yet.")
        return
    print(f"\n{'#':<6}  {'Barcode':<15}  {'Name':<32}  {'Price':>7}  {'Stock':>5}")
    print("─" * 72)
    for row in rows:
        num = int(row["barcode"][len(INHOUSE_PREFIX):len(INHOUSE_PREFIX)+5])
        price_str = f"€{row['price']:.2f}" if row["price"] else "—"
        print(f"{num:<6}  {row['barcode']:<15}  {row['title']:<32}  {price_str:>7}  {row['stock']:>5}")
    print()


def cmd_add(conn, config, name: str, price: float | None, number: int | None) -> None:
    item_number = number if number is not None else next_item_number(conn)
    barcode_number = make_barcode_number(item_number)

    # Check for collision
    existing = conn.execute(
        "SELECT title FROM catalog WHERE barcode = ?", (barcode_number,)
    ).fetchone()
    if existing:
        print(f"⚠  Item #{item_number} already exists: '{existing['title']}'")
        print(f"   Use --regenerate {item_number} to re-generate its barcode image.")
        sys.exit(1)

    # Register in catalog
    conn.execute("""
        INSERT INTO catalog (barcode, title, author, price, stock, manual, added_at, updated_at)
        VALUES (?, ?, ?, ?, 99, 1, ?, ?)
    """, (barcode_number, name, "In-house", price, timestamp_now(), timestamp_now()))
    conn.commit()

    svg_path = generate_svg(barcode_number, name, price)

    print(f"\n✦  Item registered and barcode generated")
    print(f"   Name:     {name}")
    print(f"   Barcode:  {barcode_number}  (item #{item_number:05d})")
    print(f"   Price:    {'€' + f'{price:.2f}' if price else 'not set (will prompt at counter)'}")
    print(f"   SVG:      {svg_path}")
    print(f"\n   Print {svg_path} and stick it on the item.")
    print(f"   The scanner will recognise it immediately.\n")


def cmd_regenerate(conn, number: int) -> None:
    barcode_number = make_barcode_number(number)
    row = conn.execute(
        "SELECT title, price FROM catalog WHERE barcode = ?", (barcode_number,)
    ).fetchone()
    if not row:
        print(f"⚠  No item #{number} found. Use --add to create it first.")
        sys.exit(1)

    svg_path = generate_svg(barcode_number, row["title"], row["price"])
    print(f"✦  Barcode regenerated: {svg_path}")


def cmd_sheet(conn, config) -> None:
    """Generate a self-contained printable HTML sheet of all in-house barcodes."""
    count = conn.execute(
        "SELECT COUNT(*) FROM catalog WHERE isbn LIKE ?", (INHOUSE_PREFIX + "%",)
    ).fetchone()[0]
    if not count:
        print("No in-house items registered yet. Use --add first.")
        return
    shop_name = config.get("shop", {}).get("name", "Bookshop")
    sheet_path = _generate_sheet(conn, INHOUSE_PREFIX, shop_name)
    print(f"✦  Print sheet written to: {sheet_path}")
    print(f"   Open in a browser and print (Ctrl+P).")
    print(f"   Set paper size A4, margins normal, scale 100%.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate in-house EAN-13 barcodes for shop items"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all in-house items")
    group.add_argument("--add", metavar="NAME", help="Add a new item and generate barcode")
    group.add_argument("--regenerate", metavar="N", type=int,
                       help="Re-generate barcode image for item number N")
    group.add_argument("--sheet", action="store_true",
                       help="Generate a printable HTML sheet of all in-house barcodes")

    parser.add_argument("--price", type=float, default=None,
                        help="Price in euros (omit for variable-price items)")
    parser.add_argument("--number", type=int, default=None,
                        help="Override item number (default: auto-increment)")

    args = parser.parse_args()

    config = load_config()
    conn = get_db(config)

    if args.list:
        cmd_list(conn)
    elif args.add:
        cmd_add(conn, config, args.add, args.price, args.number)
    elif args.regenerate is not None:
        cmd_regenerate(conn, args.regenerate)
    elif args.sheet:
        cmd_sheet(conn, config)


if __name__ == "__main__":
    main()
