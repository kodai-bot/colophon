# SPDX-License-Identifier: AGPL-3.0-or-later
"""
payments.py - Payments mode for the Colophon bookshop counter system.

Log sundry payments: room hire, memberships, event bookings, etc.
No PIN required. Stays open for multiple entries in a row.
Prints a receipt (untick "Print receipt" to skip) and opens the cash
drawer for cash payments, as Counter mode does.
Press Escape to return to mode selector.
"""

from textual.app import App, ComposeResult
from textual.widgets import Static, Input, Button, Select, Checkbox
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual import on
from datetime import datetime

from app.utils import load_config, get_logger, timestamp_now
from app.catalog import get_db
from app.payment_methods import get_method
from app.printing import format_payment_receipt, print_receipt, open_drawer
from app.ui.quotes import get_quote_display
from app.ui.widgets import BackButton, HintBar, literal


DEFAULT_PAYMENT_TYPES = [
    "Room Hire",
    "Membership",
    "Event Booking",
    "Donation",
    "Other",
]

CSS = """
Screen { align: center middle; }

#card {
    width: 80%;
    min-width: 54;
    max-width: 72;
    height: auto;
    max-height: 100%;
    overflow-y: auto;
    border: solid #2a2a5a;
    background: #0f0f2a;
    padding: 1 3;
}

#title {
    color: #d4af37;
    text-align: center;
    padding: 0 0 1 0;
    border-bottom: solid #2a2a5a;
    margin-bottom: 1;
    text-style: bold;
}

.field-row {
    height: 3;
    margin-bottom: 1;
    align: left middle;
}

.field-label {
    width: 14;
    height: 3;
    color: #c8b89a;
    content-align: left middle;
    padding: 0 1 0 0;
}

.field-label-opt {
    width: 14;
    height: 3;
    color: #6a6a8a;
    content-align: left middle;
    padding: 0 1 0 0;
}

.field-input {
    width: 1fr;
    background: #09091f;
    border: solid #3a3a6a;
    color: #e8dcc8;
}

.field-input:focus {
    border: solid #d4af37;
    color: #d4af37;
}

Select {
    width: 1fr;
}

#receipt-row {
    height: 3;
    align: left middle;
}

#print-receipt {
    background: #0f0f2a;
    border: none;
    color: #c8b89a;
}

#print-receipt:focus {
    color: #d4af37;
}

#error-msg {
    color: #ff6b6b;
    text-align: center;
    height: 0;
    margin: 0;
}

#error-msg.visible {
    height: auto;
    margin-bottom: 1;
}

#error-msg.ok {
    color: #6bcf8f;
    text-style: bold;
}

.btn-row {
    height: 3;
    align: center middle;
    margin-top: 1;
}

#btn-record {
    width: 22;
    height: 3;
    background: #0a1a3a;
    border: solid #d4af37;
    color: #d4af37;
    text-style: bold;
    margin-right: 2;
    content-align: center middle;
}

#btn-record:hover { background: #1a2a5a; }
#btn-record:focus { background: #1a2a5a; border: double #d4af37; }

#btn-cancel {
    width: 12;
    height: 3;
    background: #1a1a2a;
    border: solid #4a4a6a;
    color: #6a6a9a;
    content-align: center middle;
}

#btn-cancel:hover { background: #2a2a4a; }
#btn-cancel:focus { border: solid #d4af37; color: #d4af37; }

#last-recorded {
    color: #4a6a5a;
    text-align: center;
    margin-top: 1;
    padding-top: 1;
    border-top: solid #1a1a3a;
    text-style: italic;
}

#footer-quote {
    color: #3a3a6a;
    text-align: center;
    text-style: italic;
}
"""


