# SPDX-License-Identifier: AGPL-3.0-or-later
"""
utils.py - Shared helper functions for Colophon
"""

import os
import csv
import logging
import yaml
from datetime import datetime
from pathlib import Path


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Load YAML config file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_logger(name: str, config: dict) -> logging.Logger:
    """Set up a named logger writing to logs/ directory."""
    log_dir = Path(config["logging"]["log_dir"])
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(config["logging"]["level"])

    if not logger.handlers:
        fh = logging.FileHandler(log_file)
        ch = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


def is_mount_available(mount_path: str) -> bool:
    """Check if the office network share is mounted and writable."""
    path = Path(mount_path)
    return path.is_mount() and os.access(path, os.W_OK)


def get_report_path(config: dict, date_str: str) -> Path:
    """
    Return the path to write CSV reports to, under YYYY/MM/ subdirectory.
    Uses office mount if available, falls back to local sync/ folder.
    """
    mount = config["office_sync"]["mount_path"]
    subdir = config["office_sync"]["report_subdir"]
    fallback = Path(config["office_sync"]["fallback_local"])
    year, month = date_str[:4], date_str[5:7]

    if is_mount_available(mount):
        report_dir = Path(mount) / subdir / year / month
    else:
        report_dir = fallback / year / month

    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_csv(filepath: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """
    Write a list of dicts to a CSV file atomically: write to a temp file in
    the same directory, then replace the target in one step. Avoids leaving
    a half-written report if the office share drops mid-write.
    """
    filepath = Path(filepath)
    tmp_path = filepath.with_name(f".{filepath.name}.tmp")
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, filepath)


def timestamp_now() -> str:
    """Return current datetime as ISO string."""
    return datetime.now().isoformat(timespec="seconds")


def format_date(dt: datetime = None) -> str:
    """Return date string YYYY-MM-DD, today if no datetime given."""
    return (dt or datetime.now()).strftime("%Y-%m-%d")


def parse_date_str(raw: str) -> str | None:
    """Parse a YYYY-MM-DD string, returning the normalized string or None if invalid."""
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None
