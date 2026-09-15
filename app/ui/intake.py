# SPDX-License-Identifier: AGPL-3.0-or-later
"""
intake.py - Intake / Catalog mode.

Browse the full catalog, receive stock, and update prices and stock counts.
Scan a barcode to jump to an item or add new ones via optional API lookup.
No sales are logged here (use Log Sale button for manual entries only).
"""

from textual.app import App, ComposeResult
from textual.widgets import Static, Input, Button, DataTable
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import on

from datetime import datetime
from app.utils import load_config, get_logger, timestamp_now
from app.catalog import (
    get_db, add_item, get_item, is_valid_barcode, get_inhouse_prefix,
    make_inhouse_barcode, next_inhouse_number,
)
from app.barcode import generate_svg, generate_sheet
from app.ui.quotes import get_quote_display
from app.ui.widgets import BackButton, HintBar


CSS = """
#header {
    width: 1fr;
    height: 3;
    background: #0a1f12;
    color: #4aaa7a;
    text-align: center;
    content-align: center middle;
    padding: 0 2;
    text-style: bold;
}

#topbar {
    height: 3;
    background: #0a1f12;
    border-bottom: solid #2a7a4a;
}

#catalog-search-input {
    margin: 0 1;
    background: #0f0f2a;
    border: solid #2a2a5a;
    color: #c8b89a;
}

#catalog-count {
    color: #5a5a8a;
    padding: 0 2;
    height: 1;
}

#catalog-table {
    height: 1fr;
    margin: 0 1;
    background: #0f0f2a;
    border: solid #1a1a4a;
}

#selection-info {
    color: #c8b89a;
    height: 1;
    padding: 0 2;
}

#scan-input {
    height: 1;
    border: none;
    background: #09091f;
    color: #09091f;
    margin: 0;
    padding: 0;
}

#action-bar {
    height: 3;
    margin: 0 1;
}

.action-btn {
    height: 3;
    min-width: 14;
    margin-right: 1;
    background: #1a1a3a;
    border: solid #4a4a8a;
    color: #c8b89a;
    content-align: center middle;
}

.action-btn:hover { background: #2a2a4a; border: solid #6a6aaa; }
.action-btn:focus { border: solid #d4af37; color: #d4af37; }
.action-btn:disabled { color: #3a3a5a; border: solid #2a2a4a; background: #0f0f1a; }
.action-btn.receiving { background: #1a4a2a; border: solid #4aaa7a; color: #4aaa7a; text-style: bold; }

#footer {
    background: #0a1f12;
    color: #3a5a4a;
    border-top: solid #1a3a2a;
    padding: 0 1;
    height: 3;
    content-align: left middle;
    text-style: italic;
}
"""


# ── Shared modal CSS ─────────────────────────────────────────────────────────

_DIALOG_CSS = """
{cls} {{ align: center middle; }}

#dialog-box {{
    width: 62;
    height: auto;
    background: #0f0f2a;
    border: double {border};
    padding: 2 3;
}}

#dialog-title {{
    color: #e8dcc8;
    text-align: center;
    text-style: bold;
    margin-bottom: 0;
}}

#dialog-info {{
    color: #9a8a7a;
    text-align: center;
    margin-bottom: 2;
}}

#dialog-label {{ color: #c8b89a; margin-bottom: 1; }}

#dialog-input {{
    background: #09091f;
    border: solid {border};
    color: {border};
}}

#dialog-hint {{
    color: #3a3a6a;
    text-align: center;
    margin-top: 1;
    text-style: italic;
}}
"""


# ── Modal for new items found via API ────────────────────────────────────────

