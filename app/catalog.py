# SPDX-License-Identifier: AGPL-3.0-or-later
"""
catalog.py - Barcode lookup, local catalog management, stock tracking
"""

import sqlite3
import requests
from pathlib import Path
from app.utils import load_config, get_logger, timestamp_now


INHOUSE_PREFIX = "2000001"  # default; overridden by config["catalog"]["inhouse_prefix"]

# Seeded categories. Ids are fixed so code can refer to Books directly; staff
# can rename them in Admin but not delete them. NULL category_id = Unsorted.
BOOKS_CATEGORY_ID = 1
DEFAULT_CATEGORIES = [(1, "Books"), (2, "Cards"), (3, "Prints")]
UNSORTED = "unsorted"      # category filter / picker key for items with no category
RETIRED = "retired"        # category filter for items taken off the list (see remove_item)


def get_inhouse_prefix(config: dict) -> str:
    return config.get("catalog", {}).get("inhouse_prefix", INHOUSE_PREFIX)


def ean13_check_digit(twelve: str) -> str:
    """Return the EAN-13 check digit for a 12-digit string."""
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(twelve))
    return str((10 - (total % 10)) % 10)


def validate_inhouse_prefix(prefix: str) -> None:
    """
    Raise ValueError if prefix isn't in the GS1 restricted-circulation range
    (7 digits, starting with 20-29) used for in-store barcodes that never
    conflict with real ISBNs/EANs.
    """
    if not (prefix.isdigit() and len(prefix) == 7 and 20 <= int(prefix[:2]) <= 29):
        raise ValueError(
            f"catalog.inhouse_prefix {prefix!r} in config/settings.yaml is not in the "
            "GS1 restricted-circulation range — it must be 7 digits starting with "
            "20-29 (e.g. '2000001')."
        )


def make_inhouse_barcode(item_number: int, prefix: str = INHOUSE_PREFIX) -> str:
    """Return a full 13-digit in-house EAN-13 code for a given item number."""
    validate_inhouse_prefix(prefix)
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


def normalize_barcode(code: str) -> str | None:
    """
    Normalize scanned or typed input to a 13-digit EAN-13 code.

    Handles three real-world cases beyond a plain 13-digit EAN-13:
    - A 5-digit price add-on some scanners append, sending 18 digits total
      (13 + 5) — the first 13 are used if they pass the EAN-13 checksum.
    - ISBN-10 input — converted to ISBN-13 (978 prefix, recomputed check digit).
    Returns None if nothing here resolves to a valid code.
    """
    code = code.strip().replace("-", "").replace(" ", "")

    if len(code) == 18 and code.isdigit():
        code = code[:13]

    if len(code) == 13 and code.isdigit():
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(code))
        return code if total % 10 == 0 else None

    if len(code) == 10 and code[:9].isdigit():
        last = code[9].upper()
        if last.isdigit() or last == "X":
            total = sum(int(d) * (10 - i) for i, d in enumerate(code[:9]))
            total += 10 if last == "X" else int(last)
            if total % 11 == 0:
                twelve = "978" + code[:9]
                return twelve + ean13_check_digit(twelve)

    return None


