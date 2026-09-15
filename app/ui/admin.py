# SPDX-License-Identifier: AGPL-3.0-or-later
"""
admin.py - Admin mode. PIN protected.

For managers only.
Sales log, daily reports, and manual book entry.
Catalog browsing, price and stock management are in Intake Mode.

"Insufficient facts always invite danger." — Spock
"""

from textual.app import App, ComposeResult
from textual.widgets import Static, Input, DataTable, Button
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual.screen import Screen, ModalScreen
from textual import on

from datetime import datetime, timedelta
from app.utils import load_config, get_logger, format_date, parse_date_str, is_mount_available, timestamp_now
from app.catalog import get_db
from app.summary import write_daily_report, get_daily_sales, get_sales_summary, get_sales_tally, write_tally_csv
from app.ui.quotes import get_quote_display
from app.ui.widgets import BackButton, HintBar


CSS = """
#header {
    width: 1fr;
    height: 3;
    background: #1a1a3a;
    color: #8a8aba;
    text-align: center;
    content-align: center middle;
    padding: 0 2;
    text-style: bold;
}

#topbar {
    height: 3;
    background: #1a1a3a;
    border-bottom: solid #2a2a5a;
}

#main-menu, #sales-panel, #report-panel {
    height: 1fr;
    overflow-y: auto;
}

.section-heading {
    color: #6a6aaa;
    border-bottom: solid #1a1a3a;
    padding: 0 1;
    margin: 1 0 0 0;
}

.menu-item {
    width: 100%;
    height: 4;
    margin: 0 1 1 1;
    text-align: left;
    content-align: left middle;
    padding: 0 2;
    background: #0f0f2a;
    border: solid #1a1a4a;
    color: #c8b89a;
}

.menu-item:hover {
    background: #1a1a4a;
    border: solid #6a6aaa;
    color: #d4af37;
}

.menu-item:focus {
    border: solid #d4af37;
    text-style: bold;
}

#footer {
    background: #1a1a3a;
    color: #3a3a6a;
    border-top: solid #1a1a3a;
    padding: 0 1;
    height: 3;
    content-align: left middle;
    text-style: italic;
}

DataTable {
    background: #0f0f2a;
    border: solid #1a1a4a;
    margin: 0 1;
    height: 1fr;
}

#mount-status {
    padding: 0 2;
    height: auto;
    margin-bottom: 1;
}

#report-destination {
    color: #6a6a8a;
    padding: 0 2;
    height: auto;
    margin-bottom: 1;
    text-style: italic;
}

#report-result {
    padding: 0 2;
    height: auto;
    margin-top: 1;
}

#sales-totals {
    padding: 0 2;
    height: auto;
    margin: 0 1 0 1;
    color: #c8b89a;
    border-top: solid #1a1a4a;
}

#sales-actions {
    height: 3;
    margin: 1 1 0 1;
}

#tally-totals {
    padding: 0 2;
    height: auto;
    margin: 0 1 0 1;
    color: #c8b89a;
    border-top: solid #1a1a4a;
}

#tally-export-result {
    padding: 0 2;
    height: auto;
    margin: 0 1 0 1;
    color: #4aaa7a;
}

#tally-period-bar {
    height: 3;
    margin: 0 1 0 1;
}

#report-date-bar {
    height: 3;
    margin: 0 1 1 1;
}

#report-date-input {
    width: 20;
    background: #0f0f2a;
    border: solid #1a1a4a;
    color: #d4af37;
}
#report-date-input:focus { border: solid #d4af37; }

.tally-period-btn {
    width: auto;
    min-width: 18;
    height: 3;
    background: #0f0f2a;
    border: solid #1a1a4a;
    color: #6a6aaa;
    content-align: center middle;
}
.tally-period-btn:hover { background: #1a1a4a; color: #c8b89a; }
.tally-period-btn:focus { border: solid #d4af37; color: #d4af37; }
.tally-period-btn.-active {
    background: #1a1a4a;
    border: solid #6a6aaa;
    color: #d4af37;
    text-style: bold;
}

#tally-export-btn {
    width: auto;
    min-width: 20;
    height: 3;
    background: #0a1f0a;
    border: solid #4aaa7a;
    color: #4aaa7a;
    content-align: center middle;
    margin-left: 2;
}
#tally-export-btn:hover { background: #0f2f0f; }
#tally-export-btn:focus { border: solid #6aff6a; color: #6aff6a; }

#btn-void-sale {
    width: auto;
    min-width: 22;
    height: 3;
    background: #1f0a0a;
    border: solid #aa4a4a;
    color: #aa4a4a;
    content-align: center middle;
}
#btn-void-sale:disabled { background: #0f0f1a; border: solid #2a2a4a; color: #3a3a6a; }
#btn-void-sale:hover { background: #2f0f0f; }
#btn-void-sale:focus { border: solid #ff6b6b; color: #ff6b6b; }

#sales-action-result {
    color: #4aaa7a;
    padding: 0 2;
    height: auto;
    margin: 0 1 0 1;
}

#orphan-panel {
    height: 1fr;
    overflow-y: auto;
}

#orphan-actions {
    height: 3;
    margin: 1 1 0 1;
}

#btn-assign-cash {
    width: auto;
    min-width: 22;
    height: 3;
    background: #0a1f0a;
    border: solid #4aaa7a;
    color: #4aaa7a;
    content-align: center middle;
}
#btn-assign-cash:disabled { background: #0f0f1a; border: solid #2a2a4a; color: #3a3a6a; }
#btn-assign-cash:hover { background: #0f2f0f; }
#btn-assign-cash:focus { border: solid #6aff6a; color: #6aff6a; }

#btn-assign-card {
    width: auto;
    min-width: 22;
    height: 3;
    margin-left: 1;
    background: #0a0a1f;
    border: solid #6a6aaa;
    color: #6a6aaa;
    content-align: center middle;
}
#btn-assign-card:disabled { background: #0f0f1a; border: solid #2a2a4a; color: #3a3a6a; }
#btn-assign-card:hover { background: #0f0f2f; }
#btn-assign-card:focus { border: solid #aaaaff; color: #aaaaff; }

#orphan-result {
    color: #4aaa7a;
    padding: 0 2;
    height: auto;
    margin: 0 1 0 1;
}

#orphan-count {
    padding: 0 2;
    height: auto;
    margin: 0 1 0 1;
    color: #c8b89a;
    border-top: solid #1a1a4a;
}
"""


