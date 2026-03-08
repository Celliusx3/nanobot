"""HTTP channel — REST API for sending messages to nanobot."""

from __future__ import annotations

import asyncio
import json
import uuid

from aiohttp import web
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.http.service import HTTPService

_REQUEST_TIMEOUT = 300  # seconds


class HTTPChannel(BaseChannel):
    """HTTP channel that exposes a REST API for chat."""

    name = "http"

    def __init__(self, config, bus: MessageBus, http_service: HTTPService):
        super().__init__(config, bus)
        self._pending: dict[str, asyncio.Future] = {}

        # Register chat routes on shared HTTP service
        http_service.add_post("/v1/chat", self._handle_chat)
        http_service.add_get("/health", self._handle_health)
        logger.info("HTTP chat routes registered on port {}", http_service.port)

    async def start(self) -> None:
        self._running = True
        # Server is managed by HTTPService — just keep the channel alive
        await asyncio.Event().wait()

    async def stop(self) -> None:
        self._running = False
        # Cancel all pending requests
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    async def send(self, msg: OutboundMessage) -> None:
        """Resolve the pending future for this chat_id (final messages only)."""
        if msg.metadata.get("_progress"):
            return
        future = self._pending.pop(msg.chat_id, None)
        if future and not future.done():
            future.set_result(msg.content)

    async def _handle_chat(self, request: web.Request) -> web.Response:
        """POST /v1/chat — send a message to nanobot."""
        try:
            body = await request.json()
        except (json.JSONDecodeError, Exception):
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = body.get("message", "").strip()
        if not message:
            return web.json_response({"error": "Missing 'message' field"}, status=400)

        session = body.get("session", "default")
        chat_id = f"{session}:{uuid.uuid4().hex[:8]}"

        # Create a future to wait for the agent's response
        future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        self._pending[chat_id] = future

        try:
            # Publish to bus
            await self._handle_message(
                sender_id="http",
                chat_id=chat_id,
                content=message,
                session_key=f"http:{session}",
            )

            # Wait for response
            result = await asyncio.wait_for(future, timeout=_REQUEST_TIMEOUT)
            return web.json_response({"response": result, "session": session})

        except asyncio.TimeoutError:
            self._pending.pop(chat_id, None)
            return web.json_response({"error": "Request timed out"}, status=504)
        except Exception as e:
            self._pending.pop(chat_id, None)
            logger.error("HTTP chat error: {}", e)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """GET /health — health check."""
        return web.json_response({"status": "ok"})
