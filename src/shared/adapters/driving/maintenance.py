from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify, request

logger = logging.getLogger("shared.maintenance")

MAINTENANCE_FLAG = Path("data/.maintenance")

WHITELIST = ("/admin/backups", "/auth", "/static", "/media")


def init_maintenance(app: Flask) -> None:
    """Register the maintenance-mode gate as a before_request hook."""

    @app.before_request
    def _maintenance_gate() -> None | tuple:
        if not MAINTENANCE_FLAG.exists():
            return None
        path: str = request.path
        if any(path.startswith(prefix) for prefix in WHITELIST):
            return None
        logger.warning("maintenance gate blocked", extra={"path": path})
        return jsonify({"error": "maintenance"}), 503


def enter_maintenance() -> None:
    """Create the maintenance flag file (creates parent dirs if missing)."""
    MAINTENANCE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    MAINTENANCE_FLAG.touch(exist_ok=True)
    logger.info("maintenance mode entered")


def exit_maintenance() -> None:
    """Remove the maintenance flag file. Idempotent if already absent."""
    try:
        MAINTENANCE_FLAG.unlink()
        logger.info("maintenance mode exited")
    except FileNotFoundError:
        pass
