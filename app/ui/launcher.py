# SPDX-License-Identifier: AGPL-3.0-or-later
"""
launcher.py - Mode selector.

One entry point. Three modes. That's it.

"A rebellion is built on hope." — Jyn Erso
"""

from textual.app import App, ComposeResult
from textual.widgets import Static, Button
from textual.binding import Binding
from textual.containers import Vertical
from textual import on
from datetime import datetime
from app.utils import load_config
from app.ui.quotes import get_quote_display
from app.ui.widgets import HintBar


CSS = """
Screen { align: center middle; }

#card {
    width: 80%;
    min-width: 50;
    max-width: 80;
    height: auto;
    border: solid #2a2a5a;
    background: #0f0f2a;
    padding: 2 4;
}

#title {
    color: #d4af37;
    text-align: center;
    padding: 1 0;
    border-bottom: solid #2a2a5a;
    margin-bottom: 2;
    text-style: bold;
}

#subtitle {
    color: #4a4a6a;
    text-align: center;
    margin-bottom: 2;
}

.mode-btn {
    width: 100%;
    height: 4;
    margin: 0 0 1 0;
    text-align: left;
    content-align: left middle;
    padding: 0 2;
}

#mode-counter   { border-left: thick #d4af37; }
#mode-intake    { border-left: thick #4aaa7a; }
#mode-payments  { border-left: thick #c87941; }
#mode-admin     { border-left: thick #6a6aaa; }

#footer-quote {
    color: #3a3a6a;
    text-align: center;
    text-style: italic;
    margin-top: 2;
    padding-top: 1;
    border-top: solid #1a1a3a;
}
"""


class LauncherApp(App):
    """Mode selector — shown at startup."""

    CSS_PATH = "theme.tcss"
    CSS = CSS

    BINDINGS = [
        Binding("1", "launch_counter", "Counter", show=True),
        Binding("2", "launch_intake", "Intake", show=True),
        Binding("3", "launch_payments", "Payments", show=True),
        Binding("4", "launch_admin", "Admin", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def compose(self) -> ComposeResult:
        config = load_config()
        shop = config.get("shop", {})
        ui = config.get("ui", {})
        app_title = ui.get("app_title", shop.get("name", "Shop"))
        item_plural = ui.get("item_plural", "items")
        today = datetime.now().strftime("%A  %d %B %Y")
        with Vertical(id="card"):
            yield Static(
                f"✦  {app_title.upper()}  ✦\n" + today,
                id="title",
            )
            yield Static("Select mode (click or press 1 / 2 / 3 / 4):", id="subtitle")
            yield Button(
                f" [1]  Counter Mode  —  Scan {item_plural} for sale",
                id="mode-counter",
                classes="mode-btn",
            )
            yield Button(
                " [2]  Intake Mode   —  Add new stock or delivery",
                id="mode-intake",
                classes="mode-btn",
            )
            yield Button(
                " [3]  Payments      —  Room hire, memberships, events, etc.",
                id="mode-payments",
                classes="mode-btn",
            )
            yield Button(
                " [4]  Admin Mode    —  Prices, corrections, reports  [PIN]",
                id="mode-admin",
                classes="mode-btn",
            )
            yield Static(get_quote_display(), id="footer-quote")
            yield HintBar(id="hint-bar")

    def on_mount(self) -> None:
        self.query_one(HintBar).update_from(self.BINDINGS)

    @on(Button.Pressed, "#mode-counter")
    def _click_counter(self) -> None:
        self.exit(result="counter")

    @on(Button.Pressed, "#mode-intake")
    def _click_intake(self) -> None:
        self.exit(result="intake")

    @on(Button.Pressed, "#mode-payments")
    def _click_payments(self) -> None:
        self.exit(result="payments")

    @on(Button.Pressed, "#mode-admin")
    def _click_admin(self) -> None:
        self.exit(result="admin")

    def action_launch_counter(self) -> None:
        self.exit(result="counter")

    def action_launch_intake(self) -> None:
        self.exit(result="intake")

    def action_launch_payments(self) -> None:
        self.exit(result="payments")

    def action_launch_admin(self) -> None:
        self.exit(result="admin")


def main():
    """
    Main entry point. Loops back to launcher after each mode exits,
    so staff can switch modes without restarting.
    """
    while True:
        launcher = LauncherApp()
        result = launcher.run()

        if result == "counter":
            from app.ui.counter import CounterApp
            if CounterApp().run() == "quit":
                break

        elif result == "intake":
            from app.ui.intake import IntakeApp
            if IntakeApp().run() == "quit":
                break

        elif result == "payments":
            from app.ui.payments import PaymentsApp
            if PaymentsApp().run() == "quit":
                break

        elif result == "admin":
            from app.ui.admin import AdminApp
            if AdminApp().run() == "quit":
                break

        else:
            break  # q or window closed


if __name__ == "__main__":
    main()
