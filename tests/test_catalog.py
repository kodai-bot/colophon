# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_catalog.py - Tests for catalog module
"""

import sqlite3
import pytest
from app.catalog import (
    get_item, add_item, decrement_stock, _create_tables,
    is_valid_barcode, resolve_barcode,
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
