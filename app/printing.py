# SPDX-License-Identifier: AGPL-3.0-or-later
"""
printing.py - ESC/POS receipt formatting and printing via CUPS.

Used by Counter mode (sale receipts) and Payments mode (room hire,
membership etc. receipts).

Best-effort: printing failures are logged and swallowed, never raised,
since by the time this is called the sale is already committed to the DB.
"""

import subprocess
from datetime import datetime
from typing import Protocol

from app.payment_methods import get_method

CODEPAGE = "cp858"  # matches SELECT_CODEPAGE_PC858 below (PC858 has the Euro sign)

INIT = b"\x1b\x40"
SELECT_CODEPAGE_PC858 = b"\x1b\x74\x13"
BOLD_ON = b"\x1b\x45\x01"
BOLD_OFF = b"\x1b\x45\x00"
ALIGN_CENTER = b"\x1b\x61\x01"
ALIGN_LEFT = b"\x1b\x61\x00"
CUT_COMMANDS = {
    "partial": b"\x1d\x56\x01",
    "full": b"\x1d\x56\x00",
}
# ESC p m t1 t2: pulse the cash drawer connector. m selects the pin
# (0 = pin 2, 1 = pin 5); t1/t2 are on/off times in 2ms units (50ms/500ms).
DRAWER_KICK = {
    2: b"\x1b\x70\x00\x19\xfa",
    5: b"\x1b\x70\x01\x19\xfa",
}


def format_currency(amount: float) -> str:
    """Format an amount as €X.XX, or -€X.XX for negative amounts (e.g. discounts)."""
    if amount < 0:
        return f"-€{abs(amount):.2f}"
    return f"€{amount:.2f}"


def format_line_item(title: str, price: float, quantity: int, width: int) -> str:
    """
    Format one receipt row: title left-aligned, price right-aligned.
    If the title doesn't fit alongside the price, wrap it onto its own
    line with the price alone on the line below.
    """
    price_str = format_currency(price)
    if quantity != 1:
        title = f"{quantity}x {title}"

    gap = width - len(title) - len(price_str)
    if gap >= 1:
        return title + (" " * gap) + price_str

    return title + "\n" + price_str.rjust(width)


def _build_receipt(body_lines: list[str], payment_method: str, config: dict) -> bytes:
    """
    Wrap receipt body lines in the parts every receipt shares: the drawer
    kick (cash only, when enabled), the shop name header, the footer line
    and the paper cut.
    """
    printer_cfg = config.get("printer", {})
    cut_mode = printer_cfg.get("cut_mode", "partial")
    footer = printer_cfg.get("footer_line", "")
    shop_name = config.get("shop", {}).get("name", "Shop")
    method = get_method(payment_method)
    kick_drawer = bool(method and method.kicks_drawer) and printer_cfg.get("cash_drawer", False)
    drawer_pin = printer_cfg.get("drawer_pin", 2)

    body_lines = list(body_lines)
    if footer:
        body_lines.append("")
        body_lines.append(footer)

    out = bytearray()
    out += INIT
    if kick_drawer:
        # Sent first so the drawer opens while the receipt is still printing.
        out += DRAWER_KICK.get(drawer_pin, DRAWER_KICK[2])
    out += SELECT_CODEPAGE_PC858
    out += ALIGN_CENTER + BOLD_ON
    out += (shop_name.upper() + "\n").encode(CODEPAGE, errors="replace")
    out += BOLD_OFF + ALIGN_LEFT
    out += ("\n".join(body_lines) + "\n").encode(CODEPAGE, errors="replace")
    out += b"\n\n\n"
    out += CUT_COMMANDS.get(cut_mode, CUT_COMMANDS["partial"])
    return bytes(out)


