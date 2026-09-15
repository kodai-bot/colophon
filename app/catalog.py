# SPDX-License-Identifier: AGPL-3.0-or-later
"""
catalog.py - Barcode lookup, local catalog management, stock tracking
"""

import sqlite3
import requests
from pathlib import Path
from app.utils import load_config, get_logger, timestamp_now


INHOUSE_PREFIX = "2000001"  # default; overridden by config["catalog"]["inhouse_prefix"]


def get_inhouse_prefix(config: dict) -> str:
    return config.get("catalog", {}).get("inhouse_prefix", INHOUSE_PREFIX)


def ean13_check_digit(twelve: str) -> str:
    """Return the EAN-13 check digit for a 12-digit string."""
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(twelve))
    return str((10 - (total % 10)) % 10)


def make_inhouse_barcode(item_number: int, prefix: str = INHOUSE_PREFIX) -> str:
    """Return a full 13-digit in-house EAN-13 code for a given item number."""
    twelve = f"{prefix}{item_number:05d}"
    return twelve + ean13_check_digit(twelve)


def next_inhouse_number(conn: sqlite3.Connection, prefix: str = INHOUSE_PREFIX) -> int:
    """Return the next unused in-house item number."""
    rows = conn.execute(
        "SELECT barcode FROM catalog WHERE barcode LIKE ? ORDER BY barcode",
        (prefix + "%",)
    ).fetchall()
    used = set()
    for row in rows:
        try:
            used.add(int(row["barcode"][len(prefix):len(prefix) + 5]))
        except (ValueError, IndexError):
            pass
    n = 1
    while n in used:
        n += 1
    return n


def is_valid_barcode(code: str) -> bool:
    """Return True if code passes EAN-13, ISBN-13, or ISBN-10 checksum."""
    code = code.strip().replace("-", "").replace(" ", "")
    if len(code) == 13 and code.isdigit():
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(code))
        return total % 10 == 0
    if len(code) == 10 and code[:9].isdigit():
        last = code[9].upper()
        if last.isdigit() or last == "X":
            total = sum(int(d) * (10 - i) for i, d in enumerate(code[:9]))
            total += 10 if last == "X" else int(last)
            return total % 11 == 0
    return False


def get_db(config: dict) -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating tables if needed."""
    db_path = Path(config["database"]["path"])
    db_path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    """Create catalog and sales tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS catalog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode     TEXT UNIQUE,
            title       TEXT NOT NULL,
            author      TEXT,
            publisher   TEXT,
            year        TEXT,
            price       REAL,
            stock       INTEGER DEFAULT 0,
            manual      INTEGER DEFAULT 0,
            added_at    TEXT,
            updated_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS sales (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode        TEXT,
            title          TEXT,
            quantity       INTEGER DEFAULT 1,
            price          REAL,
            sold_at        TEXT,
            voided         INTEGER DEFAULT 0,
            payment_method TEXT,
            transaction_id TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            synced_at   TEXT,
            report_path TEXT,
            status      TEXT
        );

        CREATE TABLE IF NOT EXISTS payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT NOT NULL,
            location     TEXT NOT NULL DEFAULT 'BOOKSHOP',
            payment_type TEXT NOT NULL,
            payer_name   TEXT NOT NULL,
            description  TEXT,
            amount       REAL NOT NULL,
            reference    TEXT,
            logged_by    TEXT DEFAULT 'counter',
            payment_method TEXT
        );
    """)
    conn.commit()
    # Migrations: add or rename columns for databases created before this version
    for migration in [
        "ALTER TABLE sales ADD COLUMN voided INTEGER DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN payment_method TEXT",
        "ALTER TABLE sales ADD COLUMN transaction_id TEXT",
        "ALTER TABLE payments ADD COLUMN payment_method TEXT",
        # Rename isbn → barcode (SQLite >= 3.25)
        "ALTER TABLE catalog RENAME COLUMN isbn TO barcode",
        "ALTER TABLE sales RENAME COLUMN isbn TO barcode",
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass  # column already exists or already renamed


def lookup_openlibrary(barcode: str, config: dict, logger) -> dict | None:
    """Query Open Library API for item metadata by ISBN/barcode."""
    url = config["api"]["open_library_url"]
    params = {
        "bibkeys": f"ISBN:{barcode}",
        "format": "json",
        "jscmd": "data"
    }
    try:
        r = requests.get(url, params=params,
                         timeout=config["api"]["timeout_seconds"])
        r.raise_for_status()
        data = r.json()
        key = f"ISBN:{barcode}"
        if key not in data:
            return None
        book = data[key]
        return {
            "barcode": barcode,
            "title": book.get("title", "Unknown Title"),
            "author": ", ".join(a["name"] for a in book.get("authors", [])),
            "publisher": ", ".join(p["name"] for p in book.get("publishers", [])),
            "year": book.get("publish_date", ""),
        }
    except Exception as e:
        logger.warning(f"Open Library lookup failed for {barcode}: {e}")
        return None


def get_item(barcode: str, conn: sqlite3.Connection) -> dict | None:
    """Look up an item in the local catalog by barcode."""
    row = conn.execute(
        "SELECT * FROM catalog WHERE barcode = ?", (barcode,)
    ).fetchone()
    return dict(row) if row else None


def add_item(item: dict, conn: sqlite3.Connection) -> None:
    """
    Insert or update an item in the catalog.
    item dict keys: barcode, title, author, publisher, year, price, stock, manual
    """
    now = timestamp_now()
    conn.execute("""
        INSERT INTO catalog (barcode, title, author, publisher, year, price, stock, manual, added_at, updated_at)
        VALUES (:barcode, :title, :author, :publisher, :year, :price, :stock, :manual, :added_at, :updated_at)
        ON CONFLICT(barcode) DO UPDATE SET
            title=excluded.title,
            author=excluded.author,
            publisher=excluded.publisher,
            year=excluded.year,
            price=excluded.price,
            stock=excluded.stock,
            updated_at=excluded.updated_at
    """, {**item, "added_at": now, "updated_at": now})
    conn.commit()


def decrement_stock(barcode: str, conn: sqlite3.Connection, qty: int = 1) -> int:
    """
    Reduce stock count for an item after a sale.
    Returns new stock level.
    """
    conn.execute("""
        UPDATE catalog SET stock = MAX(0, stock - ?), updated_at = ?
        WHERE barcode = ?
    """, (qty, timestamp_now(), barcode))
    conn.commit()
    row = conn.execute(
        "SELECT stock FROM catalog WHERE barcode = ?", (barcode,)
    ).fetchone()
    return row["stock"] if row else 0


def resolve_barcode(barcode: str, conn: sqlite3.Connection,
                    config: dict, logger) -> dict | None:
    """
    Main resolution function:
    1. Check local DB
    2. If not found and lookup_enabled, query Open Library
    3. If found via API, cache in local DB
    4. Return item dict or None
    """
    item = get_item(barcode, conn)
    if item:
        return item

    if not config.get("api", {}).get("lookup_enabled", True):
        return None

    logger.info(f"Barcode {barcode} not in local DB — querying Open Library")
    item = lookup_openlibrary(barcode, config, logger)
    if item:
        item.setdefault("price", None)
        item.setdefault("stock", 1)
        item.setdefault("manual", 0)
        add_item(item, conn)
        return item

    return None
