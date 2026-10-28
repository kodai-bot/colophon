# SPDX-License-Identifier: AGPL-3.0-or-later
"""
intake.py - Intake / Catalog mode.

Browse the full catalog, receive stock, and update prices and stock counts.
Scan a barcode to jump to an item or add new ones via optional API lookup.
No sales are logged here (use Log Sale button for manual entries only).
"""

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Static, Input, Button, DataTable, Select, OptionList
from textual.widgets.option_list import Option
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import on, work

from datetime import datetime
from app.utils import load_config, get_logger, timestamp_now
from app.catalog import (
    get_db, add_item, get_item, normalize_barcode, get_inhouse_prefix,
    make_inhouse_barcode, next_inhouse_number, decrement_stock,
    BOOKS_CATEGORY_ID, list_categories, create_category, set_category,
    get_category_name, list_catalog, UNSORTED,
)
from app.barcode import generate_svg, generate_sheet
from app.ui.quotes import get_quote_display
from app.ui.widgets import BackButton, HintBar, literal


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

#category-bar {
    height: 1;
    margin: 0 1;
}

.cat-tab {
    height: 1;
    min-width: 6;
    border: none;
    padding: 0 1;
    margin-right: 1;
    background: #1a1a3a;
    color: #8a8aaa;
}

.cat-tab:hover { background: #2a2a4a; color: #c8b89a; }
.cat-tab.-active { background: #1a4a2a; color: #4aaa7a; text-style: bold; }

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
            yield Button(literal("[C]  Cash"), id="sale-btn-cash", classes="sale-btn")
            yield Button(literal("[K]  Card"), id="sale-btn-card", classes="sale-btn")
            yield Static("Esc to cancel", id="sale-hint")

    def action_cash(self) -> None: self.dismiss("cash")
    def action_card(self) -> None: self.dismiss("card")
    def action_cancel(self) -> None: self.dismiss(None)

    @on(Button.Pressed, "#sale-btn-cash")
    def _cash(self) -> None: self.dismiss("cash")

    @on(Button.Pressed, "#sale-btn-card")
    def _card(self) -> None: self.dismiss("card")


# ── Categories ───────────────────────────────────────────────────────────────

NEW_CATEGORY = "__new__"   # picker option that opens NewCategoryModal


def singular(category_name: str) -> str:
    """'Cards' -> 'Card', 'Jewellery' -> 'Jewellery'. Good enough for labels."""
    if len(category_name) > 1 and category_name.endswith("s") and not category_name.endswith("ss"):
        return category_name[:-1]
    return category_name


class NewCategoryModal(ModalScreen):
    """Name a new category. create_fn(name) -> {"id", "name"}, raising
    ValueError on a bad name; the error is shown here so staff can correct it."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="NewCategoryModal", border="#4aaa7a")

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, create_fn, **kwargs):
        super().__init__(**kwargs)
        self._create_fn = create_fn

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-box"):
            yield Static("NEW CATEGORY", id="dialog-title")
            yield Static("e.g. Calendars, Jewellery, Tickets", id="dialog-info")
            yield Static("  Category name (plural):", id="dialog-label")
            yield Input(placeholder="Calendars", id="dialog-input")
            yield Static("  Enter to create   ·   Esc to cancel", id="dialog-hint")

    def on_mount(self) -> None:
        self.query_one("#dialog-input").focus()

    @on(Input.Submitted, "#dialog-input")
    def confirm(self, event: Input.Submitted) -> None:
        try:
            self.dismiss(self._create_fn(event.value))
        except ValueError as e:
            self.query_one("#dialog-info").update(f"⚠  {e}")

    def action_cancel(self) -> None:
        self.dismiss(None)


class CategoryPickerModal(ModalScreen):
    """Choose a category for one or more items. Dismisses with a category id,
    UNSORTED, or None on cancel."""

    DEFAULT_CSS = _DIALOG_CSS.format(cls="CategoryPickerModal", border="#4aaa7a") + """
    #category-options {
        height: auto;
        max-height: 14;
        background: #09091f;
        border: solid #4aaa7a;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, item_display: str, current: str, categories: list[dict],
                 create_fn, **kwargs):
        super().__init__(**kwargs)
        self._item_display = item_display
        self._current = current
        self._categories = categories
        self._create_fn = create_fn

    def compose(self) -> ComposeResult:
        options = [Option(c["name"], id=str(c["id"])) for c in self._categories]
        options.append(Option("Unsorted", id=UNSORTED))
        options.append(Option("＋ New category…", id=NEW_CATEGORY))
        with Vertical(id="dialog-box"):
            yield Static(self._item_display[:56], id="dialog-title")
            yield Static(f"Currently: {self._current}", id="dialog-info")
            yield Static("  Move to category:", id="dialog-label")
            yield OptionList(*options, id="category-options")
            yield Static("  ↑↓ then Enter   ·   Esc to cancel", id="dialog-hint")

    def on_mount(self) -> None:
        self.query_one("#category-options").focus()

    @on(OptionList.OptionSelected, "#category-options")
    def _chosen(self, event: OptionList.OptionSelected) -> None:
        key = event.option.id
        if key == NEW_CATEGORY:
            self.app.push_screen(
                NewCategoryModal(self._create_fn), callback=self._on_new_category
            )
        elif key == UNSORTED:
            self.dismiss(UNSORTED)
        else:
            self.dismiss(int(key))

    def _on_new_category(self, category: dict | None) -> None:
        if category:
            self.dismiss(category["id"])

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Add Item modal ───────────────────────────────────────────────────────────

class AddItemModal(ModalScreen):
    """Form for adding an item with unknown or missing barcode.

    Pass barcode="" (default) to show an editable barcode field with auto-assign
    fallback. Pass a scanned barcode to pre-fill it as a read-only label.
    A category must be chosen; the heading and field labels follow it (books
    get Author / Publisher, everything else Artist / Supplier).
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

    #add-category {
        margin: 0 0 1 0;
        width: 40;
    }

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

    def __init__(self, barcode: str = "", ui: dict | None = None,
                 categories: list[dict] | None = None,
                 category_id: int | None = None, create_fn=None, **kwargs):
        super().__init__(**kwargs)
        self._barcode = barcode
        self._ui = ui or {}
        self._categories = list(categories or [])
        self._category_id = category_id
        self._create_fn = create_fn

    def _category_options(self) -> list[tuple[str, object]]:
        options = [(c["name"], c["id"]) for c in self._categories]
        if self._create_fn:
            options.append(("＋ New category…", NEW_CATEGORY))
        return options

    def _category_name(self) -> str | None:
        for c in self._categories:
            if c["id"] == self._category_id:
                return c["name"]
        return None

    def _labels(self) -> dict:
        """Heading and field labels for the chosen category."""
        name = self._category_name()
        is_book = self._category_id == BOOKS_CATEGORY_ID
        barcode_label = self._ui.get("barcode_label", "Barcode") if is_book else "Barcode"
        thing = singular(name).upper() if name else "ITEM"
        if self._barcode:
            heading = f"ADD {thing} — SCANNED {barcode_label.upper()}"
        else:
            heading = f"ADD {thing} MANUALLY"
        return {
            "heading": heading,
            "barcode": barcode_label,
            "creator": self._ui.get("creator_label", "Author") if is_book else "Artist / Maker",
            "vendor": self._ui.get("vendor_label", "Publisher") if is_book else "Supplier",
            "save": f"  ✦  Save {singular(name) if name else 'Item'}",
        }

    def compose(self) -> ComposeResult:
        labels = self._labels()
        with Vertical(id="add-dialog"):
            yield Static(labels["heading"], id="add-dialog-title")
            yield Static("  Category *", classes="add-label")
            yield Select(
                self._category_options(),
                prompt="Choose category…",
                value=self._category_id if self._category_id is not None else Select.NULL,
                id="add-category",
            )
            if self._barcode:
                yield Static(f"  {labels['barcode']}: {self._barcode}", id="add-barcode-display")
            else:
                yield Static(
                    f"  {labels['barcode']}  (leave blank to auto-assign in-house barcode):",
                    classes="add-label", id="add-barcode-label",
                )
                yield Input(
                    placeholder="Optional — leave blank for in-house barcode",
                    id="add-barcode-input",
                    classes="add-input",
                )
            yield Static("  Title *", classes="add-label")
            yield Input(placeholder="Title", id="add-title", classes="add-input")
            yield Static(f"  {labels['creator']}", classes="add-label", id="add-creator-label")
            yield Input(placeholder=labels["creator"], id="add-author", classes="add-input")
            yield Static(f"  {labels['vendor']}", classes="add-label", id="add-vendor-label")
            yield Input(placeholder=labels["vendor"], id="add-publisher", classes="add-input")
            yield Static("  Year", classes="add-label")
            yield Input(placeholder="e.g. 1993", id="add-year", classes="add-input")
            yield Static("  Price (€)", classes="add-label")
            yield Input(placeholder="e.g. 8.50", id="add-price-input")
            yield Static("  Copies in stock", classes="add-label")
            yield Input(placeholder="e.g. 1", id="add-stock-input")
            yield Static("", id="add-error")
            yield Button(labels["save"], id="add-save-btn")
            yield Static("  Tab between fields   ·   Esc to cancel", id="add-hint")

    def on_mount(self) -> None:
        if self._category_id is None:
            self.query_one("#add-category").focus()
        else:
            self.query_one("#add-title").focus()

    def _refresh_labels(self) -> None:
        labels = self._labels()
        self.query_one("#add-dialog-title").update(labels["heading"])
        self.query_one("#add-creator-label").update(f"  {labels['creator']}")
        self.query_one("#add-author").placeholder = labels["creator"]
        self.query_one("#add-vendor-label").update(f"  {labels['vendor']}")
        self.query_one("#add-publisher").placeholder = labels["vendor"]
        self.query_one("#add-save-btn").label = labels["save"]
        if self._barcode:
            self.query_one("#add-barcode-display").update(
                f"  {labels['barcode']}: {self._barcode}"
            )
        else:
            self.query_one("#add-barcode-label").update(
                f"  {labels['barcode']}  (leave blank to auto-assign in-house barcode):"
            )

    @on(Select.Changed, "#add-category")
    def _category_changed(self, event: Select.Changed) -> None:
        if event.value == NEW_CATEGORY:
            self.app.push_screen(
                NewCategoryModal(self._create_fn), callback=self._on_new_category
            )
            return
        self._category_id = None if event.value is Select.NULL else event.value
        self.query_one("#add-error").update("")
        self._refresh_labels()

    def _on_new_category(self, category: dict | None) -> None:
        select = self.query_one("#add-category", Select)
        if category:
            self._categories.append(category)
            self._category_id = category["id"]
            select.set_options(self._category_options())
        # Put the picker back on the real choice (set_options clears it, and a
        # cancelled "New category…" must not stay selected).
        select.value = self._category_id if self._category_id is not None else Select.NULL
        self._refresh_labels()
        self.query_one("#add-title").focus()

    def _collect(self) -> dict | None:
        if self._category_id is None:
            self.query_one("#add-error").update("  ⚠  Choose a category")
            self.query_one("#add-category").focus()
            return None

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
            "category_id": self._category_id,
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
        Binding("c", "set_category", "Category", show=True),
        Binding("left_square_bracket", "prev_category_tab", "Previous tab", show=False),
        Binding("right_square_bracket", "next_category_tab", "Next tab", show=False),
        Binding("ctrl+q", "quit", "Quit", show=True),
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
        # Category tab: "all", UNSORTED, or a category id
        self._category_filter: str | int = "all"

    def compose(self) -> ComposeResult:
        creator_label = self._ui.get("creator_label", "Author")

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
        yield Horizontal(id="category-bar")
        yield Static("", id="catalog-count")
        yield DataTable(id="catalog-table", cursor_type="row")
        yield Static("", id="selection-info")
        yield Input(id="scan-input")

        with Horizontal(id="action-bar"):
            yield Button(literal("[P] Price"),               id="btn-set-price", classes="action-btn", disabled=True)
            yield Button(literal("[S] Stock"),               id="btn-set-stock", classes="action-btn", disabled=True)
            yield Button("[+] Receive",             id="btn-receive",   classes="action-btn")
            yield Button(literal("[L] Label"),               id="btn-gen-label", classes="action-btn", disabled=True)
            yield Button(literal("[G] Log Sale"),            id="btn-log-sale",  classes="action-btn", disabled=True)
            yield Button(literal("[C] Category"),            id="btn-set-category", classes="action-btn", disabled=True)
            yield Button(literal("[A] Add Item"),            id="btn-add-item",  classes="action-btn")

        yield HintBar(id="hint-bar")
        yield Static(get_quote_display(), id="footer")

    def on_mount(self) -> None:
        self._build_category_tabs()
        self._load_catalog_table()
        self.query_one(HintBar).update_from(self.BINDINGS)
        self.query_one("#catalog-search-input").focus()

    # ── Category tabs ─────────────────────────────────────────

    def _categories(self) -> list[dict]:
        return list_categories(self.conn)

    def _tab_keys(self) -> list[str | int]:
        return ["all"] + [c["id"] for c in self._categories()] + [UNSORTED]

    def _build_category_tabs(self) -> None:
        """(Re)build the tab strip: All · <categories> · Unsorted."""
        bar = self.query_one("#category-bar", Horizontal)
        bar.remove_children()
        tabs = [("all", "All")]
        tabs += [(str(c["id"]), c["name"]) for c in self._categories()]
        tabs.append((UNSORTED, "Unsorted"))
        bar.mount(*[
            Button(label, name=key, compact=True,
                   classes="cat-tab -active" if key == str(self._category_filter) else "cat-tab")
            for key, label in tabs
        ])

    def _select_category_tab(self, key: str | int) -> None:
        if key == self._category_filter:
            return
        self._category_filter = key
        # Marks are cleared so a bulk Price/Stock/Category can't silently
        # include items hidden on another tab.
        self._marked_barcodes.clear()
        for btn in self.query(".cat-tab"):
            btn.set_class(btn.name == str(key), "-active")
        self._load_catalog_table(self.query_one("#catalog-search-input").value.strip())

    @on(Button.Pressed, ".cat-tab")
    def _click_category_tab(self, event: Button.Pressed) -> None:
        key = event.button.name
        self._select_category_tab(int(key) if key.isdigit() else key)
        self.query_one("#catalog-table", DataTable).focus()

    def _cycle_category_tab(self, step: int) -> None:
        keys = self._tab_keys()
        i = keys.index(self._category_filter) if self._category_filter in keys else 0
        self._select_category_tab(keys[(i + step) % len(keys)])

    def action_prev_category_tab(self) -> None:
        self._cycle_category_tab(-1)

    def action_next_category_tab(self) -> None:
        self._cycle_category_tab(1)

    def _current_tab_name(self) -> str | None:
        """Name of the selected category tab, or None for All / Unsorted."""
        if isinstance(self._category_filter, int):
            return get_category_name(self._category_filter, self.conn)
        return None

    def _create_category(self, name: str) -> dict:
        """create_fn for the category modals; raises ValueError on a bad name."""
        cat_id = create_category(name, self.conn)
        cat_name = get_category_name(cat_id, self.conn)
        self.logger.info(f"Intake: category created '{cat_name}' (id={cat_id})")
        self._build_category_tabs()
        return {"id": cat_id, "name": cat_name}

    # ── Catalog table ─────────────────────────────────────────

    def _setup_columns(self, show_category: bool) -> None:
        creator_label = self._ui.get("creator_label", "Author")
        table = self.query_one("#catalog-table", DataTable)
        table.clear(columns=True)
        self._mark_col_key = table.add_column(" ", width=2)
        table.add_column("Title",          width=38)
        table.add_column(creator_label,    width=24)
        if show_category:
            table.add_column("Category",   width=10)
        table.add_column("Price",          width=8)
        table.add_column("Stock",          width=6)

    def _load_catalog_table(self, term: str = "") -> None:
        show_category = self._category_filter == "all"
        self._setup_columns(show_category)
        table = self.query_one("#catalog-table", DataTable)
        self._highlighted_barcode = None

        rows = list_catalog(self.conn, term, self._category_filter)

        for row in rows:
            barcode = row["barcode"] or ""
            price_str = f"€{row['price']:.2f}" if row["price"] else "—"
            mark = "✓" if barcode in self._marked_barcodes else " "
            stock_str = str(row["stock"] or 0)
            if row["needs_recount"]:
                stock_str += " ⚠"
            cells = [mark, (row["title"] or "")[:38], (row["author"] or "")[:24]]
            if show_category:
                cells.append(row["category"][:10])
            cells += [price_str, stock_str]
            if (row["stock"] or 0) <= 0:
                # Out of stock: listed at the bottom, dimmed (mark stays plain)
                cells = cells[:1] + [Text(c, style="dim") for c in cells[1:]]
            table.add_row(*cells, key=barcode)

        count = len(rows)
        tab_name = self._current_tab_name()
        if tab_name:
            noun = tab_name.lower() if count != 1 else singular(tab_name).lower()
        elif self._category_filter == UNSORTED:
            noun = "unsorted items" if count != 1 else "unsorted item"
        else:
            noun = "items" if count != 1 else "item"
        label = f"  {count} {noun}"
        out_n = sum(1 for row in rows if (row["stock"] or 0) <= 0)
        if out_n:
            label += f" · {out_n} out of stock (dimmed, at bottom)"
        if term:
            label += f" matching '{term}'"
        label += literal("  ·  [ ] tabs  ·  ↑↓ browse  ·  [M] mark  ·  [P] price  ·  [S] stock  ·  [+] receive")
        recount_n = sum(1 for row in rows if row["needs_recount"])
        if recount_n:
            label += f"  ·  ⚠ {recount_n} need recount"
        self.query_one("#catalog-count").update(label)
        self.query_one("#btn-add-item", Button).label = (
            literal(f"[A] Add {singular(tab_name)}") if tab_name else literal("[A] Add Item")
        )
        self._update_action_bar()

    def _jump_to_barcode(self, barcode: str) -> None:
        table = self.query_one("#catalog-table", DataTable)
        if barcode not in table.rows and self._category_filter != "all":
            # The item lives on another tab — show All so it can be found.
            self._select_category_tab("all")
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
        self.query_one("#btn-set-category", Button).disabled = not has_any
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
        normalized = normalize_barcode(term)
        if normalized or term.startswith(self._inhouse_prefix):
            await self._process_scan(normalized or term)
        else:
            self._load_catalog_table(term)

    # ── Scan input ────────────────────────────────────────────

    @on(Input.Submitted, "#scan-input")
    async def handle_scan_input(self, event: Input.Submitted) -> None:
        barcode = event.value.strip()
        event.input.value = ""
        if barcode:
            await self._process_scan(normalize_barcode(barcode) or barcode)

    @work(thread=True)
    def _lookup_openlibrary_worker(self, barcode: str) -> dict | None:
        """Run the Open Library HTTP call off the UI thread so a slow/absent
        network connection doesn't freeze the interface during a scan."""
        from app.catalog import lookup_openlibrary
        return lookup_openlibrary(barcode, self.config, self.logger)

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
            self._open_add_item(barcode)
            return

        self.query_one("#selection-info").update("  Querying Open Library…")

        api_item = await self._lookup_openlibrary_worker(barcode).wait()

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
            self._open_add_item(barcode)

    def _on_price_entered(self, price: float | None) -> None:
        item = self._current_new_item
        if not item:
            return
        item["price"] = price
        item["stock"] = 1
        item["category_id"] = BOOKS_CATEGORY_ID
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

    def _open_add_item(self, barcode: str = "") -> None:
        """Open the Add form, defaulting the category to the selected tab
        (or Books for a scanned ISBN). Under All / Unsorted staff must pick."""
        if barcode[:3] in ("978", "979"):
            category_id = BOOKS_CATEGORY_ID
        elif isinstance(self._category_filter, int):
            category_id = self._category_filter
        else:
            category_id = None
        self.push_screen(
            AddItemModal(
                barcode=barcode, ui=self._ui,
                categories=self._categories(), category_id=category_id,
                create_fn=self._create_category,
            ),
            callback=self._on_add_item,
        )

    def action_add_item(self) -> None:
        self._open_add_item()

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
            "category_id": result.get("category_id"),
        }
        add_item(item, self.conn)
        self.logger.info(
            f"Intake: manual item added '{item['title']}' ({barcode}) "
            f"category={get_category_name(item['category_id'], self.conn)}"
        )
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
            old_row = self.conn.execute(
                "SELECT price FROM catalog WHERE barcode = ?", (barcode,)
            ).fetchone()
            old_price = old_row["price"] if old_row else None
            self.conn.execute(
                "UPDATE catalog SET price = ?, updated_at = ? WHERE barcode = ?",
                (price, now, barcode),
            )
            self.logger.info(
                f"Intake: price changed for barcode={barcode} old={old_price} new={price:.2f}"
            )
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
            old_row = self.conn.execute(
                "SELECT stock FROM catalog WHERE barcode = ?", (barcode,)
            ).fetchone()
            old_stock = old_row["stock"] if old_row else None
            self.conn.execute(
                "UPDATE catalog SET stock = ?, needs_recount = 0, updated_at = ? WHERE barcode = ?",
                (stock, now, barcode),
            )
            self.logger.info(
                f"Intake: stock changed for barcode={barcode} old={old_stock} new={stock}"
            )
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

    # ── Category action ──────────────────────────────────────

    def action_set_category(self) -> None:
        active = self._active_barcodes()
        if not active:
            return
        if len(active) == 1:
            barcode = next(iter(active))
            row = self.conn.execute(
                "SELECT title, category_id FROM catalog WHERE barcode = ?", (barcode,)
            ).fetchone()
            if not row:
                return
            display = row["title"]
            current = get_category_name(row["category_id"], self.conn)
        else:
            display = f"{len(active)} items"
            ids = {
                r["category_id"] for r in self.conn.execute(
                    f"SELECT category_id FROM catalog WHERE barcode IN "
                    f"({','.join('?' * len(active))})", list(active)
                )
            }
            current = get_category_name(ids.pop(), self.conn) if len(ids) == 1 else "mixed"
        self.push_screen(
            CategoryPickerModal(display, current, self._categories(), self._create_category),
            callback=lambda choice: self._apply_category(active, choice),
        )

    def _apply_category(self, barcodes: set[str], choice) -> None:
        if choice is None:
            return
        category_id = None if choice == UNSORTED else choice
        new_name = get_category_name(category_id, self.conn)
        changed = set_category(barcodes, category_id, self.conn)
        for barcode, old_id in changed:
            self.logger.info(
                f"Intake: category changed for barcode={barcode} "
                f"old={get_category_name(old_id, self.conn)} new={new_name}"
            )
        self._marked_barcodes.clear()
        term = self.query_one("#catalog-search-input").value.strip()
        self._load_catalog_table(term)
        n = len(changed)
        self.query_one("#selection-info").update(
            f"  ✦  {n} item{'s' if n != 1 else ''} moved to {new_name}"
        )
        self.query_one("#catalog-table", DataTable).focus()

    @on(Button.Pressed, "#btn-set-category")
    def _click_category(self) -> None:
        self.action_set_category()

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
                    "UPDATE catalog SET stock = stock + ?, needs_recount = 0, updated_at = ? WHERE barcode = ?",
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
        decrement_stock(barcode, self.conn)
        price_str = f"€{row['price']:.2f}" if row["price"] else "no price"
        self.logger.info(
            f"Intake: manual sale logged '{row['title']}' {price_str} {method}"
        )
        term = self.query_one("#catalog-search-input").value.strip()
        self._load_catalog_table(term)
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

    def action_quit(self) -> None:
        """Ctrl+Q exits the whole program, not just this mode."""
        self.exit(result="quit")
