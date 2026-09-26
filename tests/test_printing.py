# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_printing.py - Tests for the receipt-printing module.

No real printer or CUPS queue is touched: `subprocess.run` is monkeypatched
in every print_receipt test.
"""

import subprocess
import pytest
from app.printing import (
    format_currency, format_line_item, format_receipt, print_receipt,
    INIT, SELECT_CODEPAGE_PC858, CUT_COMMANDS, CODEPAGE,
)


class StubLogger:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warning(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.infos.append(msg)


@pytest.fixture
def config():
    return {
        "shop": {"name": "Test Shop"},
        "printer": {
            "enabled": True,
            "queue_name": "colophon_receipt",
            "paper_width_chars": 42,
            "cut_mode": "partial",
            "footer_line": "Thanks!",
        },
    }


# ── format_currency ────────────────────────────────────────────

def test_format_currency_positive():
    assert format_currency(4.5) == "€4.50"


def test_format_currency_negative():
    assert format_currency(-5.0) == "-€5.00"


# ── format_line_item ────────────────────────────────────────────

def test_format_line_item_fits_on_one_line():
    line = format_line_item("Short Title", 4.00, 1, 42)
    assert "\n" not in line
    assert line.startswith("Short Title")
    assert line.endswith("€4.00")
    assert len(line) == 42


def test_format_line_item_wraps_long_title():
    long_title = "A" * 40
    line = format_line_item(long_title, 4.00, 1, 42)
    title_part, price_part = line.split("\n")
    assert title_part == long_title
    assert price_part.strip() == "€4.00"
    assert len(price_part) == 42


def test_format_line_item_quantity_prefix():
    line = format_line_item("Postcard", 2.00, 3, 42)
    assert line.startswith("3x Postcard")


def test_format_line_item_negative_price():
    line = format_line_item("Discount", -5.00, 1, 42)
    assert line.endswith("-€5.00")


# ── format_receipt ──────────────────────────────────────────────

def test_format_receipt_returns_bytes(config):
    receipt = format_receipt([("Book", 10.0, 1)], 10.0, "cash", "txn1", config)
    assert isinstance(receipt, bytes)


def test_format_receipt_starts_with_init(config):
    receipt = format_receipt([("Book", 10.0, 1)], 10.0, "cash", "txn1", config)
    assert receipt.startswith(INIT)


def test_format_receipt_codepage_precedes_euro_byte(config):
    receipt = format_receipt([("Book", 10.0, 1)], 10.0, "cash", "txn1", config)
    codepage_idx = receipt.index(SELECT_CODEPAGE_PC858)
    euro_idx = receipt.index("€".encode(CODEPAGE))
    assert codepage_idx < euro_idx


def test_format_receipt_euro_encodes_correctly(config):
    receipt = format_receipt([("Book", 10.0, 1)], 10.0, "cash", "txn1", config)
    assert b"\xd5" in receipt  # € under cp858


@pytest.mark.parametrize("cut_mode", ["partial", "full"])
def test_format_receipt_ends_with_configured_cut(config, cut_mode):
    config["printer"]["cut_mode"] = cut_mode
    receipt = format_receipt([("Book", 10.0, 1)], 10.0, "cash", "txn1", config)
    assert receipt.endswith(CUT_COMMANDS[cut_mode])


def test_format_receipt_total_line_uses_total_argument_not_item_sum(config):
    # Items sum to 5.00, but total is passed separately (e.g. after a discount)
    # and must be what's printed, not a re-sum of the items.
    receipt = format_receipt([("Book", 5.00, 1)], 3.50, "cash", "txn1", config)
    text = receipt.decode(CODEPAGE)
    assert "€3.50" in text
    assert "TOTAL" in text


# ── print_receipt ───────────────────────────────────────────────

def test_print_receipt_disabled_returns_false_and_skips_subprocess(config, monkeypatch):
    config["printer"]["enabled"] = False
    called = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.append((a, k)))

    result = print_receipt(b"data", config, StubLogger())

    assert result is False
    assert called == []


def test_print_receipt_success(config, monkeypatch):
    class FakeResult:
        returncode = 0
        stderr = b""

    captured = {}

    def fake_run(args, input=None, capture_output=None, timeout=None):
        captured["args"] = args
        captured["input"] = input
        return FakeResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    logger = StubLogger()

    result = print_receipt(b"receipt-bytes", config, logger)

    assert result is True
    assert captured["args"] == ["lp", "-d", "colophon_receipt", "-o", "raw"]
    assert isinstance(captured["input"], bytes)
    assert logger.warnings == []


def test_print_receipt_nonzero_exit_logs_warning(config, monkeypatch):
    class FakeResult:
        returncode = 1
        stderr = b"printer offline"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())
    logger = StubLogger()

    result = print_receipt(b"data", config, logger)

    assert result is False
    assert len(logger.warnings) == 1


def test_print_receipt_lp_not_found(config, monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", fake_run)
    logger = StubLogger()

    result = print_receipt(b"data", config, logger)

    assert result is False
    assert len(logger.warnings) == 1


def test_print_receipt_timeout(config, monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="lp", timeout=10)

    monkeypatch.setattr(subprocess, "run", fake_run)
    logger = StubLogger()

    result = print_receipt(b"data", config, logger)

    assert result is False
    assert len(logger.warnings) == 1
