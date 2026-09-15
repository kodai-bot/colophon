# SPDX-License-Identifier: AGPL-3.0-or-later
"""
summary.py - Daily sales reports and office sync.

Generates CSV reports and writes them to the mounted office share,
or to sync/ locally if the mount is unavailable.

Usage:
    python -m app.summary              # report for today
    python -m app.summary --date 2025-06-01
"""

import csv
import argparse
from datetime import datetime
from pathlib import Path
from app.utils import load_config, get_logger, get_report_path, write_csv, format_date
from app.catalog import get_db


def get_daily_payments(date_str: str, conn) -> list[dict]:
    """Fetch all payments for a given date (YYYY-MM-DD)."""
    rows = conn.execute("""
        SELECT timestamp, location, payment_type, payer_name, description, amount, reference
        FROM payments
        WHERE DATE(timestamp) = ?
        ORDER BY timestamp
    """, (date_str,)).fetchall()
    return [dict(r) for r in rows]


def get_daily_sales(date_str: str, conn) -> list[dict]:
    """Fetch all non-voided sales for a given date (YYYY-MM-DD)."""
    rows = conn.execute("""
        SELECT barcode, title, quantity, price, sold_at, payment_method, transaction_id
        FROM sales
        WHERE DATE(sold_at) = ? AND voided = 0
        ORDER BY sold_at
    """, (date_str,)).fetchall()
    return [dict(r) for r in rows]


def get_catalog(conn) -> list[dict]:
    """Fetch full catalog sorted by title."""
    rows = conn.execute("""
        SELECT barcode, title, author, publisher, year, price, stock
        FROM catalog
        ORDER BY title
    """).fetchall()
    return [dict(r) for r in rows]


def get_low_stock(threshold: int, conn) -> list[dict]:
    """Fetch all catalog items at or below the low stock threshold."""
    rows = conn.execute("""
        SELECT barcode, title, author, stock
        FROM catalog
        WHERE stock <= ?
        ORDER BY stock, title
    """, (threshold,)).fetchall()
    return [dict(r) for r in rows]


def get_sales_tally(conn, start_date: str, end_date: str | None = None,
                    inhouse_prefix: str = "2000001") -> list[dict]:
    """
    Return sales grouped by title for a date range, sorted by qty descending.
    Adds an 'item_type' key: 'Book' for ISBN items, 'In-house' for everything else.
    end_date defaults to start_date (single day).
    """
    if end_date is None:
        end_date = start_date
    rows = conn.execute("""
        SELECT
            s.barcode,
            s.title,
            SUM(s.quantity)                                                                          AS qty,
            SUM(COALESCE(s.price, 0) * s.quantity)                                                   AS revenue,
            SUM(CASE WHEN s.payment_method = 'cash' THEN COALESCE(s.price, 0) * s.quantity ELSE 0 END) AS cash,
            SUM(CASE WHEN s.payment_method = 'card' THEN COALESCE(s.price, 0) * s.quantity ELSE 0 END) AS card
        FROM sales s
        WHERE DATE(s.sold_at) BETWEEN ? AND ? AND s.voided = 0
        GROUP BY s.barcode, s.title
        ORDER BY qty DESC, s.title
    """, (start_date, end_date)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        bc = d.get("barcode") or ""
        d["item_type"] = "In-house" if bc.startswith(inhouse_prefix) else "Book"
        result.append(d)
    return result


def write_tally_csv(rows: list[dict], filepath: Path) -> None:
    write_csv(
        filepath,
        [{
            "type":    r["item_type"],
            "title":   r["title"],
            "qty":     r["qty"],
            "revenue": round(r["revenue"], 2),
            "cash":    round(r["cash"], 2),
            "card":    round(r["card"], 2),
        } for r in rows],
        fieldnames=["type", "title", "qty", "revenue", "cash", "card"],
    )


def get_sales_summary(sales: list[dict]) -> dict:
    """Compute summary stats from a list of sale records."""
    total_items = sum(s["quantity"] for s in sales)
    total_revenue = sum((s["price"] or 0) * s["quantity"] for s in sales)
    cash_revenue = sum(
        (s["price"] or 0) * s["quantity"]
        for s in sales if s.get("payment_method") == "cash"
    )
    card_revenue = sum(
        (s["price"] or 0) * s["quantity"]
        for s in sales if s.get("payment_method") == "card"
    )
    return {
        "total_transactions": len(sales),
        "total_items_sold": total_items,
        "total_revenue": round(total_revenue, 2),
        "cash_revenue": round(cash_revenue, 2),
        "card_revenue": round(card_revenue, 2),
    }


def write_daily_report(date_str: str, config: dict, logger) -> Path:
    """
    Generate and write the daily sales CSV report.
    Returns path where the file was written.
    """
    conn = get_db(config)
    sales = get_daily_sales(date_str, conn)
    summary = get_sales_summary(sales)
    catalog = get_catalog(conn)

    ui = config.get("ui", {})
    barcode_label = ui.get("barcode_label", "barcode").lower().replace(" ", "_")
    creator_label = ui.get("creator_label", "author").lower()
    vendor_label = ui.get("vendor_label", "publisher").lower()

    report_dir = get_report_path(config, date_str)

    # Daily sales detail — use configured barcode label as column header
    sales_file = report_dir / f"sales_{date_str}.csv"
    write_csv(
        sales_file,
        sales,
        fieldnames=["transaction_id", "barcode", "title", "quantity", "price", "payment_method", "sold_at"]
    )

    # Sundry payments
    payments = get_daily_payments(date_str, conn)
    payments_file = report_dir / f"payments_{date_str}.csv"
    write_csv(
        payments_file,
        payments,
        fieldnames=["timestamp", "location", "payment_type", "payer_name",
                    "description", "amount", "reference"]
    )
    logger.info(f"Payments report: {len(payments)} records")

    # Summary row
    summary_file = report_dir / f"summary_{date_str}.csv"
    write_csv(
        summary_file,
        [summary],
        fieldnames=["total_transactions", "total_items_sold", "total_revenue",
                    "cash_revenue", "card_revenue"]
    )

    # Full catalog / inventory
    catalog_file = report_dir / f"catalog_{date_str}.csv"
    remapped_catalog = [
        {barcode_label: r["barcode"], "title": r["title"],
         creator_label: r["author"], vendor_label: r["publisher"],
         "year": r["year"], "price": r["price"], "stock": r["stock"]}
        for r in catalog
    ]
    write_csv(
        catalog_file,
        remapped_catalog,
        fieldnames=[barcode_label, "title", creator_label, vendor_label, "year", "price", "stock"]
    )
    logger.info(f"Catalog export: {len(catalog)} items")

    logger.info(
        f"Daily report written to {report_dir} — "
        f"{summary['total_transactions']} sales, "
        f"€{summary['total_revenue']} revenue"
    )

    # Log sync to DB
    conn.execute("""
        INSERT INTO sync_log (synced_at, report_path, status)
        VALUES (?, ?, ?)
    """, (datetime.now().isoformat(), str(report_dir), "ok"))
    conn.commit()

    return report_dir


def main():
    parser = argparse.ArgumentParser(description="Generate daily sales report")
    parser.add_argument(
        "--date",
        default=format_date(),
        help="Date to report on (YYYY-MM-DD), defaults to today"
    )
    args = parser.parse_args()

    config = load_config()
    logger = get_logger("summary", config)
    report_dir = write_daily_report(args.date, config, logger)
    print(f"Reports written to: {report_dir}")


if __name__ == "__main__":
    main()
