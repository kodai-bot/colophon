# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_categories.py - Item categories: migration, backfill, helpers, report column
"""

import csv
import sqlite3
import pytest

from app.catalog import (
    _create_tables, add_item, get_item, create_category, rename_category,
    delete_category, move_category, set_category, list_categories,
    BOOKS_CATEGORY_ID,
)


# Catalog table as it was before v1.7.0 (no category_id column)
OLD_CATALOG = """
    CREATE TABLE catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT, barcode TEXT UNIQUE, title TEXT NOT NULL,
        author TEXT, publisher TEXT, year TEXT, price REAL, stock INTEGER DEFAULT 0,
        manual INTEGER DEFAULT 0, added_at TEXT, updated_at TEXT
    )
"""

OLD_ROWS = [
    ("9780571331475", "A Real Book"),
    ("2001916000013", "Rainbow-Card"),
    ("2001916000020", "Cottie-Print"),
    ("2001916000037", "Hawkwell Jewellery"),
]


@pytest.fixture
def old_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(OLD_CATALOG)
    conn.executemany("INSERT INTO catalog (barcode, title) VALUES (?, ?)", OLD_ROWS)
    conn.commit()
    return conn


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _categories_by_title(conn):
    return {
        r["title"]: r["category_id"]
        for r in conn.execute("SELECT title, category_id FROM catalog")
    }


def test_migration_backfills_existing_items(old_db):
    _create_tables(old_db)
    assert _categories_by_title(old_db) == {
        "A Real Book": 1, "Rainbow-Card": 2, "Cottie-Print": 3, "Hawkwell Jewellery": None,
    }


def test_migration_is_repeatable_and_keeps_staff_choices(old_db):
    _create_tables(old_db)
    # Staff move the jewellery to Prints and the card to Unsorted...
    set_category(["2001916000037"], 3, old_db)
    set_category(["2001916000013"], None, old_db)
    # ...and the next startup must not re-guess either of them.
    _create_tables(old_db)
    assert old_db.execute("SELECT COUNT(*) FROM catalog").fetchone()[0] == len(OLD_ROWS)
    assert old_db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 3
    cats = _categories_by_title(old_db)
    assert cats["Hawkwell Jewellery"] == 3
    assert cats["Rainbow-Card"] is None


def test_seeded_categories_in_order(db):
    assert [c["name"] for c in list_categories(db)] == ["Books", "Cards", "Prints"]


def test_create_category_rejects_blank_reserved_and_duplicates(db):
    for bad in ("", "   ", "cards", "CARDS", "Unsorted", "all"):
        with pytest.raises(ValueError):
            create_category(bad, db)
    cid = create_category("  Calendars ", db)
    assert [c["name"] for c in list_categories(db)][-1] == "Calendars"
    with pytest.raises(ValueError):
        create_category("calendars", db)
    assert cid > 3


def test_rename_allows_case_change_of_itself(db):
    assert rename_category(2, "CARDS", db) == "CARDS"
    with pytest.raises(ValueError):
        rename_category(2, "Prints", db)


def test_delete_category_moves_items_to_unsorted(db):
    cid = create_category("Calendars", db)
    add_item({"barcode": "2001916000044", "title": "Calendar", "author": None,
              "publisher": None, "year": None, "price": 10.0, "stock": 1,
              "manual": 1, "category_id": cid}, db)
    assert delete_category(cid, db) == 1
    assert get_item("2001916000044", db)["category_id"] is None
    with pytest.raises(ValueError):
        delete_category(BOOKS_CATEGORY_ID, db)


def test_move_category_swaps_order(db):
    move_category(3, -1, db)
    assert [c["name"] for c in list_categories(db)] == ["Books", "Prints", "Cards"]
    move_category(1, -1, db)  # already first: no change
    assert [c["name"] for c in list_categories(db)] == ["Books", "Prints", "Cards"]


def test_add_item_upsert_keeps_category_when_none_given(db):
    item = {"barcode": "9780571331475", "title": "Book", "author": None,
            "publisher": None, "year": None, "price": 5.0, "stock": 1, "manual": 0,
            "category_id": BOOKS_CATEGORY_ID}
    add_item(item, db)
    add_item({k: v for k, v in item.items() if k != "category_id"} | {"price": 6.0}, db)
    row = get_item("9780571331475", db)
    assert row["category_id"] == BOOKS_CATEGORY_ID
    assert row["price"] == 6.0


def test_set_category_reports_only_changes(db):
    for bc, title in (("2001916000013", "A"), ("2001916000020", "B")):
        add_item({"barcode": bc, "title": title, "author": None, "publisher": None,
                  "year": None, "price": 1.0, "stock": 1, "manual": 1,
                  "category_id": 2 if title == "A" else None}, db)
    changed = set_category(["2001916000013", "2001916000020"], 2, db)
    assert changed == [("2001916000020", None)]


def test_catalog_csv_has_category_as_last_column(tmp_path):
    from app.summary import write_daily_report
    from app.catalog import get_db

    config = {
        "database": {"path": str(tmp_path / "bookshop.db")},
        "office_sync": {
            "mount_path": str(tmp_path / "nonexistent_mount"),
            "report_subdir": "reports",
            "fallback_local": str(tmp_path / "sync") + "/",
        },
        "ui": {"barcode_label": "ISBN", "creator_label": "Author", "vendor_label": "Publisher"},
    }
    conn = get_db(config)
    add_item({"barcode": "2001916000013", "title": "Rainbow", "author": None,
              "publisher": "Cuala", "year": None, "price": 6.0, "stock": 3,
              "manual": 1, "category_id": 2}, conn)

    class _NullLogger:
        def info(self, *a, **k): pass

    report_dir = write_daily_report("2026-10-07", config, _NullLogger())
    with open(report_dir / "catalog_2026-10-07.csv", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["isbn", "title", "author", "publisher", "year", "price", "stock", "category"]
    assert rows[1][-1] == "Cards"
