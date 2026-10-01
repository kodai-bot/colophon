# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_dashboard.py - Tests for the read-only sales/stock dashboard.

Uses a file-backed temp DB (not :memory:) because the dashboard opens a
fresh connection per request via get_db(config) — :memory: would give each
request an independent, empty database.
"""

import inspect
import pytest
from app.catalog import get_db, add_item
from app.logger import record_sale
from app.dashboard import create_app


@pytest.fixture
def config(tmp_path):
    return {
        "database": {"path": str(tmp_path / "bookshop.db")},
        "shop": {"name": "Test Shop"},
        "stock": {"low_stock_threshold": 2},
        "catalog": {"inhouse_prefix": "2000001"},
        "dashboard": {"enabled": True, "port": 8088, "refresh_seconds": 30},
    }


@pytest.fixture
def client(config):
    conn = get_db(config)
    add_item({
        "barcode": "9780571331475",
        "title": "Test Book",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "year": "2020",
        "price": 12.99,
        "stock": 1,
        "manual": 0,
    }, conn)
    sale_id = record_sale("9780571331475", "Test Book", 12.99, conn)
    conn.execute("UPDATE sales SET payment_method = 'cash' WHERE id = ?", (sale_id,))
    conn.commit()
    conn.close()

    app = create_app(config)
    app.testing = True
    return app.test_client()


def test_default_route_shows_today(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Test Book" in resp.data
    assert b"12.99" in resp.data


def test_date_range_route_valid_dates(client):
    resp = client.get("/?start=2020-01-01&end=2030-01-01")
    assert resp.status_code == 200
    assert b"Test Book" in resp.data


def test_invalid_date_falls_back_gracefully(client):
    resp = client.get("/?start=not-a-date")
    assert resp.status_code == 200
    assert b"Test Book" in resp.data
    assert b"Couldn&#39;t understand" in resp.data or b"Couldn't understand" in resp.data


def test_low_stock_item_is_listed(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Test Book" in resp.data  # stock=1, threshold=2, so it's low


def test_dashboard_module_calls_no_known_mutating_functions():
    """
    Tripwire, not a full guarantee: confirms the obvious write-path functions
    and raw SQL verbs don't appear in app/dashboard.py's source. A real
    guarantee still needs a manual review at commit time (see AGENTS.md /
    the plan this was built from) — a renamed function or a new mutating
    helper wouldn't be caught here.
    """
    import app.dashboard as dash
    source = inspect.getsource(dash)
    for forbidden in ("record_sale", "void_last_sale", "add_item", "decrement_stock",
                       "INSERT", "UPDATE", "DELETE"):
        assert forbidden not in source, f"found forbidden mutating reference: {forbidden}"