def format_receipt(
    items: list[tuple[str, float, int]],
    total: float,
    payment_method: str,
    txn_id: str,
    config: dict,
) -> bytes:
    """Build the full ESC/POS byte sequence for a Counter-mode receipt."""
    width = config.get("printer", {}).get("paper_width_chars", 42)

    body_lines = [datetime.now().strftime("%a %d %b %Y  %H:%M"), ""]
    for title, price, quantity in items:
        body_lines.append(format_line_item(title, price, quantity, width))
    body_lines.append("-" * width)
    body_lines.append(format_line_item("TOTAL", total, 1, width))
    body_lines.append(f"Paid: {payment_method.upper()}")
    return _build_receipt(body_lines, payment_method, config)


def format_payment_receipt(
    payment_type: str,
    payer_name: str,
    amount: float,
    payment_method: str,
    payment_id: int,
    config: dict,
    reference: str | None = None,
    notes: str | None = None,
) -> bytes:
    """
    Build the full ESC/POS byte sequence for a Payments-mode receipt
    (room hire, membership, etc.). Numbered P-<id> from the payments table,
    so it can't be mistaken for a Counter transaction.
    """
    width = config.get("printer", {}).get("paper_width_chars", 42)

    body_lines = [
        datetime.now().strftime("%a %d %b %Y  %H:%M"),
        f"Receipt no. P-{payment_id}",
        "",
        format_line_item(payment_type, amount, 1, width),
        f"Received from: {payer_name}",
    ]
    if reference:
        body_lines.append(f"Ref: {reference}")
    if notes:
        body_lines.append(notes)
    body_lines.append("-" * width)
    body_lines.append(format_line_item("TOTAL", amount, 1, width))
    body_lines.append(f"Paid: {payment_method.upper()}")
    return _build_receipt(body_lines, payment_method, config)


class Printer(Protocol):
    """The transport seam: anything that can send raw receipt bytes
    somewhere. CupsEscPosPrinter below is the only implementation that has
    ever been needed in production. A future printer model (different
    transport, same ESC/POS bytes) adds a new class here, nothing else."""

    def send(self, data: bytes, config: dict, logger, what: str) -> bool: ...


class CupsEscPosPrinter:
    """Sends raw ESC/POS bytes to a CUPS queue via `lp -d <queue> -o raw`.
    Proven in production against an Epson TM-T20II over USB."""

    def send(self, data: bytes, config: dict, logger, what: str) -> bool:
        printer_cfg = config.get("printer", {})
        if not printer_cfg.get("enabled", False):
            return False

        queue = printer_cfg.get("queue_name", "colophon_receipt")

        try:
            result = subprocess.run(
                ["lp", "-d", queue, "-o", "raw"],
                input=data,
                capture_output=True,
                timeout=10,
            )
        except FileNotFoundError:
            logger.warning(f"{what} failed: 'lp' command not found (is CUPS installed?)")
            return False
        except subprocess.TimeoutExpired:
            logger.warning(f"{what} failed: 'lp' command timed out")
            return False
        except Exception as e:
            logger.warning(f"{what} failed: {e}")
            return False

        if result.returncode != 0:
            logger.warning(
                f"{what} failed (lp exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace').strip()}"
            )
            return False

        logger.info(f"{what} sent to queue '{queue}'")
        return True


_default_printer = CupsEscPosPrinter()


def print_receipt(
    receipt_bytes: bytes, config: dict, logger, printer: Printer = _default_printer
) -> bool:
    """
    Send receipt_bytes to the configured CUPS queue via `lp -d <queue> -o raw`.
    Returns True on success, False on any failure. Never raises.
    """
    return printer.send(receipt_bytes, config, logger, "Receipt")


def open_drawer(config: dict, logger, printer: Printer = _default_printer) -> bool:
    """
    Open the cash drawer on its own, with no receipt (Counter mode's No sale).
    Returns False without sending anything if the drawer isn't enabled.
    """
    printer_cfg = config.get("printer", {})
    if not printer_cfg.get("cash_drawer", False):
        return False
    kick = DRAWER_KICK.get(printer_cfg.get("drawer_pin", 2), DRAWER_KICK[2])
    return printer.send(INIT + kick, config, logger, "Drawer kick")
