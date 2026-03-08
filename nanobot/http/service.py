"""Shared HTTP server for nanobot.

Channels and tools register routes via add_get/add_post.
All routes must be registered before start() is called.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from aiohttp import web
from loguru import logger


class HTTPService:
    """Shared HTTP server that channels and tools register routes on."""

    def __init__(self, port: int = 18790):
        self.port = port
        self.base_url = os.environ.get("BASE_URL", f"http://localhost:{port}").rstrip("/")
        self._app = web.Application()
        self._runner: web.AppRunner | None = None

    def add_get(self, path: str, handler: Callable[..., Any]) -> None:
        """Register a GET route."""
        self._app.router.add_get(path, handler)

    def add_post(self, path: str, handler: Callable[..., Any]) -> None:
        """Register a POST route."""
        self._app.router.add_post(path, handler)

    async def start(self) -> None:
        """Start the HTTP server. All routes must be registered before this."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        logger.info("HTTP server listening on 0.0.0.0:{}", self.port)

    async def stop(self) -> None:
        """Stop the HTTP server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
