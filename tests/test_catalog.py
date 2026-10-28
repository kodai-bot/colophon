# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_catalog.py - Tests for catalog module
"""

import sqlite3
import pytest
from app.catalog import (
    get_item, add_item, decrement_stock, _create_tables,
    is_valid_barcode, resolve_barcode, normalize_barcode, validate_inhouse_prefix,
    list_catalog, UNSORTED, RETIRED, remove_item, restore_item, has_sales,
)


@pytest.fixture
def in_memory_db():
    """Provide a fresh in-memory SQLite DB for each test."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


@pytest.fixture
def sample_item():
    return {
        "barcode": "9780571331475",
        "title": "Test Book",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "year": "2020",
        "price": 12.99,
        "stock": 5,
        "manual": 0,
    }


def test_add_and_retrieve_item(in_memory_db, sample_item):
    add_item(sample_item, in_memory_db)
    result = get_item("9780571331475", in_memory_db)
    assert result is not None
    assert result["title"] == "Test Book"
    assert result["author"] == "Test Author"


def test_item_not_found_returns_none(in_memory_db):
    result = get_item("0000000000000", in_memory_db)
    assert result is None


def test_decrement_stock(in_memory_db, sample_item):
    add_item(sample_item, in_memory_db)
    new_stock = decrement_stock("9780571331475", in_memory_db)
    assert new_stock == 4


def test_decrement_stock_does_not_go_negative(in_memory_db, sample_item):
    sample_item["stock"] = 0
    add_item(sample_item, in_memory_db)
    new_stock = decrement_stock("9780571331475", in_memory_db)
    assert new_stock == 0
    assert get_item("9780571331475", in_memory_db)["needs_recount"] == 1


def test_decrement_stock_does_not_flag_when_stock_positive(in_memory_db, sample_item):
    add_item(sample_item, in_memory_db)
    decrement_stock("9780571331475", in_memory_db)
    assert get_item("9780571331475", in_memory_db)["needs_recount"] == 0


def test_decrement_stock_preserves_existing_flag(in_memory_db, sample_item):
    add_item(sample_item, in_memory_db)
    in_memory_db.execute(
        "UPDATE catalog SET needs_recount = 1 WHERE barcode = ?",
        ("9780571331475",),
    )
    in_memory_db.commit()
    decrement_stock("9780571331475", in_memory_db)
    assert get_item("9780571331475", in_memory_db)["needs_recount"] == 1


def test_create_tables_migration_is_idempotent(in_memory_db, sample_item):
    _create_tables(in_memory_db)  # second call must not raise
    add_item(sample_item, in_memory_db)
    assert get_item("9780571331475", in_memory_db)["needs_recount"] == 0


def test_add_item_upserts_on_duplicate_barcode(in_memory_db, sample_item):
    add_item(sample_item, in_memory_db)
    sample_item["title"] = "Updated Title"
    add_item(sample_item, in_memory_db)
    result = get_item("9780571331475", in_memory_db)
    assert result["title"] == "Updated Title"


def test_is_valid_barcode_isbn13_valid():
    assert is_valid_barcode("9780571331475")
    assert is_valid_barcode("978-0-571-33147-5")


def test_is_valid_barcode_isbn13_invalid():
    assert not is_valid_barcode("9780571331476")  # wrong check digit
    assert not is_valid_barcode("123456789012")   # 12 digits
    assert not is_valid_barcode("abcdefghijklm")  # letters


def test_is_valid_barcode_isbn10_valid():
    assert is_valid_barcode("0306406152")
    assert is_valid_barcode("080442957X")


def test_is_valid_barcode_isbn10_invalid():
    assert not is_valid_barcode("0306406153")  # wrong check digit
    assert not is_valid_barcode("030640615")   # too short


def test_is_valid_barcode_garbage():
    assert not is_valid_barcode("")
    assert not is_valid_barcode("hello")
    assert not is_valid_barcode("12345")


def test_resolve_barcode_lookup_disabled(in_memory_db):
    """When lookup_enabled is false, unknown barcodes return None without API call."""
    config = {"api": {"lookup_enabled": False}}

    class _Logger:
        def info(self, *a): pass
        def warning(self, *a): pass

    result = resolve_barcode("9780571331475", in_memory_db, config, _Logger())
    assert result is None


def test_normalize_barcode_plain_ean13():
    assert normalize_barcode("9780571331475") == "9780571331475"


def test_normalize_barcode_strips_ean5_price_addon():
    """Some scanners send the 5-digit price add-on appended, as 18 digits total."""
    assert normalize_barcode("978057133147512345") == "9780571331475"


def test_normalize_barcode_rejects_bad_ean5_host():
    """If the first 13 digits don't check out, the whole scan is rejected."""
    assert normalize_barcode("978057133147612345") is None


def test_normalize_barcode_converts_isbn10_to_isbn13():
    assert normalize_barcode("0261102214") == "9780261102217"


def test_normalize_barcode_garbage_returns_none():
    assert normalize_barcode("not-a-barcode") is None


def test_validate_inhouse_prefix_accepts_gs1_range():
    validate_inhouse_prefix("2000001")  # should not raise
    validate_inhouse_prefix("2999999")  # should not raise


def test_validate_inhouse_prefix_rejects_outside_gs1_range():
    with pytest.raises(ValueError):
        validate_inhouse_prefix("9990001")


