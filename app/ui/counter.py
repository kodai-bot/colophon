# SPDX-License-Identifier: AGPL-3.0-or-later
"""
counter.py - Main Textual counter application.

Staff-facing. Scan-only. Cannot be broken by accident.
Run with: python -m app.ui.counter

"A rebellion is built on hope." — Jyn Erso
"""

from textual.app import App, ComposeResult
from textual.widgets import Static, Input, Button
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import on
from textual.timer import Timer
from datetime import datetime
import time

from app.utils import load_config, get_logger
from app.catalog import get_db, resolve_barcode, decrement_stock, is_valid_barcode, get_inhouse_prefix
from app.logger import record_sale, void_last_sale
from app.ui.widgets import (
    HeaderBar, ScanDisplay, DailyManifest,
    NonIsbnPanel, FooterBar, StockAlert,
    BackButton, HintBar,
)


CSS = """
#topbar { height: 3; }

HeaderBar {
    background: #1a1a3a;
    color: #d4af37;
    border-bottom: solid #d4af37;
}

#scan-display {
    height: 6;
    margin: 0 1;
    padding: 0 1;
}

#scan-display.status-ok {
    border: solid #d4af37;
    color: #d4af37;
}

#scan-display.status-warn {
    border: solid #8b0000;
    color: #ff6b6b;
}

#scan-display.status-pending {
    border: solid #cc8400;
    color: #ffb347;
}

#scan-input {
    height: 1;
    border: none;
    background: #0a0a1a;
    color: #0a0a1a;
    margin: 0;
    padding: 0;
}

#main-row { height: 1fr; }

NonIsbnPanel {
    width: 2fr;
    min-width: 38;
    height: 1fr;
    overflow-y: auto;
}

DailyManifest {
    width: 1fr;
    min-width: 28;
    height: 1fr;
    overflow-y: auto;
    padding: 0 1;
}

#action-row { height: 3; }

#pay-btn {
    width: 1fr;
    height: 3;
    background: #0a1f0a;
    border: solid #4aaa7a;
    color: #4aaa7a;
    text-style: bold;
    margin: 0;
    content-align: center middle;
}

#pay-btn:hover  { background: #0f2f0f; }
#pay-btn:focus  { border: solid #d4af37; color: #d4af37; }
#pay-btn.-empty { background: #0f0f1a; border: solid #2a2a4a; color: #3a3a6a; }

#discount-btn {
    width: auto;
    min-width: 22;
    height: 3;
    background: #1f150a;
    border: solid #aa7a4a;
    color: #d4a86a;
    margin: 0;
    content-align: center middle;
}

#discount-btn:hover { background: #2f200f; }
#discount-btn:focus { border: solid #d4af37; color: #d4af37; }
"""