class PriceEntryScreen(ModalScreen):
    """Modal price entry for new items found via API."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="PriceEntryScreen", border="#d4af37")

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, author: str, extra: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._author = author
        self._extra = extra

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-box"):
            yield Static(self._title, id="dialog-title")
            info_parts = [p for p in (self._author, self._extra) if p]
            yield Static("  ".join(info_parts), id="dialog-info")
            yield Static("  Enter price (€):", id="dialog-label")
            yield Input(placeholder="0.00", id="dialog-input")
            yield Static(
                "  Enter to confirm   ·   Esc to add without price",
                id="dialog-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#dialog-input").focus()

    @on(Input.Submitted, "#dialog-input")
    def confirm(self, event: Input.Submitted) -> None:
        price_str = event.value.strip()
        try:
            self.dismiss(float(price_str) if price_str else None)
        except ValueError:
            self.query_one("#dialog-input").value = ""

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Set Price modal ──────────────────────────────────────────────────────────

class SetPriceModal(ModalScreen):
    """Set price for one or more catalog items."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="SetPriceModal", border="#d4af37")

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, item_display: str, current_price: float | None, **kwargs):
        super().__init__(**kwargs)
        self._item_display = item_display
        self._current_price = current_price

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-box"):
            yield Static(self._item_display[:56], id="dialog-title")
            if self._current_price is not None:
                yield Static(
                    f"Current price: €{self._current_price:.2f}", id="dialog-info"
                )
            else:
                yield Static("", id="dialog-info")
            yield Static("  New price (€):", id="dialog-label")
            yield Input(placeholder="0.00", id="dialog-input")
            yield Static("  Enter to confirm   ·   Esc to cancel", id="dialog-hint")

    def on_mount(self) -> None:
        self.query_one("#dialog-input").focus()

    @on(Input.Submitted, "#dialog-input")
    def confirm(self, event: Input.Submitted) -> None:
        try:
            self.dismiss(float(event.value.strip()))
        except ValueError:
            self.query_one("#dialog-input").value = ""

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Set Stock modal ──────────────────────────────────────────────────────────

class SetStockModal(ModalScreen):
    """Set exact stock count for one or more catalog items."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="SetStockModal", border="#4aaa7a")

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, item_display: str, current_stock: int, **kwargs):
        super().__init__(**kwargs)
        self._item_display = item_display
        self._current_stock = current_stock

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-box"):
            yield Static(self._item_display[:56], id="dialog-title")
            yield Static(f"Current stock: {self._current_stock}", id="dialog-info")
            yield Static("  Set stock to:", id="dialog-label")
            yield Input(placeholder="0", id="dialog-input")
            yield Static("  Enter to confirm   ·   Esc to cancel", id="dialog-hint")

    def on_mount(self) -> None:
        self.query_one("#dialog-input").focus()

    @on(Input.Submitted, "#dialog-input")
    def confirm(self, event: Input.Submitted) -> None:
        try:
            self.dismiss(int(event.value.strip()))
        except ValueError:
            self.query_one("#dialog-input").value = ""

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Receive Stock modal ──────────────────────────────────────────────────────

class ReceiveStockModal(ModalScreen):
    """Add copies to stock for one or more catalog items."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="ReceiveStockModal", border="#4aaa7a") + """
    #qty-row { height: 3; align: center middle; margin-bottom: 1; }
    .qty-btn {
        width: 5; height: 3; min-width: 5;
        background: #1a4a2a; border: solid #4aaa7a; color: #4aaa7a;
        content-align: center middle;
    }
    .qty-btn:hover { background: #2a6a3a; }
    #qty-display {
        color: #d4af37; width: 6; height: 3;
        text-align: center; content-align: center middle; text-style: bold;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("plus,kp_add,equals_sign", "qty_up", "More"),
        Binding("minus,kp_subtract", "qty_down", "Less"),
    ]

    def __init__(self, item_display: str, current_stock: int, **kwargs):
        super().__init__(**kwargs)
        self._item_display = item_display
        self._current_stock = current_stock
        self._qty = 1

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-box"):
            yield Static(self._item_display[:56], id="dialog-title")
            yield Static(f"Current stock: {self._current_stock}", id="dialog-info")
            yield Static("  Copies to add:", id="dialog-label")
            with Horizontal(id="qty-row"):
                yield Button("−", id="btn-minus", classes="qty-btn")
                yield Static("1", id="qty-display")
                yield Button("+", id="btn-plus", classes="qty-btn")
            yield Static(
                "  Enter or click + to confirm   ·   Esc to cancel", id="dialog-hint"
            )

    def on_mount(self) -> None:
        self.query_one("#btn-plus").focus()

    @on(Button.Pressed, "#btn-plus")
    def _click_plus(self) -> None:
        self.action_qty_up()

    @on(Button.Pressed, "#btn-minus")
    def _click_minus(self) -> None:
        self.action_qty_down()

    def action_qty_up(self) -> None:
        self._qty = min(self._qty + 1, 99)
        self.query_one("#qty-display").update(str(self._qty))

    def action_qty_down(self) -> None:
        self._qty = max(self._qty - 1, 1)
        self.query_one("#qty-display").update(str(self._qty))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.dismiss(self._qty)


