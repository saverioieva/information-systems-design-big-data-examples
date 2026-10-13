"""Backward-compatible entry point: the default REST adapter is FastAPI."""

from order_service.main_fastapi import app

__all__ = ["app"]
