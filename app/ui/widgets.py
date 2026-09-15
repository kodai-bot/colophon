# SPDX-License-Identifier: AGPL-3.0-or-later
"""
widgets.py - Reusable Textual widgets for the bookshop UI.
"""

import random
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from textual.reactive import reactive
from datetime import datetime
from app.ui.quotes import get_quote_display


IDLE_PHRASES = [
    "SCANNING FOR LIFEFORMS...",
    "SENSORS NOMINAL — STANDING BY...",
    "AWAITING NEXT TRANSMISSION...",
    "CHANNEL OPEN — READY TO RECEIVE...",
    "ALL SYSTEMS NOMINAL...",
    "DATABANKS IDLE — HAILING FREQUENCIES OPEN...",
]


class HeaderBar(Static):
    """Top header — shop name, location, date and live clock."""

    def __init__(self, title: str = "Shop", location: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title.upper()
        self._location = location.upper()

    def on_mount(self) -> None:
        self.set_interval(1, self.refresh)

    def render(self) -> str:
        now = datetime.now()
        today = now.strftime("%A  %d %B %Y")
        clock = now.strftime("%H:%M:%S")
        loc_part = f"  ·  {self._location}" if self._location else ""
        return f"✦  {self._title}{loc_part}  ✦\n{today}  ·  {clock}"


class BackButton(Button):
    """
    Visible back/escape control. Same widget, same label across all modes
    so volunteers build muscle memory. Posts standard Button.Pressed —
    each mode wires its own handler.
    """

    def __init__(self, label: str = "← Back  [Esc]", **kwargs):
        super().__init__(label, **kwargs)


_KEY_DISPLAY = {
    "plus": "+", "kp_add": "+", "equals_sign": "=",
    "minus": "−", "kp_subtract": "−",
    "escape": "Esc",
    "ctrl+p": "Ctrl+P", "ctrl+z": "Ctrl+Z", "ctrl+s": "Ctrl+S",
}


def _humanize_key(raw: str) -> str:
    first = raw.split(",")[0].strip().lower()
    return _KEY_DISPLAY.get(first, first.upper())


class HintBar(Static):
    """
    One-line hint bar showing the visible keybindings of the current mode.
    Auto-generated from a list of textual.binding.Binding objects so the
    hints never go stale.
    """

    def update_from(self, bindings) -> None:
        labels = [
            f"[{_humanize_key(b.key)}] {b.description}"
            for b in bindings
            if getattr(b, "show", False) and b.description
        ]
        self.update("    ".join(labels))


class ScanDisplay(Static):
    """
    Shows the result of the last scan, plus a persistent warning while a
    transaction is open/unpaid, and a rotating flavor phrase when idle.
    """

    title: reactive[str] = reactive("")
    author: reactive[str] = reactive("")
    price: reactive[str] = reactive("")
    status: reactive[str] = reactive(IDLE_PHRASES[0])
    status_class: reactive[str] = reactive("status-ready")
    pending_items: reactive[int] = reactive(0)
    pending_total: reactive[float] = reactive(0.0)
    flavor: reactive[str] = reactive(IDLE_PHRASES[0])
    show_flavor: reactive[bool] = reactive(False)

    @staticmethod
    def _fit(text: str, width: int = 44) -> str:
        if len(text) <= width:
            return f"{text:<{width}}"
        return text[: width - 1] + "…"

    def render(self) -> str:
        if self.pending_items:
            lines = [f"  {self.status}"]
            if self.title:
                lines.append(f"  {self._fit(self.title, 54)}")
                detail = "  ·  ".join(p for p in [self.author, self.price] if p)
                if detail:
                    lines.append(f"  {detail}")
            noun = "item" if self.pending_items == 1 else "items"
            lines.append(
                f"  ⚠ TRANSMISSION OPEN — {self.pending_items} {noun} / "
                f"€{self.pending_total:.2f} — RUN SUBTOTAL TO CLOSE"
            )
            return "\n".join(lines)

        if not self.title:
            return f"  {self.flavor}"

        top = self.flavor if self.show_flavor else self.status
        lines = [f"  {top}", f"  {self._fit(self.title, 54)}"]
        detail = "  ·  ".join(p for p in [self.author, self.price] if p)
        if detail:
            lines.append(f"  {detail}")
        return "\n".join(lines)

    def _refresh_display_class(self) -> None:
        for cls in ("status-ready", "status-ok", "status-warn", "status-pending"):
            self.remove_class(cls)
        self.add_class("status-pending" if self.pending_items else self.status_class)

    def watch_status_class(self, _old: str, _new: str) -> None:
        self._refresh_display_class()

    def watch_pending_items(self, _old: int, _new: int) -> None:
        self._refresh_display_class()

    def set_pending(self, items: int, total: float) -> None:
        self.pending_items = items
        self.pending_total = total

    def rotate_flavor(self) -> None:
        self.flavor = random.choice(IDLE_PHRASES)
        self.show_flavor = not self.show_flavor

    def show_book(self, title: str, author: str, price: str, ok: bool = True) -> None:
        self.title = title
        self.author = author
        self.price = price
        self.status = "✦ LOGGED TO THE DATABANKS" if ok else "⚠  UNKNOWN — NOTIFY MANAGER"
        self.status_class = "status-ok" if ok else "status-warn"

    def show_sale_complete(self, total: float, method: str, count: int) -> None:
        noun = "item" if count == 1 else "items"
        self.title = f"{count} {noun}  ·  €{total:.2f}  ·  {method.upper()}"
        self.author = "Ready for next customer"
        self.price = ""
        self.status = "✦ SALE COMPLETE"
        self.status_class = "status-ok"

    def show_item(self, name: str, value: str) -> None:
        self.title = name
        self.author = ""
        self.price = value
        self.status = "✦ ITEM LOGGED"
        self.status_class = "status-ok"


class DailyManifest(Static):
    """Basket in progress + running daily totals."""

    basket_items: reactive[int] = reactive(0)
    basket_total: reactive[float] = reactive(0.0)
    items: reactive[int] = reactive(0)
    revenue: reactive[float] = reactive(0.0)
    cash: reactive[float] = reactive(0.0)
    card: reactive[float] = reactive(0.0)
    last_sync: reactive[str] = reactive("not yet")

    def render(self) -> str:
        if self.basket_items:
            basket_line = f"  {self.basket_items} item{'s' if self.basket_items != 1 else ''}   €{self.basket_total:.2f}\n"
        else:
            basket_line = "  —  empty\n"
        return (
            f"  TODAY'S TOTAL\n"
            f"  ─────────────────\n"
            f"  Items:   {self.items}\n"
            f"  Revenue: €{self.revenue:.2f}\n"
            f"  Cash:    €{self.cash:.2f}\n"
            f"  Card:    €{self.card:.2f}\n"
            f"  THIS SALE\n"
            f"  ─────────────────\n"
            f"{basket_line}"
        )

    def update_basket(self, items: int, total: float) -> None:
        self.basket_items = items
        self.basket_total = total

    def update_totals(self, items: int, revenue: float,
                      cash: float = 0.0, card: float = 0.0) -> None:
        self.items = items
        self.revenue = revenue
        self.cash = cash
        self.card = card

    def update_sync(self, sync_time: str) -> None:
        self.last_sync = sync_time


class NonIsbnPanel(Vertical):
    """
    Non-ISBN item buttons. Items loaded from config.
    Each item is a real Button so mouse/touch works; number keys still
    bound at app level for keyboard / scanner workflow.
    """

    DEFAULT_CSS = """
    NonIsbnPanel { height: auto; }
    NonIsbnPanel > .nonisbn-heading {
        color: #9090cc;
        padding: 0 1;
        margin-bottom: 0;
    }
    NonIsbnPanel > Button.nonisbn-btn {
        width: 100%;
        height: 3;
        margin: 0;
        text-align: left;
        content-align: left middle;
        padding: 0 1;
        background: #0f0f2a;
        border: solid #2a2a5a;
        color: #c8b89a;
    }
    NonIsbnPanel > Button.nonisbn-btn:hover {
        background: #1a1a4a;
        border: solid #6a6aaa;
        color: #d4af37;
    }
    NonIsbnPanel > Button.nonisbn-btn:focus {
        background: #1a1a4a;
        border: solid #d4af37;
        color: #d4af37;
        text-style: bold;
    }
    """

    def __init__(self, items: list[dict], heading: str = "OTHER ITEMS", **kwargs):
        super().__init__(**kwargs)
        self._items = items
        self._heading = heading

    def compose(self) -> ComposeResult:
        yield Static(f"  {self._heading}", classes="nonisbn-heading")
        for i, item in enumerate(self._items, 1):
            price = f"€{item['price']:.2f}" if item.get("price") else "enter price"
            yield Button(
                f" [{i}]  {item['name']:<20}  {price}",
                id=f"nonisbn-{i}",
                classes="nonisbn-btn",
            )

    def get_item(self, index: int) -> dict | None:
        """Return item dict for a given 1-based index (key press or button)."""
        if 1 <= index <= len(self._items):
            return self._items[index - 1]
        return None

    def index_from_button_id(self, button_id: str) -> int | None:
        """Parse '5' out of 'nonisbn-5'. Returns None if not a nonisbn button."""
        if button_id and button_id.startswith("nonisbn-"):
            try:
                return int(button_id.split("-", 1)[1])
            except ValueError:
                return None
        return None


class FooterBar(Static):
    """Rotating quote footer. Quote changes on each scan."""

    quote: reactive[str] = reactive("")

    def on_mount(self) -> None:
        self.refresh_quote()

    def render(self) -> str:
        return f"  {self.quote}"

    def refresh_quote(self) -> None:
        self.quote = get_quote_display()


class StockAlert(Static):
    """Shown briefly when stock drops to low threshold."""

    def show_alert(self, title: str, stock: int) -> None:
        self.update(f"  ⚠  LOW STOCK: '{title}' — only {stock} remaining")
        self.add_class("alert-visible")

    def clear_alert(self) -> None:
        self.update("")
        self.remove_class("alert-visible")