class PaymentsApp(App):
    """
    Colophon — Payments Mode.
    Log room hire, memberships, event bookings, and other sundry payments.
    """

    CSS_PATH = "theme.tcss"
    CSS = CSS

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.logger = get_logger("payments", self.config)
        self.conn = get_db(self.config)
        self._payment_types = self.config.get("payment_types", DEFAULT_PAYMENT_TYPES)
        self._location = self.config.get("payments", {}).get("location_tag", "BOOKSHOP")
        self._shop_name = self.config.get("shop", {}).get("name", "Shop")
        self._printer_enabled = self.config.get("printer", {}).get("enabled", False)

    def compose(self) -> ComposeResult:
        today = datetime.now().strftime("%a  %d %b %Y")
        options = [(t, t) for t in self._payment_types]
        with Vertical(id="card"):
            yield Static(
                f"✦  {self._shop_name.upper()} {self._location}  ·  PAYMENT ENTRY  ·  {today}  ✦",
                id="title",
            )
            with Horizontal(classes="field-row"):
                yield Static("Type:", classes="field-label")
                yield Select(options, prompt="Select payment type...", id="payment-type")
            with Horizontal(classes="field-row"):
                yield Static("Name:", classes="field-label")
                yield Input(
                    placeholder="Payer name (required)",
                    id="field-name",
                    classes="field-input",
                )
            with Horizontal(classes="field-row"):
                yield Static("Amount €:", classes="field-label")
                yield Input(
                    placeholder="0.00",
                    id="field-amount",
                    classes="field-input",
                )
            with Horizontal(classes="field-row"):
                yield Static("Method:", classes="field-label")
                yield Select(
                    [("Cash", "cash"), ("Card", "card")],
                    prompt="Cash or Card?",
                    id="payment-method",
                )
            with Horizontal(classes="field-row"):
                yield Static("Reference:", classes="field-label-opt")
                yield Input(
                    placeholder="booking ref, membership no. etc.  (optional)",
                    id="field-reference",
                    classes="field-input",
                )
            with Horizontal(classes="field-row"):
                yield Static("Notes:", classes="field-label-opt")
                yield Input(
                    placeholder="additional details  (optional)",
                    id="field-notes",
                    classes="field-input",
                )
            if self._printer_enabled:
                with Horizontal(id="receipt-row"):
                    yield Static("", classes="field-label")
                    yield Checkbox("Print receipt", value=True, id="print-receipt")
            yield Static("", id="error-msg")
            with Horizontal(classes="btn-row"):
                yield Button("  RECORD PAYMENT  ", id="btn-record")
                yield Button(literal("Cancel  [Esc]"), id="btn-cancel")
            yield Static("", id="last-recorded")
            yield Static(get_quote_display(), id="footer-quote")
            yield HintBar(id="hint-bar")

    def on_mount(self) -> None:
        self.query_one("#payment-type").focus()
        self.query_one(HintBar).update_from(self.BINDINGS)

    # ── Validation & save ──────────────────────────────────────

    def _validate_and_save(self) -> None:
        ptype = self.query_one("#payment-type", Select).value
        method = self.query_one("#payment-method", Select).value
        name = self.query_one("#field-name", Input).value.strip()
        amount_str = self.query_one("#field-amount", Input).value.strip()
        reference = self.query_one("#field-reference", Input).value.strip()
        notes = self.query_one("#field-notes", Input).value.strip()

        if ptype is Select.NULL or not ptype:
            self._show_error("Please select a payment type.")
            self.query_one("#payment-type").focus()
            return

        if method is Select.NULL or not method:
            self._show_error("Please select a payment method (Cash or Card).")
            self.query_one("#payment-method").focus()
            return

        if not name:
            self._show_error("Payer name is required.")
            self.query_one("#field-name").focus()
            return

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            self._show_error("Amount must be a positive number.")
            self.query_one("#field-amount").focus()
            return

        now = timestamp_now()
        cursor = self.conn.execute("""
            INSERT INTO payments
                (timestamp, location, payment_type, payer_name, description, amount, reference, logged_by, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now, self._location, ptype, name,
            notes or None, amount, reference or None, "counter", method,
        ))
        self.conn.commit()
        payment_id = cursor.lastrowid

        # Printing is best-effort and never raises: the payment is already saved.
        receipt_status = "skipped"
        if self._printer_enabled and self.query_one("#print-receipt", Checkbox).value:
            receipt = format_payment_receipt(
                ptype, name, amount, method, payment_id, self.config,
                reference=reference or None, notes=notes or None,
            )
            printed = print_receipt(receipt, self.config, self.logger)  # kicks the drawer for cash
            receipt_status = "printed" if printed else "failed"
        elif get_method(method) and get_method(method).kicks_drawer:
            open_drawer(self.config, self.logger)

        self.logger.info(
            f"Payment recorded: {ptype} — {name} — €{amount:.2f}  method={method}  "
            f"ref={reference or '—'}  id=P-{payment_id}  "
            f"receipt={receipt_status}"
        )

        time_str = datetime.now().strftime("%H:%M")
        self.query_one("#last-recorded").update(
            f"Last recorded:  {ptype}  —  {name}  —  €{amount:.2f}  —  {method.upper()}  —  {time_str}"
        )
        receipt_note = {
            "printed": "  ·  receipt printed",
            "failed": "  ·  ⚠ receipt didn't print",
        }.get(receipt_status, "")
        self._show_ok(
            f"Payment logged:  {ptype}  €{amount:.2f}  {method.upper()}{receipt_note}"
        )
        self._clear_fields()
        self.query_one("#footer-quote").update(get_quote_display())
        self.query_one("#payment-type").focus()

    def _clear_fields(self) -> None:
        self.query_one("#payment-type", Select).value = Select.NULL
        self.query_one("#payment-method", Select).value = Select.NULL
        self.query_one("#field-name", Input).value = ""
        self.query_one("#field-amount", Input).value = ""
        self.query_one("#field-reference", Input).value = ""
        self.query_one("#field-notes", Input).value = ""
        if self._printer_enabled:
            self.query_one("#print-receipt", Checkbox).value = True

    def _show_error(self, msg: str) -> None:
        err = self.query_one("#error-msg")
        err.update(f"⚠  {msg}")
        err.remove_class("ok")
        err.add_class("visible")

    def _show_ok(self, msg: str) -> None:
        """Green confirmation in the same spot as errors, so staff know the payment saved."""
        err = self.query_one("#error-msg")
        err.update(f"✓  {msg}")
        err.add_class("visible", "ok")

    def _hide_error(self) -> None:
        err = self.query_one("#error-msg")
        err.update("")
        err.remove_class("visible", "ok")

    # ── Event handlers ─────────────────────────────────────────

    @on(Button.Pressed, "#btn-record")
    def _click_record(self) -> None:
        self._validate_and_save()

    @on(Button.Pressed, "#btn-cancel")
    def _click_cancel(self) -> None:
        self.exit()

    @on(Input.Submitted)
    def _input_submitted(self, event: Input.Submitted) -> None:
        """Enter in any field triggers form submission."""
        self._validate_and_save()

    # ── Back ───────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.exit()

    def action_quit(self) -> None:
        """Ctrl+Q exits the whole program, not just this mode."""
        self.exit(result="quit")


def main():
    app = PaymentsApp()
    app.run()


if __name__ == "__main__":
    main()