def get_db(config: dict) -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating tables if needed."""
    db_path = Path(config["database"]["path"])
    db_path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # WAL + busy_timeout let the TUI and the nightly cron report process share
    # the DB without "database is locked" errors.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    _create_counter_items(conn, config.get("non_isbn_items") or [])
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

        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
            sort_order  INTEGER,
            created_at  TEXT
        );
    """)
    for cat_id, name in DEFAULT_CATEGORIES:
        conn.execute(
            "INSERT OR IGNORE INTO categories (id, name, sort_order, created_at)"
            " VALUES (?, ?, ?, ?)",
            (cat_id, name, cat_id, timestamp_now()),
        )
    conn.commit()
    # Migrations: add or rename columns for databases created before this version
    for migration in [
        "ALTER TABLE sales ADD COLUMN voided INTEGER DEFAULT 0",
        "ALTER TABLE sales ADD COLUMN payment_method TEXT",
        "ALTER TABLE sales ADD COLUMN transaction_id TEXT",
        "ALTER TABLE payments ADD COLUMN payment_method TEXT",
        "ALTER TABLE catalog ADD COLUMN needs_recount INTEGER DEFAULT 0",
        "ALTER TABLE catalog ADD COLUMN retired INTEGER DEFAULT 0",
        # Rename isbn → barcode (SQLite >= 3.25)
        "ALTER TABLE catalog RENAME COLUMN isbn TO barcode",
        "ALTER TABLE sales RENAME COLUMN isbn TO barcode",
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass  # column already exists or already renamed

    # Categories (v1.7.0). The backfill runs only in the same step that adds
    # the column, so it sorts the pre-existing catalog once and never
    # second-guesses a category staff have set (or left Unsorted) since.
    try:
        conn.execute(
            "ALTER TABLE catalog ADD COLUMN category_id INTEGER REFERENCES categories(id)"
        )
    except Exception:
        pass  # column already exists
    else:
        _backfill_categories(conn)
        conn.commit()


def _backfill_categories(conn: sqlite3.Connection) -> None:
    """Best-guess categories for items that predate them.

    Real barcodes (anything outside the GS1 in-store range 20-29) are books.
    In-house items are sorted by the "-Card" / "-Print" that staff had been
    adding to titles; anything else is left Unsorted for staff to sort.
    """
    conn.execute(
        "UPDATE catalog SET category_id = 1"
        " WHERE category_id IS NULL AND barcode NOT GLOB '2[0-9]*'"
    )
    conn.execute(
        "UPDATE catalog SET category_id = 2"
        " WHERE category_id IS NULL AND LOWER(title) LIKE '%card%'"
    )
    conn.execute(
        "UPDATE catalog SET category_id = 3"
        " WHERE category_id IS NULL AND LOWER(title) LIKE '%print%'"
    )


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
    item dict keys: barcode, title, author, publisher, year, price, stock, manual,
    and optionally category_id (an update without one keeps the existing category)
    """
    now = timestamp_now()
    conn.execute("""
        INSERT INTO catalog (barcode, title, author, publisher, year, price, stock, manual,
                             category_id, added_at, updated_at)
        VALUES (:barcode, :title, :author, :publisher, :year, :price, :stock, :manual,
                :category_id, :added_at, :updated_at)
        ON CONFLICT(barcode) DO UPDATE SET
            title=excluded.title,
            author=excluded.author,
            publisher=excluded.publisher,
            year=excluded.year,
            price=excluded.price,
            stock=excluded.stock,
            category_id=COALESCE(excluded.category_id, catalog.category_id),
            updated_at=excluded.updated_at
    """, {"category_id": None, **item, "added_at": now, "updated_at": now})
    conn.commit()


def list_catalog(conn: sqlite3.Connection, term: str = "",
                 category_filter="all", by_stock: bool = False) -> list[sqlite3.Row]:
    """Catalog rows for browsing: in-stock items first, then out-of-stock
    (stock 0 or less), each group A–Z by title. term matches title, author
    or publisher. category_filter is "all", UNSORTED, RETIRED or a category
    id; retired items only appear under RETIRED. by_stock lists the most
    stock first instead (ties A–Z), which also leaves out-of-stock last."""
    where, params = [], []
    where.append("COALESCE(c.retired, 0) = 1" if category_filter == RETIRED
                 else "COALESCE(c.retired, 0) = 0")
    if term:
        like = f"%{term.lower()}%"
        where.append("(LOWER(c.title) LIKE ? OR LOWER(c.author) LIKE ?"
                     " OR LOWER(COALESCE(c.publisher, '')) LIKE ?)")
        params += [like, like, like]
    if category_filter == UNSORTED:
        where.append("c.category_id IS NULL")
    elif isinstance(category_filter, int):
        where.append("c.category_id = ?")
        params.append(category_filter)
    return conn.execute(f"""
        SELECT c.barcode, c.title, c.author, c.price, c.stock, c.needs_recount,
               COALESCE(k.name, 'Unsorted') AS category
        FROM catalog c
        LEFT JOIN categories k ON k.id = c.category_id
        WHERE {" AND ".join(where)}
        ORDER BY {"COALESCE(c.stock, 0) DESC" if by_stock else "(COALESCE(c.stock, 0) <= 0)"},
                 c.title
    """, params).fetchall()


def has_sales(barcode: str, conn: sqlite3.Connection) -> bool:
    """True if any sale (voided or not) was ever logged for this barcode."""
    return conn.execute(
        "SELECT 1 FROM sales WHERE barcode = ? LIMIT 1", (barcode,)
    ).fetchone() is not None


def remove_item(barcode: str, conn: sqlite3.Connection) -> str | None:
    """Take an item off the catalog list. An item that has never sold is
    deleted (it was a mistake); one with sales history is retired instead,
    so its sales still make sense. Returns "deleted", "retired" or None."""
    if not get_item(barcode, conn):
        return None
    if has_sales(barcode, conn):
        conn.execute(
            "UPDATE catalog SET retired = 1, updated_at = ? WHERE barcode = ?",
            (timestamp_now(), barcode),
        )
        result = "retired"
    else:
        conn.execute("DELETE FROM catalog WHERE barcode = ?", (barcode,))
        result = "deleted"
    conn.commit()
    return result


def restore_item(barcode: str, conn: sqlite3.Connection) -> None:
    """Put a retired item back on the catalog list."""
    conn.execute(
        "UPDATE catalog SET retired = 0, updated_at = ? WHERE barcode = ?",
        (timestamp_now(), barcode),
    )
    conn.commit()


# ── Categories ───────────────────────────────────────────────────────────────

def list_categories(conn: sqlite3.Connection) -> list[dict]:
    """All categories in display order, each with its item count."""
    rows = conn.execute("""
        SELECT c.id, c.name, c.sort_order, COUNT(cat.id) AS item_count
        FROM categories c
        LEFT JOIN catalog cat ON cat.category_id = c.id
        GROUP BY c.id
        ORDER BY c.sort_order, c.name
    """).fetchall()
    return [dict(r) for r in rows]


def get_category_name(category_id: int | None, conn: sqlite3.Connection) -> str:
    if category_id is None:
        return "Unsorted"
    row = conn.execute(
        "SELECT name FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    return row["name"] if row else "Unsorted"


def _clean_category_name(name: str, conn: sqlite3.Connection,
                         exclude_id: int | None = None) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("Category name can't be blank")
    if name.lower() in ("all", "unsorted"):
        raise ValueError(f"'{name}' is reserved")
    clash = conn.execute(
        "SELECT id FROM categories WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
        (name, exclude_id),
    ).fetchone()
    if clash:
        raise ValueError(f"There is already a category called '{name}'")
    return name


def create_category(name: str, conn: sqlite3.Connection) -> int:
    """Create a category at the end of the list. Raises ValueError on a
    blank, reserved or duplicate (case-insensitive) name. Returns its id."""
    name = _clean_category_name(name, conn)
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 1 FROM categories"
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO categories (name, sort_order, created_at) VALUES (?, ?, ?)",
        (name, next_order, timestamp_now()),
    )
    conn.commit()
    return cur.lastrowid


def rename_category(category_id: int, name: str, conn: sqlite3.Connection) -> str:
    name = _clean_category_name(name, conn, exclude_id=category_id)
    conn.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
    conn.commit()
    return name


def delete_category(category_id: int, conn: sqlite3.Connection) -> int:
    """Delete a staff-created category; its items become Unsorted.
    The seeded categories can't be deleted. Returns the number of items moved."""
    if category_id in {cid for cid, _ in DEFAULT_CATEGORIES}:
        raise ValueError("Books, Cards and Prints can be renamed but not deleted")
    moved = conn.execute(
        "UPDATE catalog SET category_id = NULL, updated_at = ? WHERE category_id = ?",
        (timestamp_now(), category_id),
    ).rowcount
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    return moved


def move_category(category_id: int, direction: int, conn: sqlite3.Connection) -> None:
    """Swap a category with its neighbour in display order (direction -1 or +1)."""
    ids = [c["id"] for c in list_categories(conn)]
    if category_id not in ids:
        return
    i = ids.index(category_id)
    j = i + direction
    if not 0 <= j < len(ids):
        return
    ids[i], ids[j] = ids[j], ids[i]
    for order, cid in enumerate(ids, start=1):
        conn.execute("UPDATE categories SET sort_order = ? WHERE id = ?", (order, cid))
    conn.commit()


def set_category(barcodes, category_id: int | None,
                 conn: sqlite3.Connection) -> list[tuple[str, int | None]]:
    """Set the category of one or more items (None = Unsorted).
    Returns [(barcode, old_category_id)] for items that actually changed."""
    now = timestamp_now()
    changed = []
    for barcode in barcodes:
        row = conn.execute(
            "SELECT category_id FROM catalog WHERE barcode = ?", (barcode,)
        ).fetchone()
        if row is None or row["category_id"] == category_id:
            continue
        conn.execute(
            "UPDATE catalog SET category_id = ?, updated_at = ? WHERE barcode = ?",
            (category_id, now, barcode),
        )
        changed.append((barcode, row["category_id"]))
    conn.commit()
    return changed


# ── Counter items (non-barcoded shortcut buttons) ────────────────────────────

MAX_COUNTER_SLOTS = 9          # number keys 1-9 at the counter
DEFAULT_COUNTER_SLOTS = 4
COUNTER_NAME_MAX = 30


def counter_slot_count(config: dict) -> int:
    """How many shortcut slots this till shows (config, clamped to 1-9).
    Per machine, because it depends on the counter screen's size."""
    try:
        n = int(config.get("counter_item_slots") or DEFAULT_COUNTER_SLOTS)
    except (TypeError, ValueError):
        n = DEFAULT_COUNTER_SLOTS
    return max(1, min(MAX_COUNTER_SLOTS, n))


def _create_counter_items(conn: sqlite3.Connection, seed_items: list) -> None:
    """Create the counter_items table (v1.8.0). Counter items used to live in
    settings.yaml (non_isbn_items); they are copied in once, when the table is
    first created, and edited in Admin from then on. Seeding only on creation
    means a slot staff have cleared is never refilled from the old config."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'counter_items'"
    ).fetchone()
    if exists:
        return
    conn.execute("""
        CREATE TABLE counter_items (
            slot        INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            price       REAL,
            updated_at  TEXT
        )
    """)
    for slot, item in enumerate(seed_items[:MAX_COUNTER_SLOTS], start=1):
        name = " ".join(str((item or {}).get("name") or "").split())
        if not name:
            continue
        conn.execute(
            "INSERT INTO counter_items (slot, name, price, updated_at) VALUES (?, ?, ?, ?)",
            (slot, name[:COUNTER_NAME_MAX], item.get("price"), timestamp_now()),
        )
    conn.commit()


def list_counter_items(conn: sqlite3.Connection, slots: int) -> list[dict]:
    """One dict per slot 1..slots: {slot, name, price}. Empty slots have
    name None. Items stored beyond `slots` are kept but not shown."""
    rows = {r["slot"]: r for r in conn.execute(
        "SELECT slot, name, price FROM counter_items WHERE slot <= ?", (slots,)
    )}
    return [
        {"slot": n, "name": rows[n]["name"] if n in rows else None,
         "price": rows[n]["price"] if n in rows else None}
        for n in range(1, slots + 1)
    ]


def parse_counter_price(raw: str) -> float | None:
    """'' -> None (staff enter the price at the counter). Accepts '20',
    '20.00', '€20', '20,50'. Raises ValueError on anything else."""
    raw = (raw or "").strip().lstrip("€").strip().replace(",", ".")
    if not raw:
        return None
    try:
        price = round(float(raw), 2)
    except ValueError:
        raise ValueError(f"'{raw}' isn't a price — use e.g. 20 or 4.50")
    if price <= 0 or price > 10000:
        raise ValueError("Price must be above €0 (leave blank to enter at the counter)")
    return price


def set_counter_item(slot: int, name: str, price: float | None,
                     conn: sqlite3.Connection) -> dict | None:
    """Fill or change a slot. Returns the old {name, price}, or None if the
    slot was empty. Raises ValueError on a bad slot or name."""
    if not 1 <= slot <= MAX_COUNTER_SLOTS:
        raise ValueError(f"No slot {slot}")
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("Name can't be blank (use Clear to empty a slot)")
    if len(name) > COUNTER_NAME_MAX:
        raise ValueError(f"Name is too long — {COUNTER_NAME_MAX} characters at most")
    old = conn.execute(
        "SELECT name, price FROM counter_items WHERE slot = ?", (slot,)
    ).fetchone()
    conn.execute("""
        INSERT INTO counter_items (slot, name, price, updated_at) VALUES (?, ?, ?, ?)
        ON CONFLICT(slot) DO UPDATE SET
            name = excluded.name, price = excluded.price, updated_at = excluded.updated_at
    """, (slot, name, price, timestamp_now()))
    conn.commit()
    return dict(old) if old else None


def clear_counter_item(slot: int, conn: sqlite3.Connection) -> dict | None:
    """Empty a slot. Returns what was in it, or None if already empty."""
    old = conn.execute(
        "SELECT name, price FROM counter_items WHERE slot = ?", (slot,)
    ).fetchone()
    conn.execute("DELETE FROM counter_items WHERE slot = ?", (slot,))
    conn.commit()
    return dict(old) if old else None


def swap_counter_slots(a: int, b: int, conn: sqlite3.Connection) -> None:
    """Swap the contents of two slots (either may be empty)."""
    if not (1 <= a <= MAX_COUNTER_SLOTS and 1 <= b <= MAX_COUNTER_SLOTS) or a == b:
        return
    # Park slot a at 0 so the primary key never clashes mid-swap.
    conn.execute("UPDATE counter_items SET slot = 0 WHERE slot = ?", (a,))
    conn.execute("UPDATE counter_items SET slot = ? WHERE slot = ?", (a, b))
    conn.execute("UPDATE counter_items SET slot = ? WHERE slot = 0", (b,))
    conn.commit()


def decrement_stock(barcode: str, conn: sqlite3.Connection, qty: int = 1) -> int:
    """
    Reduce stock count for an item after a sale.
    If stock was already at or below zero before this sale, flags the item
    as needing a manual recount instead of silently discarding the
    contradiction. Returns new stock level.

    Note: if qty > 1 oversells an item that was still in stock (e.g.
    stock=2, qty=5), the pre-update stock is >0 so needs_recount is not
    set — every current caller passes qty=1, so this doesn't arise today.
    """
    conn.execute("""
        UPDATE catalog
        SET stock = MAX(0, stock - ?),
            needs_recount = CASE WHEN stock <= 0 THEN 1 ELSE needs_recount END,
            updated_at = ?
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
        item.setdefault("category_id", BOOKS_CATEGORY_ID)
        add_item(item, conn)
        return item

    return None
