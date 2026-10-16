# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_counter_items.py - Counter shortcut items: seeding, slots, editing
"""

import sqlite3
import pytest

from app.catalog import (
    _create_tables, _create_counter_items, list_counter_items, counter_slot_count,
    parse_counter_price, set_counter_item, clear_counter_item, swap_counter_slots,
)

SEED = [
    {"name": "Postcard", "price": 4.0},
    {"name": "Postcard (large)", "price": 6.0},
    {"name": "Tour admission", "price": None},
    {"name": "Card bundle (4 for €20)", "price": 20.0},
]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    _create_tables(c)
    _create_counter_items(c, SEED)
    yield c
    c.close()


def names(conn, slots=5):
    return [i["name"] for i in list_counter_items(conn, slots)]


def test_seeded_from_config_with_spare_slot(conn):
    assert names(conn) == [
        "Postcard", "Postcard (large)", "Tour admission", "Card bundle (4 for €20)", None,
    ]
    items = list_counter_items(conn, 4)
    assert items[2]["price"] is None and items[3]["price"] == 20.0


def test_seed_runs_only_once(conn):
    clear_counter_item(1, conn)
    _create_counter_items(conn, SEED)        # next app start
    assert names(conn, 1) == [None]          # cleared slot stays cleared


def test_seed_skips_blank_names_but_keeps_slot_numbers():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    _create_counter_items(c, [{"name": "A", "price": 1}, {"name": "  "}, {"name": "C"}])
    assert names(c, 3) == ["A", None, "C"]


def test_slot_count_clamped():
    assert counter_slot_count({}) == 4
    assert counter_slot_count({"counter_item_slots": 5}) == 5
    assert counter_slot_count({"counter_item_slots": 20}) == 9
    assert counter_slot_count({"counter_item_slots": 0}) == 4     # blank/0 → default
    assert counter_slot_count({"counter_item_slots": -3}) == 1
    assert counter_slot_count({"counter_item_slots": "x"}) == 4


def test_items_beyond_slot_count_kept_but_hidden(conn):
    set_counter_item(7, "Spare", 2.0, conn)
    assert len(list_counter_items(conn, 5)) == 5
    assert list_counter_items(conn, 7)[6]["name"] == "Spare"


def test_set_returns_old_and_overwrites(conn):
    old = set_counter_item(4, "  Gift   wrap ", 3.5, conn)
    assert old == {"name": "Card bundle (4 for €20)", "price": 20.0}
    assert list_counter_items(conn, 4)[3] == {"slot": 4, "name": "Gift wrap", "price": 3.5}
    assert set_counter_item(5, "New", None, conn) is None


@pytest.mark.parametrize("slot,name", [(0, "x"), (10, "x"), (5, ""), (5, "   "), (5, "x" * 31)])
def test_set_rejects_bad_input(conn, slot, name):
    with pytest.raises(ValueError):
        set_counter_item(slot, name, 1.0, conn)


@pytest.mark.parametrize("raw,expected", [
    ("", None), ("  ", None), ("20", 20.0), ("20.00", 20.0), ("€4.5", 4.5),
    ("6,50", 6.5), ("1.005", 1.0),
])
def test_parse_price(raw, expected):
    assert parse_counter_price(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "0", "-5", "100000"])
def test_parse_price_rejects(raw):
    with pytest.raises(ValueError):
        parse_counter_price(raw)


def test_clear(conn):
    assert clear_counter_item(2, conn) == {"name": "Postcard (large)", "price": 6.0}
    assert clear_counter_item(2, conn) is None
    assert names(conn, 3) == ["Postcard", None, "Tour admission"]


def test_swap_filled_and_empty(conn):
    swap_counter_slots(1, 2, conn)
    assert names(conn, 2) == ["Postcard (large)", "Postcard"]
    swap_counter_slots(4, 5, conn)           # move into the empty spare slot
    assert names(conn)[3:] == [None, "Card bundle (4 for €20)"]
    swap_counter_slots(1, 1, conn)
    swap_counter_slots(0, 1, conn)           # out of range: no-op
    assert names(conn, 1) == ["Postcard (large)"]