class PriceEntryScreen(ModalScreen):
    """Modal price prompt for items with variable price."""

    DEFAULT_CSS = """
    PriceEntryScreen { align: center middle; }

    #price-dialog {
        width: 54;
        height: auto;
        background: #0f0f2a;
        border: double #d4af37;
        padding: 2 3;
    }

    #price-dialog-name {
        color: #d4af37;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #price-dialog-label { color: #c8b89a; margin-bottom: 1; }

    #price-dialog-input {
        background: #09091f;
        border: solid #d4af37;
        color: #d4af37;
    }

    #price-dialog-hint {
        color: #3a3a6a;
        text-align: center;
        margin-top: 1;
        text-style: italic;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, item_name: str, label: str = "  Enter price (€):", **kwargs):
        super().__init__(**kwargs)
        self._item_name = item_name
        self._label = label

    def compose(self) -> ComposeResult:
        with Vertical(id="price-dialog"):
            yield Static(self._item_name.upper(), id="price-dialog-name")
            yield Static(self._label, id="price-dialog-label")
            yield Input(placeholder="0.00", id="price-dialog-input")
            yield Static("  Enter to confirm   ·   Esc to cancel", id="price-dialog-hint")

    def on_mount(self) -> None:
        self.query_one("#price-dialog-input").focus()

    @on(Input.Submitted, "#price-dialog-input")
    def confirm(self, event: Input.Submitted) -> None:
        try:
            self.dismiss(float(event.value.strip()))
        except ValueError:
            self.query_one("#price-dialog-input").value = ""

    def action_cancel(self) -> None:
        self.dismiss(None)


class PaymentScreen(ModalScreen):
    """Payment method selection shown when Subtotal is pressed."""

    DEFAULT_CSS = """
    PaymentScreen { align: center middle; }

    #payment-dialog {
        width: 44;
        height: auto;
        background: #0f0f2a;
        border: double #d4af37;
        padding: 2 3;
    }

    #payment-total {
        color: #d4af37;
        text-align: center;
        text-style: bold;
        margin-bottom: 2;
    }

    .payment-btn {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        content-align: center middle;
        text-style: bold;
    }

    #btn-cash {
        background: #0a1f0a;
        border: solid #4aaa7a;
        color: #4aaa7a;
    }
    #btn-cash:hover { background: #0f2f0f; }

    #btn-card {
        background: #0a0a1f;
        border: solid #6a6aaa;
        color: #6a6aaa;
    }
    #btn-card:hover { background: #0f0f2f; }

    #payment-skip {
        color: #3a3a6a;
        text-align: center;
        text-style: italic;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("c", "cash", "Cash", show=False),
        Binding("k", "card", "Card", show=False),
        Binding("escape", "skip", "Skip", show=False),
    ]

    def __init__(self, total: float, item_count: int, **kwargs):
        super().__init__(**kwargs)
        self._total = total
        self._item_count = item_count

    def compose(self) -> ComposeResult:
        noun = "item" if self._item_count == 1 else "items"
        with Vertical(id="payment-dialog"):
            yield Static(
                f"{self._item_count} {noun}  ·  Total: €{self._total:.2f}",
                id="payment-total",
            )
            yield Button("[C]  Cash", id="btn-cash", classes="payment-btn")
            yield Button("[K]  Card", id="btn-card", classes="payment-btn")
            yield Static("  Esc to keep basket open", id="payment-skip")

    def action_cash(self) -> None:
        self.dismiss("cash")

    def action_card(self) -> None:
        self.dismiss("card")

    def action_skip(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-cash")
    def _cash(self) -> None:
        self.dismiss("cash")

    @on(Button.Pressed, "#btn-card")
    def _card(self) -> None:
        self.dismiss("card")



class CounterApp(App):
    """
    Counter Mode — scan items and log sales.
    """

    CSS_PATH = "theme.tcss"
    CSS = CSS

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("ctrl+z", "undo_sale", "Undo last", show=True),
        Binding("ctrl+t", "pay", "Subtotal / Pay", show=True),
        Binding("ctrl+d", "discount", "Discount", show=True),
        Binding("1", "select_item('1')", "Item 1", show=True),
        Binding("2", "select_item('2')", "Item 2", show=True),
        Binding("3", "select_item('3')", "Item 3", show=True),
        Binding("4", "select_item('4')", "Item 4", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.logger = get_logger("counter", self.config)
        self.conn = get_db(self.config)
        self.non_isbn_items = self.config.get("non_isbn_items", [])
        self.low_threshold = self.config["stock"]["low_stock_threshold"]
        self._inhouse_prefix = get_inhouse_prefix(self.config)
        self._ui = self.config.get("ui", {})
        self._alert_timer: Timer | None = None
        self._quote_timer: Timer | None = None
        self._flavor_timer: Timer | None = None
        self._last_scan_at: float = 0.0
        self._daily_items = 0
        self._daily_revenue = 0.0
        self._daily_cash = 0.0
        self._daily_card = 0.0
        self._txn_id: str | None = None
        self._basket_items = 0
        self._basket_total = 0.0
        self._load_daily_totals()

    def _load_daily_totals(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        row = self.conn.execute("""
            SELECT COUNT(*) as cnt, SUM(COALESCE(price, 0) * quantity) as rev
            FROM sales WHERE DATE(sold_at) = ? AND voided = 0
        """, (today,)).fetchone()
        self._daily_items = row["cnt"] or 0
        self._daily_revenue = row["rev"] or 0.0
        for attr, method in (("_daily_cash", "cash"), ("_daily_card", "card")):
            r = self.conn.execute("""
                SELECT SUM(COALESCE(price, 0) * quantity) as rev
                FROM sales WHERE DATE(sold_at) = ? AND voided = 0 AND payment_method = ?
            """, (today, method)).fetchone()
            setattr(self, attr, r["rev"] or 0.0)

    def _new_txn_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def compose(self) -> ComposeResult:
        shop = self.config.get("shop", {})
        with Horizontal(id="topbar"):
            yield HeaderBar(
                title=shop.get("name", "Shop"),
                location=shop.get("location", ""),
            )
            yield BackButton("⌂ Home  [Esc]", id="back-btn")

        yield ScanDisplay(id="scan-display")
        yield Input(placeholder="", id="scan-input")

        with Horizontal(id="main-row"):
            yield NonIsbnPanel(
                self.non_isbn_items,
                heading=self._ui.get("misc_items_label", "OTHER ITEMS"),
                id="non-isbn-panel",
            )
            yield DailyManifest(id="daily-manifest")

        with Horizontal(id="action-row"):
            yield Button("  ✦  Subtotal / Pay  [Ctrl+T]", id="pay-btn", classes="-empty")
            yield Button("  −  Discount  [Ctrl+D]", id="discount-btn")

        yield StockAlert(id="stock-alert")
        yield HintBar(id="hint-bar")
        yield FooterBar()

    def on_mount(self) -> None:
        self.query_one("#scan-input").focus()
        self.query_one(DailyManifest).update_totals(
            self._daily_items, self._daily_revenue, self._daily_cash, self._daily_card
        )
        self.query_one(HintBar).update_from(self.BINDINGS)
        self._quote_timer = self.set_interval(60, self._rotate_quote)
        self._flavor_timer = self.set_interval(20, self._rotate_flavor)

    def _rotate_quote(self) -> None:
        self.query_one(FooterBar).refresh_quote()

    def _rotate_flavor(self) -> None:
        self.query_one(ScanDisplay).rotate_flavor()

    def _update_basket_display(self) -> None:
        manifest = self.query_one(DailyManifest)
        manifest.update_basket(self._basket_items, self._basket_total)
        self.query_one(ScanDisplay).set_pending(self._basket_items, self._basket_total)
        pay_btn = self.query_one("#pay-btn")
        if self._basket_items:
            pay_btn.remove_class("-empty")
        else:
            pay_btn.add_class("-empty")

    # ── Scan handling ─────────────────────────────────────────

    @on(Input.Submitted, "#scan-input")
    async def handle_scan(self, event: Input.Submitted) -> None:
        barcode = event.value.strip()
        event.input.value = ""
        event.input.focus()
        if not barcode:
            return

        now = time.monotonic()
        if now - self._last_scan_at < 0.4:
            return  # debounce: swallow rapid double-fire from scanner
        self._last_scan_at = now

        if not is_valid_barcode(barcode):
            self.query_one(ScanDisplay).show_book(
                f"Bad scan: {barcode}", "Not a valid barcode — try again", "", ok=False
            )
            return

        await self._process_barcode(barcode)

    async def _process_barcode(self, barcode: str) -> None:
        scan = self.query_one(ScanDisplay)

        # In-house barcodes: catalog-only, never query external APIs
        if barcode.startswith(self._inhouse_prefix):
            from app.catalog import get_item
            item = get_item(barcode, self.conn)
            if item is None:
                scan.show_book(
                    f"In-house code: {barcode}",
                    "Not registered — run gen_barcode.py --add", "", ok=False,
                )
                return
        else:
            item = resolve_barcode(barcode, self.conn, self.config, self.logger)

        if item is None:
            self.logger.warning(f"Unknown barcode scanned: {barcode}")
            scan.show_book(f"{self._ui.get('barcode_label', 'Barcode')}: {barcode}", "Not found in databanks", "", ok=False)
            self.conn.execute("""
                INSERT INTO sales (barcode, title, quantity, price, sold_at)
                VALUES (?, ?, 1, NULL, ?)
            """, (barcode, "UNKNOWN", datetime.now().isoformat()))
            self.conn.commit()
            self.query_one(FooterBar).refresh_quote()
            return

        price = item.get("price")
        if price is None:
            def on_price(entered_price: float | None) -> None:
                if entered_price is not None:
                    self._finalize_book_sale(barcode, item, entered_price)
                self.query_one("#scan-input").focus()
            self.push_screen(PriceEntryScreen(item["title"]), callback=on_price)
        else:
            self._finalize_book_sale(barcode, item, price)

    def _finalize_book_sale(self, barcode: str, item: dict, price: float | None) -> None:
        title = item["title"]
        author = item.get("author", "")
        price_str = f"€{price:.2f}" if price else "price not recorded"

        if self._txn_id is None:
            self._txn_id = self._new_txn_id()

        record_sale(barcode, title, price, self.conn, transaction_id=self._txn_id)
        new_stock = decrement_stock(barcode, self.conn)

        self._basket_items += 1
        self._basket_total += price or 0.0
        self._daily_items += 1
        self._daily_revenue += price or 0.0

        self.query_one(ScanDisplay).show_book(title, author, price_str, ok=True)
        self.query_one(DailyManifest).update_totals(
            self._daily_items, self._daily_revenue, self._daily_cash, self._daily_card
        )
        self._update_basket_display()
        self.query_one(FooterBar).refresh_quote()
        self.logger.info(f"Sale: '{title}' {price_str} — stock now {new_stock}")

        if new_stock <= self.low_threshold:
            alert = self.query_one(StockAlert)
            alert.show_alert(title, new_stock)
            if self._alert_timer:
                self._alert_timer.stop()
            self._alert_timer = self.set_timer(5, alert.clear_alert)

    # ── Non-barcode items ──────────────────────────────────────

    def action_select_item(self, key: str) -> None:
        self._select_item_index(int(key))

    @on(Button.Pressed, ".nonisbn-btn")
    def _click_non_isbn(self, event: Button.Pressed) -> None:
        panel = self.query_one(NonIsbnPanel)
        idx = panel.index_from_button_id(event.button.id or "")
        if idx is not None:
            self._select_item_index(idx)

    def _select_item_index(self, index: int) -> None:
        panel = self.query_one(NonIsbnPanel)
        item = panel.get_item(index)
        if item is None:
            return

        if item.get("price"):
            self._log_misc_item(item, item["price"])
            self.query_one("#scan-input").focus()
        else:
            def on_price(price: float | None) -> None:
                if price is not None:
                    self._log_misc_item(item, price)
                self.query_one("#scan-input").focus()

            self.push_screen(PriceEntryScreen(item["name"]), callback=on_price)

    def _log_misc_item(self, item: dict, price: float | None) -> None:
        name = item["name"]
        price_str = f"€{price:.2f}" if price else "no price"

        if self._txn_id is None:
            self._txn_id = self._new_txn_id()

        self.conn.execute("""
            INSERT INTO sales (barcode, title, quantity, price, sold_at, transaction_id)
            VALUES (?, ?, 1, ?, ?, ?)
        """, (None, name, price, datetime.now().isoformat(), self._txn_id))
        self.conn.commit()

        self._basket_items += 1
        self._basket_total += price or 0.0
        self._daily_items += 1
        self._daily_revenue += price or 0.0

        self.query_one(ScanDisplay).show_item(name, price_str)
        self.query_one(DailyManifest).update_totals(
            self._daily_items, self._daily_revenue, self._daily_cash, self._daily_card
        )
        self._update_basket_display()
        self.query_one(FooterBar).refresh_quote()
        self.logger.info(f"Misc item sale: '{name}' {price_str}")

    async def _show_stock_alert(self, title: str, stock: int) -> None:
        alert = self.query_one(StockAlert)
        alert.show_alert(title, stock)
        if self._alert_timer:
            self._alert_timer.stop()
        self._alert_timer = self.set_timer(5, alert.clear_alert)

    # ── Subtotal / Pay ─────────────────────────────────────────

    @on(Button.Pressed, "#pay-btn")
    def _click_pay(self) -> None:
        self.action_pay()

    def action_pay(self) -> None:
        if not self._txn_id or self._basket_items == 0:
            return

        txn_id = self._txn_id
        basket_items = self._basket_items
        basket_total = self._basket_total

        def on_payment(method: str | None) -> None:
            if method:
                self.conn.execute(
                    "UPDATE sales SET payment_method = ? WHERE transaction_id = ? AND voided = 0",
                    (method, txn_id),
                )
                self.conn.commit()
                self.logger.info(
                    f"Payment: {method}  txn={txn_id}  "
                    f"{basket_items} items  €{basket_total:.2f}"
                )
                if method == "cash":
                    self._daily_cash += basket_total
                elif method == "card":
                    self._daily_card += basket_total
                self._txn_id = None
                self._basket_items = 0
                self._basket_total = 0.0
                self._update_basket_display()
                self.query_one(DailyManifest).update_totals(
                    self._daily_items, self._daily_revenue,
                    self._daily_cash, self._daily_card,
                )
                scan = self.query_one(ScanDisplay)
                scan.show_sale_complete(basket_total, method, basket_items)
            self.query_one("#scan-input").focus()

        self.push_screen(
            PaymentScreen(total=basket_total, item_count=basket_items),
            callback=on_payment,
        )

    # ── Discount ──────────────────────────────────────────────

    @on(Button.Pressed, "#discount-btn")
    def _click_discount(self) -> None:
        self.action_discount()

    def action_discount(self) -> None:
        if not self._txn_id or self._basket_items == 0:
            return

        def on_discount(amount: float | None) -> None:
            if amount is not None and amount > 0:
                self._apply_discount(min(amount, self._basket_total))
            self.query_one("#scan-input").focus()

        self.push_screen(
            PriceEntryScreen("Discount", label="  Enter discount amount (€):"),
            callback=on_discount,
        )

    def _apply_discount(self, amount: float) -> None:
        if self._txn_id is None:
            return
        price_str = f"-€{amount:.2f}"

        self.conn.execute("""
            INSERT INTO sales (barcode, title, quantity, price, sold_at, transaction_id)
            VALUES (NULL, 'Discount', 1, ?, ?, ?)
        """, (-amount, datetime.now().isoformat(), self._txn_id))
        self.conn.commit()

        self._basket_items += 1
        self._basket_total = max(0.0, self._basket_total - amount)
        self._daily_items += 1
        self._daily_revenue -= amount

        self.query_one(ScanDisplay).show_item("Discount", price_str)
        self.query_one(DailyManifest).update_totals(
            self._daily_items, self._daily_revenue, self._daily_cash, self._daily_card
        )
        self._update_basket_display()
        self.query_one(FooterBar).refresh_quote()
        self.logger.info(f"Discount applied: {price_str}  txn={self._txn_id}")

    # ── Undo ──────────────────────────────────────────────────

    def action_undo_sale(self) -> None:
        sale = void_last_sale(self.conn, self.logger)
        scan = self.query_one(ScanDisplay)

        if sale is None:
            scan.show_book("Nothing to undo", "No sales recorded today", "", ok=False)
            return

        title = sale.get("title") or "Unknown"
        price = sale.get("price") or 0.0
        price_str = f"€{price:.2f}" if price else "no price"

        if self._txn_id and sale.get("transaction_id") == self._txn_id:
            self._basket_items = max(0, self._basket_items - (sale.get("quantity") or 1))
            self._basket_total = max(0.0, self._basket_total - price)
            if self._basket_items == 0:
                self._txn_id = None
            self._update_basket_display()

        self._daily_items = max(0, self._daily_items - (sale.get("quantity") or 1))
        self._daily_revenue = max(0.0, self._daily_revenue - price)
        method = sale.get("payment_method")
        if method == "cash":
            self._daily_cash = max(0.0, self._daily_cash - price)
        elif method == "card":
            self._daily_card = max(0.0, self._daily_card - price)

        scan.show_book(
            f"VOIDED: {title}", f"Sale removed  ·  {price_str} reversed", "", ok=False
        )
        self.query_one(DailyManifest).update_totals(
            self._daily_items, self._daily_revenue, self._daily_cash, self._daily_card
        )
        self.query_one(FooterBar).refresh_quote()

    # ── Back ──────────────────────────────────────────────────

    @on(Button.Pressed, "#back-btn")
    def _click_back(self) -> None:
        self.exit()

    def action_go_back(self) -> None:
        self.exit()


def main():
    app = CounterApp()
    app.run()


if __name__ == "__main__":
    main()