class PinScreen(Screen):
    """PIN entry screen shown before admin access."""

    DEFAULT_CSS = """
    Screen { background: #09091f; align: center middle; }

    #pin-container {
        width: 80%;
        max-width: 60;
        min-width: 36;
        height: auto;
        border: solid #2a2a5a;
        background: #0f0f2a;
        padding: 2 4;
    }

    #pin-label {
        color: #6a6aaa;
        text-align: center;
        margin-bottom: 2;
    }

    #pin-input {
        background: #09091f;
        border: solid #2a2a5a;
        color: #d4af37;
        text-align: center;
    }

    #pin-error {
        color: #ff6b6b;
        text-align: center;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self, correct_pin: str, **kwargs):
        super().__init__(**kwargs)
        self._correct_pin = correct_pin

    def compose(self) -> ComposeResult:
        with Vertical(id="pin-container"):
            yield Static(
                "✦  ADMIN MODE\n\nEnter PIN to continue:",
                id="pin-label",
            )
            yield Input(password=True, id="pin-input", placeholder="····")
            yield Static("", id="pin-error")

    def on_mount(self) -> None:
        self.query_one("#pin-input").focus()

    @on(Input.Submitted, "#pin-input")
    def check_pin(self, event: Input.Submitted) -> None:
        if event.value == self._correct_pin:
            self.dismiss(True)
        else:
            self.query_one("#pin-error").update("⚠  Incorrect PIN")
            self.query_one("#pin-input").value = ""


class SalePaymentScreen(ModalScreen):
    """Payment method selector for manually logging a sale from the catalog."""

    DEFAULT_CSS = """
    SalePaymentScreen { align: center middle; }

    #sale-dialog {
        width: 52;
        height: auto;
        background: #0f0f2a;
        border: double #d4af37;
        padding: 2 3;
    }

    #sale-book-title {
        color: #e8dcc8;
        text-align: center;
        text-style: bold;
        margin-bottom: 0;
    }

    #sale-book-price {
        color: #d4af37;
        text-align: center;
        margin-bottom: 2;
    }

    .sale-btn {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        content-align: center middle;
        text-style: bold;
    }

    #sale-btn-cash { background: #0a1f0a; border: solid #4aaa7a; color: #4aaa7a; }
    #sale-btn-cash:hover { background: #0f2f0f; }
    #sale-btn-card { background: #0a0a1f; border: solid #6a6aaa; color: #6a6aaa; }
    #sale-btn-card:hover { background: #0f0f2f; }

    #sale-hint { color: #3a3a6a; text-align: center; text-style: italic; margin-top: 1; }
    """

    BINDINGS = [
        Binding("c", "cash", "Cash", show=False),
        Binding("k", "card", "Card", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, title: str, price: float | None, **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._price = price

    def compose(self) -> ComposeResult:
        price_str = f"€{self._price:.2f}" if self._price else "no price recorded"
        with Vertical(id="sale-dialog"):
            yield Static(self._title[:44], id="sale-book-title")
            yield Static(price_str, id="sale-book-price")
            yield Button("[C]  Cash", id="sale-btn-cash", classes="sale-btn")
            yield Button("[K]  Card", id="sale-btn-card", classes="sale-btn")
            yield Static("Esc to cancel", id="sale-hint")

    def action_cash(self) -> None: self.dismiss("cash")
    def action_card(self) -> None: self.dismiss("card")
    def action_cancel(self) -> None: self.dismiss(None)

    @on(Button.Pressed, "#sale-btn-cash")
    def _cash(self) -> None: self.dismiss("cash")

    @on(Button.Pressed, "#sale-btn-card")
    def _card(self) -> None: self.dismiss("card")


class VoidConfirmScreen(ModalScreen):
    """Confirm before voiding a selected sale."""

    DEFAULT_CSS = """
    VoidConfirmScreen { align: center middle; }

    #void-dialog {
        width: 52;
        height: auto;
        background: #0f0f2a;
        border: double #ff6b6b;
        padding: 2 3;
    }

    #void-heading {
        color: #ff6b6b;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #void-detail {
        color: #c8b89a;
        text-align: center;
        margin-bottom: 2;
    }

    #void-btn-confirm {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        content-align: center middle;
        text-style: bold;
        background: #1f0a0a;
        border: solid #ff6b6b;
        color: #ff6b6b;
    }
    #void-btn-confirm:hover { background: #2f0f0f; }

    #void-btn-cancel {
        width: 100%;
        height: 3;
        content-align: center middle;
        background: #1a1a2a;
        border: solid #4a4a6a;
        color: #6a6a9a;
    }
    #void-btn-cancel:hover { background: #2a2a4a; }

    #void-hint { color: #3a3a6a; text-align: center; text-style: italic; margin-top: 1; }
    """

    BINDINGS = [
        Binding("v", "confirm", "Void", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, title: str, price: float | None, time_str: str, **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._price = price
        self._time_str = time_str

    def compose(self) -> ComposeResult:
        price_str = f"€{self._price:.2f}" if self._price else "no price recorded"
        with Vertical(id="void-dialog"):
            yield Static("VOID SALE", id="void-heading")
            yield Static(
                f"{self._title[:44]}\n{price_str}  ·  {self._time_str}",
                id="void-detail",
            )
            yield Button("[V]  Confirm Void", id="void-btn-confirm")
            yield Button("Cancel  [Esc]", id="void-btn-cancel")
            yield Static("Esc to cancel", id="void-hint")

    def action_confirm(self) -> None: self.dismiss(True)
    def action_cancel(self) -> None: self.dismiss(False)

    @on(Button.Pressed, "#void-btn-confirm")
    def _confirm(self) -> None: self.dismiss(True)

    @on(Button.Pressed, "#void-btn-cancel")
    def _cancel(self) -> None: self.dismiss(False)


class AdminApp(App):
    """
    Admin mode — price changes, stock corrections, sales log.
    PIN protected at launch.
    """

    CSS_PATH = "theme.tcss"
    CSS = CSS

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("1", "menu_sales", "Sales log", show=True),
        Binding("2", "menu_report", "Send report", show=True),
        Binding("3", "menu_tally", "Sales tally", show=True),
        Binding("4", "menu_orphans", "Fix orphaned", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.logger = get_logger("admin", self.config)
        self.conn = get_db(self.config)
        self._pin = str(self.config.get("admin", {}).get("pin", "0000"))
        self._mode = "menu"           # menu | sales | report
        self._current_item = None
        self._sales_table_ready = False
        self._sales_selected_id: int | None = None
        self._tally_table_ready = False
        self._tally_period: str = "today"  # today | month | all
        self._orphan_table_ready = False
        self._orphan_selected_txn: str | None = None
        self._report_date: str = format_date()

    def compose(self) -> ComposeResult:
        app_title = self.config.get("ui", {}).get("app_title", "Shop")
        with Horizontal(id="topbar"):
            yield Static(f"✦  ADMIN  ·  {app_title.upper()}", id="header")
            yield BackButton("← Menu  [Esc]", id="back-btn")

        # Main menu
        with Vertical(id="main-menu"):
            yield Static("Select an option (click or press 1 – 3):", classes="section-heading")
            yield Button(
                "[1]  View today's sales log  —  See all transactions for today",
                classes="menu-item", id="menu-sales",
            )
            yield Button(
                "[2]  Send report  —  Write CSV to office share (or sync/ fallback)",
                classes="menu-item", id="menu-report",
            )
            yield Button(
                "[3]  Sales tally  —  See what's selling today, grouped by item",
                classes="menu-item", id="menu-tally",
            )
            yield Button(
                "[4]  Fix orphaned transactions  —  Assign payment method to unconfirmed sales",
                classes="menu-item", id="menu-orphans",
            )

        # Sales log panel
        with Vertical(id="sales-panel"):
            yield Static("TODAY'S SALES LOG", classes="section-heading")
            yield DataTable(id="sales-table", cursor_type="row")
            with Horizontal(id="sales-actions"):
                yield Button("  ✗  Void Selected", id="btn-void-sale", disabled=True)
            yield Static("", id="sales-action-result")
            yield Static("", id="sales-totals")

        # Sales tally panel
        with Vertical(id="tally-panel"):
            yield Static("SALES TALLY", classes="section-heading")
            with Horizontal(id="tally-period-bar"):
                yield Button("[T] Today",      id="tally-today",      classes="tally-period-btn -active")
                yield Button("[M] This Month", id="tally-month",      classes="tally-period-btn")
                yield Button("[A] All Time",   id="tally-all",        classes="tally-period-btn")
                yield Button("↓  Export CSV",  id="tally-export-btn")
            yield DataTable(id="tally-table", cursor_type="row")
            yield Static("", id="tally-totals")
            yield Static("", id="tally-export-result")

        # Orphaned transactions panel
        with Vertical(id="orphan-panel"):
            yield Static("ORPHANED TRANSACTIONS", classes="section-heading")
            yield DataTable(id="orphan-table", cursor_type="row")
            with Horizontal(id="orphan-actions"):
                yield Button("[C]  Assign Cash", id="btn-assign-cash", disabled=True)
                yield Button("[K]  Assign Card", id="btn-assign-card", disabled=True)
            yield Static("", id="orphan-result")
            yield Static("", id="orphan-count")

        # Report panel
        with Vertical(id="report-panel"):
            yield Static("SEND REPORT", classes="section-heading")
            with Horizontal(id="report-date-bar"):
                yield Button("[T] Today", id="report-date-today", classes="tally-period-btn -active")
                yield Button("[Y] Yesterday", id="report-date-yesterday", classes="tally-period-btn")
                yield Input(id="report-date-input", placeholder="YYYY-MM-DD", value=format_date())
            yield Static("", id="mount-status")
            yield Static("", id="report-destination")
            yield Button("  ✦  Send Report", id="send-report-btn", classes="menu-item")
            yield Static("", id="report-result")

        yield HintBar(id="hint-bar")
        yield Static(get_quote_display(), id="footer")

    def on_mount(self) -> None:
        self._hide_all_panels()
        self.query_one(HintBar).update_from(self.BINDINGS)
        self.push_screen(
            PinScreen(correct_pin=self._pin),
            callback=self._pin_result,
        )

    def _pin_result(self, success: bool) -> None:
        if not success:
            self.exit()

    _ALL_PANELS = ("main-menu", "sales-panel", "tally-panel", "orphan-panel", "report-panel")

    def _hide_all_panels(self) -> None:
        for panel_id in self._ALL_PANELS:
            try:
                w = self.query_one(f"#{panel_id}")
                w.styles.display = "block" if panel_id == "main-menu" else "none"
            except Exception:
                pass

    def _show_panel(self, panel_id: str) -> None:
        for pid in self._ALL_PANELS:
            self.query_one(f"#{pid}").styles.display = (
                "block" if pid == panel_id else "none"
            )

    def _setup_sales_table(self) -> None:
        table = self.query_one("#sales-table", DataTable)
        barcode_label = self.config.get("ui", {}).get("barcode_label", "Barcode")
        table.add_columns("Time", "Title", "Price", "Payment", barcode_label)

    def _load_sales_table(self) -> None:
        table = self.query_one("#sales-table", DataTable)
        table.clear()
        self._sales_selected_id = None
        self.query_one("#btn-void-sale", Button).disabled = True
        self.query_one("#sales-action-result").update("")
        today = format_date()
        rows = self.conn.execute("""
            SELECT id, sold_at, title, price, barcode, voided, payment_method
            FROM sales
            WHERE DATE(sold_at) = ?
            ORDER BY sold_at DESC
        """, (today,)).fetchall()
        for row in rows:
            voided = row["voided"]
            time_str = row["sold_at"][11:16] if row["sold_at"] else ""
            price_str = f"€{row['price']:.2f}" if row["price"] else "—"
            title_str = (row["title"] or "")[:36]
            pay_str = (row["payment_method"] or "—").upper()
            if voided:
                table.add_row(
                    f"✗ {time_str}",
                    f"[VOID] {title_str}",
                    price_str,
                    pay_str,
                    row["barcode"] or "—",
                    key=str(row["id"]),
                )
            else:
                table.add_row(
                    time_str,
                    title_str,
                    price_str,
                    pay_str,
                    row["barcode"] or "—",
                    key=str(row["id"]),
                )

        live = [r for r in rows if not r["voided"]]
        total = sum(r["price"] or 0.0 for r in live)
        cash  = sum(r["price"] or 0.0 for r in live if r["payment_method"] == "cash")
        card  = sum(r["price"] or 0.0 for r in live if r["payment_method"] == "card")
        n = len(live)
        self.query_one("#sales-totals").update(
            f"  {n} sale{'s' if n != 1 else ''}  ·  "
            f"Total: €{total:.2f}  ·  Cash: €{cash:.2f}  ·  Card: €{card:.2f}"
        )

    # ── Menu actions: keyboard + click both route here ────────

    def action_menu_sales(self) -> None:
        if not self._sales_table_ready:
            self._setup_sales_table()
            self._sales_table_ready = True
        self._load_sales_table()
        self._show_panel("sales-panel")
        self._mode = "sales"

    @on(DataTable.RowHighlighted, "#sales-table")
    def _sales_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        key = str(event.row_key.value) if event.row_key else None
        try:
            self._sales_selected_id = int(key) if key else None
        except (ValueError, TypeError):
            self._sales_selected_id = None
        can_void = False
        if self._sales_selected_id is not None:
            sale_row = self.conn.execute(
                "SELECT voided FROM sales WHERE id = ?", (self._sales_selected_id,)
            ).fetchone()
            can_void = sale_row is not None and not sale_row["voided"]
        self.query_one("#btn-void-sale", Button).disabled = not can_void

    @on(Button.Pressed, "#btn-void-sale")
    def _click_void_sale(self) -> None:
        sale_id = self._sales_selected_id
        if sale_id is None:
            return
        sale_row = self.conn.execute(
            "SELECT title, price, sold_at FROM sales WHERE id = ? AND voided = 0",
            (sale_id,),
        ).fetchone()
        if not sale_row:
            return
        time_str = sale_row["sold_at"][11:16] if sale_row["sold_at"] else ""
        self.push_screen(
            VoidConfirmScreen(sale_row["title"] or "", sale_row["price"], time_str),
            callback=lambda confirmed: self._on_void_confirmed(confirmed, sale_id),
        )

    def _on_void_confirmed(self, confirmed: bool, sale_id: int) -> None:
        if not confirmed:
            return
        sale_row = self.conn.execute(
            "SELECT * FROM sales WHERE id = ?", (sale_id,)
        ).fetchone()
        if not sale_row or sale_row["voided"]:
            return
        sale = dict(sale_row)
        self.conn.execute("UPDATE sales SET voided = 1 WHERE id = ?", (sale_id,))
        if sale.get("barcode"):
            qty = sale.get("quantity") or 1
            self.conn.execute(
                "UPDATE catalog SET stock = stock + ?, updated_at = ? WHERE barcode = ?",
                (qty, timestamp_now(), sale["barcode"]),
            )
        self.conn.commit()
        self.logger.info(f"Admin: voided sale id={sale_id} '{sale.get('title')}'")
        price_str = f"€{sale['price']:.2f}" if sale.get("price") else "—"
        self._load_sales_table()
        self.query_one("#sales-action-result").update(
            f"✦  Voided:  '{sale.get('title', '')}  ·  {price_str}"
        )

    @on(Button.Pressed, "#menu-sales")
    def _click_sales(self) -> None:
        self.action_menu_sales()

    def action_menu_report(self) -> None:
        self._show_panel("report-panel")
        self._mode = "report"
        self._report_date = format_date()
        self.query_one("#report-date-input", Input).value = self._report_date
        self._set_report_date_active("report-date-today")
        self._refresh_report_destination()
        self.query_one("#report-result").update("")

    def _refresh_report_destination(self) -> None:
        mount_path = self.config["office_sync"]["mount_path"]
        subdir = self.config["office_sync"]["report_subdir"]
        fallback = self.config["office_sync"]["fallback_local"]
        year, month = self._report_date[:4], self._report_date[5:7]
        if is_mount_available(mount_path):
            self.query_one("#mount-status").update(
                f"✦  Office share connected  ({mount_path})"
            )
            self.query_one("#report-destination").update(
                f"   Report for {self._report_date} will go to: {mount_path}/{subdir}/{year}/{month}/"
            )
        else:
            self.query_one("#mount-status").update(
                f"⚠  Office share not available  ({mount_path})"
            )
            self.query_one("#report-destination").update(
                f"   Report for {self._report_date} will be saved locally to: {fallback}{year}/{month}/"
            )

    def _set_report_date_active(self, active_id: str | None) -> None:
        for btn_id in ("report-date-today", "report-date-yesterday"):
            btn = self.query_one(f"#{btn_id}", Button)
            if btn_id == active_id:
                btn.add_class("-active")
            else:
                btn.remove_class("-active")

    @on(Button.Pressed, "#report-date-today")
    def _report_date_today(self) -> None:
        self._report_date = format_date()
        self.query_one("#report-date-input", Input).value = self._report_date
        self._set_report_date_active("report-date-today")
        self._refresh_report_destination()
        self.query_one("#report-result").update("")

    @on(Button.Pressed, "#report-date-yesterday")
    def _report_date_yesterday(self) -> None:
        self._report_date = format_date(datetime.now() - timedelta(days=1))
        self.query_one("#report-date-input", Input).value = self._report_date
        self._set_report_date_active("report-date-yesterday")
        self._refresh_report_destination()
        self.query_one("#report-result").update("")

    @on(Input.Submitted, "#report-date-input")
    def _report_date_submitted(self, event: Input.Submitted) -> None:
        parsed = parse_date_str(event.value)
        if parsed is None:
            self.query_one("#report-result").update("⚠  Invalid date — use YYYY-MM-DD")
            return
        if parsed > format_date():
            self.query_one("#report-result").update("⚠  Can't pick a future date")
            return
        self._report_date = parsed
        self._set_report_date_active(None)
        self._refresh_report_destination()
        self.query_one("#report-result").update("")

    def action_menu_tally(self) -> None:
        if not self._tally_table_ready:
            table = self.query_one("#tally-table", DataTable)
            table.add_columns("Type", "Title", "Qty", "Revenue", "Cash", "Card")
            self._tally_table_ready = True
        self._tally_period = "today"
        self._set_tally_period_active("tally-today")
        self._load_tally_table()
        self._show_panel("tally-panel")
        self._mode = "tally"

    def _tally_date_range(self) -> tuple[str, str]:
        today = format_date()
        if self._tally_period == "today":
            return today, today
        if self._tally_period == "month":
            year, month = today[:4], today[5:7]
            return f"{year}-{month}-01", today
        # all
        return "2000-01-01", today

    def _load_tally_table(self) -> None:
        table = self.query_one("#tally-table", DataTable)
        table.clear()
        self.query_one("#tally-export-result").update("")
        inhouse_prefix = self.config.get("catalog", {}).get("inhouse_prefix", "2000001")
        start, end = self._tally_date_range()
        rows = get_sales_tally(self.conn, start, end, inhouse_prefix=inhouse_prefix)
        for r in rows:
            table.add_row(
                r["item_type"],
                (r["title"] or "")[:38],
                str(r["qty"]),
                f"€{r['revenue']:.2f}",
                f"€{r['cash']:.2f}",
                f"€{r['card']:.2f}",
            )
        total_qty = sum(r["qty"] for r in rows)
        total_rev = sum(r["revenue"] for r in rows)
        total_cash = sum(r["cash"] for r in rows)
        total_card = sum(r["card"] for r in rows)
        n = len(rows)
        label = {"today": "today", "month": "this month", "all": "all time"}[self._tally_period]
        self.query_one("#tally-totals").update(
            f"  {n} distinct item{'s' if n != 1 else ''} sold {label}  ·  "
            f"{total_qty} units  ·  Total: €{total_rev:.2f}  ·  "
            f"Cash: €{total_cash:.2f}  ·  Card: €{total_card:.2f}"
        )

    def _set_tally_period_active(self, active_id: str) -> None:
        for btn_id in ("tally-today", "tally-month", "tally-all"):
            btn = self.query_one(f"#{btn_id}", Button)
            if btn_id == active_id:
                btn.add_class("-active")
            else:
                btn.remove_class("-active")

    @on(Button.Pressed, "#tally-today")
    def _tally_period_today(self) -> None:
        self._tally_period = "today"
        self._set_tally_period_active("tally-today")
        self._load_tally_table()

    @on(Button.Pressed, "#tally-month")
    def _tally_period_month(self) -> None:
        self._tally_period = "month"
        self._set_tally_period_active("tally-month")
        self._load_tally_table()

    @on(Button.Pressed, "#tally-all")
    def _tally_period_all(self) -> None:
        self._tally_period = "all"
        self._set_tally_period_active("tally-all")
        self._load_tally_table()

    @on(Button.Pressed, "#tally-export-btn")
    def _tally_export(self) -> None:
        today = format_date()
        inhouse_prefix = self.config.get("catalog", {}).get("inhouse_prefix", "2000001")
        start, end = self._tally_date_range()
        rows = get_sales_tally(self.conn, start, end, inhouse_prefix=inhouse_prefix)
        label = {"today": "today", "month": "month", "all": "alltime"}[self._tally_period]
        from app.utils import get_report_path
        report_dir = get_report_path(self.config, today)
        from datetime import datetime as _dt
        ts = _dt.now().strftime("%H%M%S")
        filepath = report_dir / f"tally_{label}_{today}_{ts}.csv"
        try:
            write_tally_csv(rows, filepath)
            self.logger.info(f"Tally exported: {filepath}")
            self.query_one("#tally-export-result").update(f"✦  Saved: {filepath}")
        except Exception as e:
            self.logger.error(f"Tally export failed: {e}")
            self.query_one("#tally-export-result").update(f"⚠  Error: {e}")

    @on(Button.Pressed, "#menu-tally")
    def _click_tally(self) -> None:
        self.action_menu_tally()

    @on(Button.Pressed, "#menu-report")
    def _click_report(self) -> None:
        self.action_menu_report()

    # ── Orphaned transactions ─────────────────────────────────

    def action_menu_orphans(self) -> None:
        if not self._orphan_table_ready:
            table = self.query_one("#orphan-table", DataTable)
            table.add_columns("Date", "Time", "Items", "Total", "Titles")
            self._orphan_table_ready = True
        self._load_orphan_table()
        self._show_panel("orphan-panel")
        self._mode = "orphan"

    def _load_orphan_table(self) -> None:
        table = self.query_one("#orphan-table", DataTable)
        table.clear()
        self._orphan_selected_txn = None
        self.query_one("#btn-assign-cash", Button).disabled = True
        self.query_one("#btn-assign-card", Button).disabled = True
        self.query_one("#orphan-result").update("")
        rows = self.conn.execute("""
            SELECT
                transaction_id,
                DATE(MIN(sold_at))                      AS sale_date,
                MIN(sold_at)                            AS sold_at,
                COUNT(*)                                AS item_count,
                SUM(COALESCE(price, 0) * quantity)      AS total,
                GROUP_CONCAT(title, ' / ')              AS titles
            FROM sales
            WHERE payment_method IS NULL AND voided = 0 AND transaction_id IS NOT NULL
            GROUP BY transaction_id
            ORDER BY sold_at DESC
        """).fetchall()
        for r in rows:
            time_str = r["sold_at"][11:16] if r["sold_at"] else ""
            table.add_row(
                r["sale_date"] or "",
                time_str,
                str(r["item_count"]),
                f"€{r['total']:.2f}",
                (r["titles"] or "")[:48],
                key=r["transaction_id"],
            )
        n = len(rows)
        total = sum(r["total"] for r in rows)
        if n:
            self.query_one("#orphan-count").update(
                f"  {n} unconfirmed transaction{'s' if n != 1 else ''}  ·  €{total:.2f} unassigned"
            )
        else:
            self.query_one("#orphan-count").update("  No orphaned transactions — all sales have a payment method.")

    @on(DataTable.RowHighlighted, "#orphan-table")
    def _orphan_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._orphan_selected_txn = str(event.row_key.value) if event.row_key else None
        enabled = self._orphan_selected_txn is not None
        self.query_one("#btn-assign-cash", Button).disabled = not enabled
        self.query_one("#btn-assign-card", Button).disabled = not enabled

    def _assign_to_orphan(self, method: str) -> None:
        txn = self._orphan_selected_txn
        if not txn:
            return
        self.conn.execute(
            "UPDATE sales SET payment_method = ? WHERE transaction_id = ? AND voided = 0 AND payment_method IS NULL",
            (method, txn),
        )
        self.conn.commit()
        self.logger.info(f"Admin: assigned {method} to orphaned txn={txn}")
        self.query_one("#orphan-result").update(f"✦  Assigned {method.upper()} to transaction {txn}")
        self._load_orphan_table()

    @on(Button.Pressed, "#btn-assign-cash")
    def _click_assign_cash(self) -> None:
        self._assign_to_orphan("cash")

    @on(Button.Pressed, "#btn-assign-card")
    def _click_assign_card(self) -> None:
        self._assign_to_orphan("card")

    @on(Button.Pressed, "#menu-orphans")
    def _click_orphans(self) -> None:
        self.action_menu_orphans()

    @on(Button.Pressed, "#send-report-btn")
    def _send_report(self) -> None:
        raw = self.query_one("#report-date-input", Input).value
        date_str = parse_date_str(raw)
        if date_str is None:
            self.query_one("#report-result").update("⚠  Invalid date — use YYYY-MM-DD")
            return
        if date_str > format_date():
            self.query_one("#report-result").update("⚠  Can't pick a future date")
            return
        try:
            report_dir = write_daily_report(date_str, self.config, self.logger)
            sales = get_daily_sales(date_str, self.conn)
            summary = get_sales_summary(sales)
            self.query_one("#report-result").update(
                f"✦  Report for {date_str}  ·  {summary['total_transactions']} transactions  ·  "
                f"€{summary['total_revenue']:.2f} revenue\n"
                f"   Written to: {report_dir}\n"
                f"   Files: sales, payments, summary, catalog"
            )
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            self.query_one("#report-result").update(f"⚠  Error: {e}")

    # ── Back: context-aware ───────────────────────────────────

    @on(Button.Pressed, "#back-btn")
    def _click_back(self) -> None:
        self.action_go_back()

    def action_quit(self) -> None:
        """Ctrl+Q exits the whole program, not just this mode."""
        self.exit(result="quit")

    def action_go_back(self) -> None:
        if self._mode == "menu":
            self.exit()
        else:
            self._mode = "menu"
            self._current_item = None
            self._show_panel("main-menu")
            self.query_one("#report-result").update("")
            self.query_one("#sales-action-result").update("")
            self.query_one("#tally-totals").update("")
            self.query_one("#tally-export-result").update("")
            self.query_one("#orphan-result").update("")
            self.query_one("#orphan-count").update("")
            self._sales_selected_id = None
            self._orphan_selected_txn = None
            try:
                self.query_one("#btn-void-sale", Button).disabled = True
            except Exception:
                pass