def test_resolve_barcode_returns_cached_item(in_memory_db, sample_item):
    """Items already in the DB are returned regardless of lookup_enabled."""
    add_item(sample_item, in_memory_db)
    config = {"api": {"lookup_enabled": False}}

    class _Logger:
        def info(self, *a): pass
        def warning(self, *a): pass

    result = resolve_barcode("9780571331475", in_memory_db, config, _Logger())
    assert result is not None
    assert result["title"] == "Test Book"


# ── list_catalog (Intake browsing order) ─────────────────────────────────────

def _add(conn, barcode, title, stock, publisher="", category_id=None):
    add_item({"barcode": barcode, "title": title, "author": "A", "publisher": publisher,
              "year": "", "price": 5.0, "stock": stock, "manual": 1,
              "category_id": category_id}, conn)


def test_list_catalog_in_stock_first_then_az(in_memory_db):
    _add(in_memory_db, "1", "Zebra", 3)
    _add(in_memory_db, "2", "Apple", 0)
    _add(in_memory_db, "3", "Mango", 1)
    _add(in_memory_db, "4", "Banana", 0)
    titles = [r["title"] for r in list_catalog(in_memory_db)]
    assert titles == ["Mango", "Zebra", "Apple", "Banana"]


def test_list_catalog_null_or_negative_stock_counts_as_out(in_memory_db):
    _add(in_memory_db, "1", "Null stock", 0)
    in_memory_db.execute("UPDATE catalog SET stock = NULL WHERE barcode = '1'")
    _add(in_memory_db, "2", "Negative", -2)
    _add(in_memory_db, "3", "Zed in stock", 1)
    titles = [r["title"] for r in list_catalog(in_memory_db)]
    assert titles == ["Zed in stock", "Negative", "Null stock"]


def test_list_catalog_search_matches_title_author_publisher(in_memory_db):
    _add(in_memory_db, "1", "Ulysses", 1, publisher="Faber")
    _add(in_memory_db, "2", "Dubliners", 1, publisher="Penguin")
    assert [r["title"] for r in list_catalog(in_memory_db, "faber")] == ["Ulysses"]
    assert [r["title"] for r in list_catalog(in_memory_db, "DUBLIN")] == ["Dubliners"]
    assert len(list_catalog(in_memory_db, "a")) == 2   # author "A"


def test_list_catalog_category_filter_keeps_order(in_memory_db):
    _add(in_memory_db, "1", "Card out", 0, category_id=2)
    _add(in_memory_db, "2", "Card in", 4, category_id=2)
    _add(in_memory_db, "3", "Loose", 1)
    assert [r["title"] for r in list_catalog(in_memory_db, category_filter=2)] == ["Card in", "Card out"]
    assert [r["title"] for r in list_catalog(in_memory_db, category_filter=UNSORTED)] == ["Loose"]
    assert len(list_catalog(in_memory_db, category_filter="all")) == 3


# ── remove_item / restore_item (Intake [R] Remove) ───────────────────────────

def _sell(conn, barcode, voided=0):
    conn.execute("INSERT INTO sales (barcode, title, quantity, price, sold_at, voided)"
                 " VALUES (?, 'x', 1, 5.0, '2026-10-28T12:00:00', ?)", (barcode, voided))
    conn.commit()


def test_remove_never_sold_item_deletes_it(in_memory_db):
    _add(in_memory_db, "1", "Mistake", 1)
    assert not has_sales("1", in_memory_db)
    assert remove_item("1", in_memory_db) == "deleted"
    assert get_item("1", in_memory_db) is None


def test_remove_sold_item_retires_and_keeps_it(in_memory_db):
    _add(in_memory_db, "1", "Old stock", 0)
    _add(in_memory_db, "2", "Current", 2)
    _sell(in_memory_db, "1")
    assert remove_item("1", in_memory_db) == "retired"
    assert get_item("1", in_memory_db)["retired"] == 1
    assert [r["title"] for r in list_catalog(in_memory_db)] == ["Current"]
    assert [r["title"] for r in list_catalog(in_memory_db, category_filter=RETIRED)] == ["Old stock"]


def test_remove_item_with_only_voided_sales_is_retired_not_deleted(in_memory_db):
    _add(in_memory_db, "1", "Voided once", 1)
    _sell(in_memory_db, "1", voided=1)
    assert remove_item("1", in_memory_db) == "retired"


def test_remove_missing_item_returns_none(in_memory_db):
    assert remove_item("nope", in_memory_db) is None


def test_restore_item_puts_it_back(in_memory_db):
    _add(in_memory_db, "1", "Back again", 1)
    _sell(in_memory_db, "1")
    remove_item("1", in_memory_db)
    restore_item("1", in_memory_db)
    assert [r["title"] for r in list_catalog(in_memory_db)] == ["Back again"]
    assert list_catalog(in_memory_db, category_filter=RETIRED) == []


def test_retired_items_left_out_of_low_stock(in_memory_db):
    from app.summary import get_low_stock
    _add(in_memory_db, "1", "Retired zero", 0)
    _add(in_memory_db, "2", "Live zero", 0)
    _sell(in_memory_db, "1")
    remove_item("1", in_memory_db)
    assert [r["title"] for r in get_low_stock(2, in_memory_db)] == ["Live zero"]
