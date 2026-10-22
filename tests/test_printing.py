# SPDX-License-Identifier: AGPL-3.0-or-later
"""
tests/test_printing.py - Tests for the receipt-printing module.

No real printer or CUPS queue is touched: `subprocess.run` is monkeypatched
in every print_receipt test.
"""

import subprocess
import pytest
from app.printing import (
    format_currency, format_line_item, format_receipt, format_payment_receipt, print_receipt,
    INIT, SELECT_CODEPAGE_PC858, CUT_COMMANDS, CODEPAGE, DRAWER_KICK, open_drawer,
    CupsEscPosPrinter,
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


# ── cash drawer kick ────────────────────────────────────────────

def test_cash_payment_kicks_drawer_when_enabled(config):
    config["printer"]["cash_drawer"] = True
    out = format_receipt([("Book", 5.0, 1)], 5.0, "cash", "T1", config)
    assert out.startswith(INIT + DRAWER_KICK[2])


def test_card_payment_never_kicks_drawer(config):
    config["printer"]["cash_drawer"] = True
    out = format_receipt([("Book", 5.0, 1)], 5.0, "card", "T1", config)
    assert not any(k in out for k in DRAWER_KICK.values())


def test_drawer_off_by_default(config):
    out = format_receipt([("Book", 5.0, 1)], 5.0, "cash", "T1", config)
    assert not any(k in out for k in DRAWER_KICK.values())


def test_drawer_pin_5(config):
    config["printer"]["cash_drawer"] = True
    config["printer"]["drawer_pin"] = 5
    out = format_receipt([("Book", 5.0, 1)], 5.0, "cash", "T1", config)
    assert out.startswith(INIT + DRAWER_KICK[5])


# ── open_drawer (No sale) ──────────────────────────────────────

def test_open_drawer_sends_kick_only(config, monkeypatch):
    config["printer"]["cash_drawer"] = True
    sent = {}

    def fake_run(cmd, input, **kwargs):
        sent["data"] = input
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert open_drawer(config, StubLogger()) is True
    assert sent["data"] == INIT + DRAWER_KICK[2]


def test_open_drawer_does_nothing_when_disabled(config, monkeypatch):
    def fail_run(*a, **k):
        raise AssertionError("lp should not be called")

    monkeypatch.setattr(subprocess, "run", fail_run)
    assert open_drawer(config, StubLogger()) is False


# ── printer seam ────────────────────────────────────────────────
# Proves CupsEscPosPrinter is a complete, swappable implementation of the
# Printer protocol, and that print_receipt/open_drawer delegate to whatever
# printer is injected (defaulting to CupsEscPosPrinter in production).

def test_cupsescpos_printer_used_directly(config, monkeypatch):
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

    result = CupsEscPosPrinter().send(b"receipt-bytes", config, logger, "Receipt")

    assert result is True
    assert captured["args"] == ["lp", "-d", "colophon_receipt", "-o", "raw"]
    assert captured["input"] == b"receipt-bytes"
    assert logger.warnings == []


class _FakePrinter:
    def __init__(self):
        self.calls = []

    def send(self, data, config, logger, what):
        self.calls.append((data, what))
        return True


def test_print_receipt_delegates_to_injected_printer(config):
    fake = _FakePrinter()
    assert print_receipt(b"data", config, StubLogger(), printer=fake) is True
    assert fake.calls == [(b"data", "Receipt")]


def test_open_drawer_delegates_to_injected_printer(config):
    config["printer"]["cash_drawer"] = True
    fake = _FakePrinter()
    assert open_drawer(config, StubLogger(), printer=fake) is True
    assert fake.calls == [(INIT + DRAWER_KICK[2], "Drawer kick")]


# ── format_payment_receipt (Payments mode) ──────────────────────

def _payment(config, method="cash", **kw):
    return format_payment_receipt("Room Hire", "Jane Smith", 50.0, method, 123, config, **kw)


def test_payment_receipt_contents(config):
    text = _payment(config).decode(CODEPAGE)
    assert "TEST SHOP" in text
    assert "Receipt no. P-123" in text
    assert "Room Hire" in text
    assert "Received from: Jane Smith" in text
    assert "€50.00" in text
    assert "Paid: CASH" in text
    assert "Thanks!" in text


def test_payment_receipt_reference_and_notes_only_when_given(config):
    bare = _payment(config).decode(CODEPAGE)
    assert "Ref:" not in bare
    full = _payment(config, reference="B-4471", notes="Hall, Sat 7pm").decode(CODEPAGE)
    assert "Ref: B-4471" in full
    assert "Hall, Sat 7pm" in full


def test_payment_receipt_cash_kicks_drawer_when_enabled(config):
    config["printer"]["cash_drawer"] = True
    assert _payment(config, "cash").startswith(INIT + DRAWER_KICK[2])


def test_payment_receipt_card_never_kicks_drawer(config):
    config["printer"]["cash_drawer"] = True
    out = _payment(config, "card")
    assert not any(k in out for k in DRAWER_KICK.values())


@pytest.mark.parametrize("cut_mode", ["partial", "full"])
def test_payment_receipt_ends_with_configured_cut(config, cut_mode):
    config["printer"]["cut_mode"] = cut_mode
    assert _payment(config).endswith(CUT_COMMANDS[cut_mode])