# ── Payment selector for manual sale logging ─────────────────────────────────

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

    #sale-item-title {
        color: #e8dcc8;
        text-align: center;
        text-style: bold;
        margin-bottom: 0;
    }

    #sale-item-price {
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
            yield Static(self._title[:44], id="sale-item-title")
            yield Static(price_str, id="sale-item-price")
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


# ── Add Item modal ───────────────────────────────────────────────────────────

class AddItemModal(ModalScreen):
    """Form for adding an item with unknown or missing barcode.

    Pass barcode="" (default) to show an editable barcode field with auto-assign
    fallback. Pass a scanned barcode to pre-fill it as a read-only label.
    Dismisses with a dict of field values, or None on cancel.
    """

    DEFAULT_CSS = """
    AddItemModal { align: center middle; }

    #add-dialog {
        width: 74;
        height: auto;
        background: #0f0f2a;
        border: double #d4af37;
        padding: 2 3;
    }

    #add-dialog-title {
        color: #d4af37;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #add-barcode-display {
        color: #6a6a8a;
        text-style: italic;
        margin-bottom: 1;
        padding: 0 1;
    }

    .add-label { color: #8a8aaa; height: 1; padding: 0 1; }

    .add-input {
        background: #0f0f1a;
        border: solid #2a2a5a;
        color: #c8b89a;
        margin: 0 0 1 0;
    }

    #add-price-input {
        background: #0f0f1a;
        border: solid #d4af37;
        color: #d4af37;
        margin: 0 0 1 0;
        width: 22;
    }

    #add-stock-input {
        background: #0f0f1a;
        border: solid #4aaa7a;
        color: #4aaa7a;
        margin: 0 0 1 0;
        width: 10;
    }

    #add-error { color: #aa4a4a; height: 1; padding: 0 1; }

    #add-save-btn {
        width: 100%;
        height: 3;
        margin-top: 1;
        background: #0a1f0a;
        border: solid #4aaa7a;
        color: #4aaa7a;
        content-align: center middle;
        text-style: bold;
    }
    #add-save-btn:hover { background: #0f2f0f; }
    #add-save-btn:focus { border: solid #d4af37; color: #d4af37; }

    #add-hint {
        color: #3a3a6a;
        text-align: center;
        text-style: italic;
        margin-top: 0;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, barcode: str = "", ui: dict | None = None, **kwargs):
        super().__init__(**kwargs)
        self._barcode = barcode
        self._ui = ui or {}

    def compose(self) -> ComposeResult:
        barcode_label = self._ui.get("barcode_label", "Barcode")
        creator_label = self._ui.get("creator_label", "Author / Creator")
        vendor_label = self._ui.get("vendor_label", "Publisher / Source")
        item_singular = self._ui.get("item_singular", "item").upper()

        heading = f"ADD {item_singular} — SCANNED {barcode_label.upper()}" if self._barcode else f"ADD {item_singular} MANUALLY"
        with Vertical(id="add-dialog"):
            yield Static(heading, id="add-dialog-title")
            if self._barcode:
                yield Static(f"  {barcode_label}: {self._barcode}", id="add-barcode-display")
            else:
                yield Static(
                    f"  {barcode_label}  (leave blank to auto-assign in-house barcode):",
                    classes="add-label",
                )
                yield Input(
                    placeholder="Optional — leave blank for in-house barcode",
                    id="add-barcode-input",
                    classes="add-input",
                )
            yield Static("  Title *", classes="add-label")
            yield Input(placeholder="Title", id="add-title", classes="add-input")
            yield Static(f"  {creator_label}", classes="add-label")
            yield Input(placeholder=creator_label, id="add-author", classes="add-input")
            yield Static(f"  {vendor_label}", classes="add-label")
            yield Input(placeholder=vendor_label, id="add-publisher", classes="add-input")
            yield Static("  Year", classes="add-label")
            yield Input(placeholder="e.g. 1993", id="add-year", classes="add-input")
            yield Static("  Price (€)", classes="add-label")
            yield Input(placeholder="e.g. 8.50", id="add-price-input")
            yield Static("  Copies in stock", classes="add-label")
            yield Input(placeholder="e.g. 1", id="add-stock-input")
            yield Static("", id="add-error")
            yield Button(f"  ✦  Save {item_singular.title()}", id="add-save-btn")
            yield Static("  Tab between fields   ·   Esc to cancel", id="add-hint")

    def on_mount(self) -> None:
        self.query_one("#add-title").focus()

    def _collect(self) -> dict | None:
        title = self.query_one("#add-title").value.strip()
        if not title:
            self.query_one("#add-error").update("  ⚠  Title is required")
            self.query_one("#add-title").focus()
            return None

        barcode = self._barcode
        if not barcode:
            try:
                barcode = self.query_one("#add-barcode-input").value.strip()
            except Exception:
                barcode = ""

        try:
            price = float(self.query_one("#add-price-input").value.strip())
        except ValueError:
            price = None

        try:
            stock = int(self.query_one("#add-stock-input").value.strip())
        except ValueError:
            stock = 1

        return {
            "barcode": barcode,
            "title": title,
            "author": self.query_one("#add-author").value.strip() or None,
            "publisher": self.query_one("#add-publisher").value.strip() or None,
            "year": self.query_one("#add-year").value.strip() or None,
            "price": price,
            "stock": stock,
        }

    @on(Button.Pressed, "#add-save-btn")
    def _save(self) -> None:
        result = self._collect()
        if result is not None:
            self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Main app ─────────────────────────────────────────────────────────────────

class IntakeApp(App):
    """
    Intake / Catalog mode — browse the full catalog, receive stock,
    and update prices and stock counts. No PIN required.
    """

    CSS_PATH = "theme.tcss"
    CSS = CSS

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("p", "set_price", "Price", show=True),
        Binding("s", "set_stock", "Stock", show=True),
        Binding("plus,kp_add,equals_sign", "receive", "Receive +", show=True),
        Binding("m", "toggle_mark", "Mark", show=True),
        Binding("a", "add_item", "Add Item", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.logger = get_logger("intake", self.config)
        self.conn = get_db(self.config)
        self._ui = self.config.get("ui", {})
        self._inhouse_prefix = get_inhouse_prefix(self.config)
        self._highlighted_barcode: str | None = None
        self._marked_barcodes: set[str] = set()
        self._mark_col_key = None
        self._current_new_item: dict | None = None
        self._receive_mode: bool = False

    def compose(self) -> ComposeResult:
        creator_label = self._ui.get("creator_label", "Author")
        item_singular = self._ui.get("item_singular", "item").title()

        with Horizontal(id="topbar"):
            yield Static(
                "✦  INTAKE MODE  ·  CATALOG & STOCK  ·  "
                + datetime.now().strftime("%d %B %Y"),
                id="header",
            )
            yield BackButton("⌂ Home  [Esc]", id="back-btn")

        yield Input(
            placeholder=f"Filter by title / {creator_label.lower()} — or scan a barcode…",
            id="catalog-search-input",
        )
        yield Static("", id="catalog-count")
        yield DataTable(id="catalog-table", cursor_type="row")
        yield Static("", id="selection-info")
        yield Input(id="scan-input")

        with Horizontal(id="action-bar"):
            yield Button("[P] Price",               id="btn-set-price", classes="action-btn", disabled=True)
            yield Button("[S] Stock",               id="btn-set-stock", classes="action-btn", disabled=True)
            yield Button("[+] Receive",             id="btn-receive",   classes="action-btn")
            yield Button("[L] Label",               id="btn-gen-label", classes="action-btn", disabled=True)
            yield Button("[G] Log Sale",            id="btn-log-sale",  classes="action-btn", disabled=True)
            yield Button(f"[A] Add {item_singular}", id="btn-add-item",  classes="action-btn")

        yield HintBar(id="hint-bar")
        yield Static(get_quote_display(), id="footer")

    def on_mount(self) -> None:
        creator_label = self._ui.get("creator_label", "Author")
        table = self.query_one("#catalog-table", DataTable)
        self._mark_col_key = table.add_column(" ", width=2)
        table.add_column("Title",          width=38)
        table.add_column(creator_label,    width=24)
        table.add_column("Price",          width=8)
        table.add_column("Stock",          width=6)
        self._load_catalog_table()
        self.query_one(HintBar).update_from(self.BINDINGS)
        self.query_one("#catalog-search-input").focus()

    # ── Catalog table ─────────────────────────────────────────

    def _load_catalog_table(self, term: str = "") -> None:
        table = self.query_one("#catalog-table", DataTable)
        table.clear()
        self._highlighted_barcode = None

        if term:
            rows = self.conn.execute("""
                SELECT barcode, title, author, price, stock
                FROM catalog
                WHERE LOWER(title) LIKE ? OR LOWER(author) LIKE ?
                ORDER BY title
            """, (f"%{term.lower()}%", f"%{term.lower()}%")).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT barcode, title, author, price, stock
                FROM catalog
                ORDER BY title
            """).fetchall()

        for row in rows:
            barcode = row["barcode"] or ""
            price_str = f"€{row['price']:.2f}" if row["price"] else "—"
            mark = "✓" if barcode in self._marked_barcodes else " "
            table.add_row(
                mark,
                (row["title"] or "")[:38],
                (row["author"] or "")[:24],
                price_str,
                str(row["stock"] or 0),
                key=barcode,
            )

        count = len(rows)
        item_plural = self._ui.get("item_plural", "items")
        label = f"  {count} {item_plural if count != 1 else self._ui.get('item_singular', 'item')}"
        if term:
            label += f" matching '{term}'"
        label += "  ·  ↑↓ browse  ·  [M] mark  ·  [P] price  ·  [S] stock  ·  [+] receive"
        self.query_one("#catalog-count").update(label)
        self._update_action_bar()

    def _jump_to_barcode(self, barcode: str) -> None:
        table = self.query_one("#catalog-table", DataTable)
        try:
            row_index = table.get_row_index(barcode)
            table.move_cursor(row=row_index)
            self._highlighted_barcode = barcode
            self._update_action_bar()
        except Exception:
            pass

    # ── Selection / action bar ────────────────────────────────

    def _active_barcodes(self) -> set[str]:
        if self._marked_barcodes:
            return set(self._marked_barcodes)
        if self._highlighted_barcode:
            return {self._highlighted_barcode}
        return set()

    def _update_action_bar(self) -> None:
        active = self._active_barcodes()
        has_any = bool(active)
        single = len(active) == 1
        single_barcode = next(iter(active)) if single else None
        is_inhouse = bool(single_barcode and single_barcode.startswith(self._inhouse_prefix))

        self.query_one("#btn-set-price", Button).disabled = not has_any
        self.query_one("#btn-set-stock", Button).disabled = not has_any
        # Receive stays enabled with nothing selected — it's also how you
        # enter scan-to-receive mode (see action_receive).
        self.query_one("#btn-gen-label", Button).disabled = not is_inhouse
        self.query_one("#btn-log-sale",  Button).disabled = not single

        marked_count = len(self._marked_barcodes)
        if marked_count:
            info = f"  {marked_count} marked"
            if self._highlighted_barcode:
                row = self.conn.execute(
                    "SELECT title FROM catalog WHERE barcode = ?",
                    (self._highlighted_barcode,),
                ).fetchone()
                if row:
                    info += f"  ·  {row['title'][:40]}"
        elif self._highlighted_barcode:
            row = self.conn.execute(
                "SELECT title FROM catalog WHERE barcode = ?",
                (self._highlighted_barcode,),
            ).fetchone()
            info = f"  {row['title'][:56]}" if row else ""
        else:
            info = ""
        self.query_one("#selection-info").update(info)

    @on(DataTable.RowHighlighted, "#catalog-table")
    def _row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._highlighted_barcode = str(event.row_key.value) if event.row_key else None
        self._update_action_bar()

    def action_toggle_mark(self) -> None:
        barcode = self._highlighted_barcode
        if not barcode:
            return
        table = self.query_one("#catalog-table", DataTable)
        if barcode in self._marked_barcodes:
            self._marked_barcodes.discard(barcode)
            mark = " "
        else:
            self._marked_barcodes.add(barcode)
            mark = "✓"
        try:
            table.update_cell(barcode, self._mark_col_key, mark)
        except Exception:
            pass
        self._update_action_bar()

    @on(Input.Submitted, "#catalog-search-input")
    async def search_catalog(self, event: Input.Submitted) -> None:
        term = event.value.strip()
        event.input.value = ""
        if is_valid_barcode(term) or term.startswith(self._inhouse_prefix):
            await self._process_scan(term)
        else:
            self._load_catalog_table(term)

    # ── Scan input ────────────────────────────────────────────

    @on(Input.Submitted, "#scan-input")
    async def handle_scan_input(self, event: Input.Submitted) -> None:
        barcode = event.value.strip()
        event.input.value = ""
        if barcode:
            await self._process_scan(barcode)

    async def _process_scan(self, barcode: str) -> None:
        item = get_item(barcode, self.conn)
        if item:
            self.query_one("#catalog-search-input").value = ""
            self._load_catalog_table()
            self._jump_to_barcode(barcode)
            if self._receive_mode:
                self.push_screen(
                    ReceiveStockModal(item["title"], item["stock"] or 0),
                    callback=lambda q: self._apply_receive({barcode}, q),
                )
            else:
                self.query_one("#catalog-table", DataTable).focus()
            return

        if not self.config.get("api", {}).get("lookup_enabled", True):
            self.push_screen(
                AddItemModal(barcode=barcode, ui=self._ui),
                callback=self._on_add_item,
            )
            return

        self.query_one("#selection-info").update("  Querying Open Library…")

        from app.catalog import lookup_openlibrary
        api_item = lookup_openlibrary(barcode, self.config, self.logger)

        if api_item:
            api_item.setdefault("price", None)
            api_item.setdefault("stock", 0)
            api_item.setdefault("manual", 0)
            self._current_new_item = api_item
            extra = self._item_extra(api_item)
            self.push_screen(
                PriceEntryScreen(
                    title=api_item["title"],
                    author=api_item.get("author", ""),
                    extra=extra,
                ),
                callback=self._on_price_entered,
            )
        else:
            self.push_screen(
                AddItemModal(barcode=barcode, ui=self._ui),
                callback=self._on_add_item,
            )

    def _on_price_entered(self, price: float | None) -> None:
        item = self._current_new_item
        if not item:
            return
        item["price"] = price
        item["stock"] = 1
        add_item(item, self.conn)
        self.logger.info(
            f"Intake: new item '{item['title']}' added — price {price}"
        )
        self._current_new_item = None
        search_term = self.query_one("#catalog-search-input").value.strip()
        self._load_catalog_table(search_term)
        self._jump_to_barcode(item["barcode"])
        self._finish_scan_focus()
        self.query_one("#footer").update(get_quote_display())

    @staticmethod
    def _item_extra(item: dict) -> str:
        parts = [item.get("publisher", ""), item.get("year", "")]
        return "  ".join(p for p in parts if p)

    def _finish_scan_focus(self) -> None:
        """After adding/jumping to an item, return focus to wherever the
        operator needs it next — the scanner if still receiving, else the table."""
        if self._receive_mode:
            self.query_one("#selection-info").update(
                "  ✦  Added  ·  scan next item, Esc to stop"
            )
            self.query_one("#scan-input").focus()
        else:
            self.query_one("#catalog-table", DataTable).focus()

    # ── Add Item action ───────────────────────────────────────

    def action_add_item(self) -> None:
        self.push_screen(AddItemModal(ui=self._ui), callback=self._on_add_item)

    @on(Button.Pressed, "#btn-add-item")
    def _click_add_item(self) -> None:
        self.action_add_item()

    def _on_add_item(self, result: dict | None) -> None:
        if not result:
            return
        barcode = result.get("barcode") or ""
        if not barcode:
            barcode = make_inhouse_barcode(
                next_inhouse_number(self.conn, self._inhouse_prefix),
                self._inhouse_prefix,
            )
            try:
                generate_svg(barcode, result["title"], result.get("price"))
                shop_name = self.config.get("shop", {}).get("name", "Bookshop")
                generate_sheet(self.conn, self._inhouse_prefix, shop_name)
            except Exception as e:
                self.logger.warning(f"Intake: label generation failed for '{result['title']}': {e}")

        item = {
            "barcode": barcode,
            "title": result["title"],
            "author": result.get("author"),
            "publisher": result.get("publisher"),
            "year": result.get("year"),
            "price": result.get("price"),
            "stock": result.get("stock") or 1,
            "manual": 1,
        }
        add_item(item, self.conn)
        self.logger.info(f"Intake: manual item added '{item['title']}' ({barcode})")
        search_term = self.query_one("#catalog-search-input").value.strip()
        self._load_catalog_table(search_term)
        self._jump_to_barcode(barcode)
        self._finish_scan_focus()
        self.query_one("#footer").update(get_quote_display())

    # ── Price action ─────────────────────────────────────────

    def action_set_price(self) -> None:
        active = self._active_barcodes()
        if not active:
            return
        if len(active) == 1:
            barcode = next(iter(active))
            row = self.conn.execute(
                "SELECT title, price FROM catalog WHERE barcode = ?", (barcode,)
            ).fetchone()
            if not row:
                return
            self.push_screen(
                SetPriceModal(row["title"], row["price"]),
                callback=lambda p: self._apply_price(active, p),
            )
        else:
            item_plural = self._ui.get("item_plural", "items")
            self.push_screen(
                SetPriceModal(f"{len(active)} {item_plural}", None),
                callback=lambda p: self._apply_price(active, p),
            )

    def _apply_price(self, barcodes: set[str], price: float | None) -> None:
        if price is None:
            return
        now = datetime.now().isoformat()
        for barcode in barcodes:
            self.conn.execute(
                "UPDATE catalog SET price = ?, updated_at = ? WHERE barcode = ?",
                (price, now, barcode),
            )
            self.logger.info(f"Intake: price set €{price:.2f} for barcode={barcode}")
        self.conn.commit()
        term = self.query_one("#catalog-search-input").value.strip()
        self._load_catalog_table(term)
        n = len(barcodes)
        self.query_one("#selection-info").update(
            f"  ✦  Price set to €{price:.2f} for {n} item{'s' if n != 1 else ''}"
        )

    @on(Button.Pressed, "#btn-set-price")
    def _click_price(self) -> None:
        self.action_set_price()

    # ── Stock action ─────────────────────────────────────────

    def action_set_stock(self) -> None:
        active = self._active_barcodes()
        if not active:
            return
        if len(active) == 1:
            barcode = next(iter(active))
            row = self.conn.execute(
                "SELECT title, stock FROM catalog WHERE barcode = ?", (barcode,)
            ).fetchone()
            if not row:
                return
            self.push_screen(
                SetStockModal(row["title"], row["stock"] or 0),
                callback=lambda s: self._apply_stock(active, s),
            )
        else:
            item_plural = self._ui.get("item_plural", "items")
            self.push_screen(
                SetStockModal(f"{len(active)} {item_plural}", 0),
                callback=lambda s: self._apply_stock(active, s),
            )

    def _apply_stock(self, barcodes: set[str], stock: int | None) -> None:
        if stock is None:
            return
        now = datetime.now().isoformat()
        for barcode in barcodes:
            self.conn.execute(
                "UPDATE catalog SET stock = ?, updated_at = ? WHERE barcode = ?",
                (stock, now, barcode),
            )
            self.logger.info(f"Intake: stock set to {stock} for barcode={barcode}")
        self.conn.commit()
        term = self.query_one("#catalog-search-input").value.strip()
        self._load_catalog_table(term)
        n = len(barcodes)
        self.query_one("#selection-info").update(
            f"  ✦  Stock set to {stock} for {n} item{'s' if n != 1 else ''}"
        )

    @on(Button.Pressed, "#btn-set-stock")
    def _click_stock(self) -> None:
        self.action_set_stock()

    # ── Receive action ────────────────────────────────────────

    def action_receive(self) -> None:
        if self._receive_mode:
            self._exit_receive_mode()
            return

        active = self._active_barcodes()
        if len(active) > 1:
            # Bulk-apply one quantity to marked items — one-shot, no mode.
            item_plural = self._ui.get("item_plural", "items")
            self.push_screen(
                ReceiveStockModal(f"{len(active)} {item_plural}", 0),
                callback=lambda q: self._apply_receive(active, q),
            )
            return

        self._enter_receive_mode()
        if len(active) == 1:
            barcode = next(iter(active))
            row = self.conn.execute(
                "SELECT title, stock FROM catalog WHERE barcode = ?", (barcode,)
            ).fetchone()
            if row:
                self.push_screen(
                    ReceiveStockModal(row["title"], row["stock"] or 0),
                    callback=lambda q: self._apply_receive({barcode}, q),
                )

    def _enter_receive_mode(self) -> None:
        self._receive_mode = True
        self.query_one("#btn-receive", Button).add_class("receiving")
        self.query_one("#selection-info").update(
            "  ✦  RECEIVING — scan an item to add stock, or scan a new barcode to add it  ·  Esc to stop"
        )
        self.query_one("#scan-input").focus()

    def _exit_receive_mode(self) -> None:
        self._receive_mode = False
        self.query_one("#btn-receive", Button).remove_class("receiving")
        self.query_one("#selection-info").update("")
        self._update_action_bar()

    def _apply_receive(self, barcodes: set[str], qty: int | None) -> None:
        if qty:
            now = datetime.now().isoformat()
            for barcode in barcodes:
                self.conn.execute(
                    "UPDATE catalog SET stock = stock + ?, updated_at = ? WHERE barcode = ?",
                    (qty, now, barcode),
                )
                self.logger.info(f"Intake: received +{qty} for barcode={barcode}")
            self.conn.commit()
            term = self.query_one("#catalog-search-input").value.strip()
            self._load_catalog_table(term)
            n = len(barcodes)
            if self._receive_mode:
                self.query_one("#selection-info").update(
                    f"  ✦  +{qty} copies added  ·  scan next item, Esc to stop"
                )
            else:
                self.query_one("#selection-info").update(
                    f"  ✦  +{qty} copies added to {n} item{'s' if n != 1 else ''}"
                )

        if self._receive_mode:
            self.query_one("#scan-input").focus()

    @on(Button.Pressed, "#btn-receive")
    def _click_receive(self) -> None:
        self.action_receive()

    # ── Label action ──────────────────────────────────────────

    @on(Button.Pressed, "#btn-gen-label")
    def _generate_label(self) -> None:
        active = self._active_barcodes()
        if len(active) != 1:
            return
        barcode = next(iter(active))
        if not barcode.startswith(self._inhouse_prefix):
            return
        row = self.conn.execute(
            "SELECT title, price FROM catalog WHERE barcode = ?", (barcode,)
        ).fetchone()
        if not row:
            return
        try:
            svg_path = generate_svg(barcode, row["title"], row["price"])
            price_str = f"€{row['price']:.2f}" if row["price"] else "no price"
            self.query_one("#selection-info").update(
                f"  ✦  Label saved: {svg_path}  ·  {price_str}"
            )
            self.logger.info(f"Intake: label generated for '{row['title']}' ({barcode})")
        except Exception as e:
            self.query_one("#selection-info").update(f"  ⚠  Label error: {e}")

    # ── Log Sale action ───────────────────────────────────────

    @on(Button.Pressed, "#btn-log-sale")
    def _log_catalog_sale(self) -> None:
        active = self._active_barcodes()
        if len(active) != 1:
            return
        barcode = next(iter(active))
        row = self.conn.execute(
            "SELECT title, price FROM catalog WHERE barcode = ?", (barcode,)
        ).fetchone()
        if not row:
            return
        self.push_screen(
            SalePaymentScreen(row["title"], row["price"]),
            callback=self._on_catalog_sale_payment,
        )

    def _on_catalog_sale_payment(self, method: str | None) -> None:
        if not method:
            return
        active = self._active_barcodes()
        if len(active) != 1:
            return
        barcode = next(iter(active))
        row = self.conn.execute(
            "SELECT title, price FROM catalog WHERE barcode = ?", (barcode,)
        ).fetchone()
        if not row:
            return
        self.conn.execute(
            "INSERT INTO sales (barcode, title, quantity, price, sold_at, payment_method)"
            " VALUES (?, ?, 1, ?, ?, ?)",
            (barcode, row["title"], row["price"], timestamp_now(), method),
        )
        self.conn.commit()
        price_str = f"€{row['price']:.2f}" if row["price"] else "no price"
        self.logger.info(
            f"Intake: manual sale logged '{row['title']}' {price_str} {method}"
        )
        self.query_one("#selection-info").update(
            f"  ✦  Sale logged: '{row['title']}'  ·  {price_str}  ·  {method.upper()}"
        )

    # ── Back / exit ───────────────────────────────────────────

    @on(Button.Pressed, "#back-btn")
    def _click_back(self) -> None:
        self.action_go_back()

    def action_go_back(self) -> None:
        if self._receive_mode:
            self._exit_receive_mode()
            return
        self.exit()
