# SPDX-License-Identifier: AGPL-3.0-or-later
"""
dashboard.py - Read-only sales/stock dashboard, served to other devices on
the shop's local network. No authentication — LAN only, never port-forward.

Runs as its own process, separate from the till app:
    python -m app.dashboard
"""

from flask import Flask, g, request, render_template

from app.catalog import get_db, get_inhouse_prefix
from app.utils import load_config, get_logger, parse_date_str, format_date
from app.summary import get_daily_sales, get_sales_summary, get_sales_tally, get_low_stock


def _range_summary(rows: list[dict]) -> dict:
    """Totals/cash/card summed across get_sales_tally() rows (a date range)."""
    return {
        "total_transactions": None,  # not meaningful once grouped by title
        "total_items_sold": sum(r["qty"] for r in rows),
        "total_revenue": round(sum(r["revenue"] for r in rows), 2),
        "cash_revenue": round(sum(r["cash"] for r in rows), 2),
        "card_revenue": round(sum(r["card"] for r in rows), 2),
    }


def create_app(config: dict) -> Flask:
    app = Flask(__name__)
    app.config["COLOPHON_CONFIG"] = config

    @app.before_request
    def _open_db():
        g.conn = get_db(config)

    @app.teardown_appcontext
    def _close_db(exception=None):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    @app.route("/")
    def index():
        today = format_date()
        start_raw = request.args.get("start")
        end_raw = request.args.get("end")

        error = None
        is_default = True

        if start_raw or end_raw:
            start = parse_date_str(start_raw) if start_raw else None
            end = parse_date_str(end_raw) if end_raw else None
            if start is None or (end_raw and end is None):
                error = "Couldn't understand that date — showing today instead."
                start = end = today
            else:
                end = end or start
                is_default = start == today and end == today
        else:
            start = end = today

        inhouse_prefix = get_inhouse_prefix(config)
        tally = get_sales_tally(g.conn, start, end, inhouse_prefix=inhouse_prefix)

        if start == today and end == today:
            summary = get_sales_summary(get_daily_sales(today, g.conn))
        else:
            summary = _range_summary(tally)

        low_threshold = config.get("stock", {}).get("low_stock_threshold", 2)
        low_stock = get_low_stock(low_threshold, g.conn)

        dash_cfg = config.get("dashboard", {})

        return render_template(
            "dashboard/index.html",
            shop_name=config.get("shop", {}).get("name", "Shop"),
            start=start,
            end=end,
            today=today,
            is_default=is_default,
            error=error,
            summary=summary,
            tally=tally,
            low_stock=low_stock,
            refresh_seconds=dash_cfg.get("refresh_seconds", 30),
        )

    return app


def main():
    config = load_config()
    logger = get_logger("dashboard", config)
    dash_cfg = config.get("dashboard", {})

    if not dash_cfg.get("enabled", False):
        print("Dashboard is disabled (set dashboard.enabled: true in config/settings.yaml).")
        return

    port = dash_cfg.get("port", 8088)
    app = create_app(config)
    logger.info(f"Starting dashboard on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
