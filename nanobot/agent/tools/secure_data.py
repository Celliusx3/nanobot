"""Tool for generating HTML-based secret configuration links.

Self-contained: owns the form handlers, HTML templates, and route registration.
Routes are registered on the shared HTTPService at init time.
"""

from __future__ import annotations

from pathlib import Path
from string import Template
from typing import Any

from aiohttp import web
from loguru import logger

from nanobot.agent.tools.base import Tool
from nanobot.config.env import EnvStore
from nanobot.services.http.service import HTTPService


# ── HTML templates (loaded from nanobot/templates/html/) ─────────

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates" / "html"

_FORM_TEMPLATE = Template((_TEMPLATE_DIR / "secure_data_form.html").read_text())
_SUCCESS_TEMPLATE = Template((_TEMPLATE_DIR / "secure_data_success.html").read_text())
_ERROR_TEMPLATE = Template((_TEMPLATE_DIR / "secure_data_error.html").read_text())


# ── Tool ────────────────────────────────────────────────────────────


class SecureDataTool(Tool):
    """Tool that generates a browser link for configuring secrets."""

    def __init__(self, http_service: HTTPService):
        self._env_store = EnvStore()
        self._http_service = http_service

        # Register form routes on shared HTTP service
        http_service.add_get("/secure/setup", self._handle_form)
        http_service.add_post("/secure/setup", self._handle_submit)

    @property
    def name(self) -> str:
        return "secure_data"

    @property
    def description(self) -> str:
        return (
            "Generate a browser link for the user to configure secret environment "
            "variables (API keys, tokens). The user opens the link, fills in the "
            "values, and they are stored encrypted."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["skill"],
                    "description": "The type of resource that needs secrets configured.",
                },
                "data": {
                    "type": "object",
                    "description": "Type-specific data. For 'skill': {name, keys}.",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the resource.",
                        },
                        "keys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of env var names to configure.",
                        },
                    },
                    "required": ["name", "keys"],
                },
            },
            "required": ["type", "data"],
        }

    async def execute(self, type: str, data: dict[str, Any], **kwargs: Any) -> str:
        if type != "skill":
            return f"Unsupported type '{type}'. Currently only 'skill' is supported."

        name = data.get("name", "")
        keys = data.get("keys", [])

        if not name:
            return "Missing 'name' in data."
        if not keys:
            return f"No keys provided for '{name}'."

        # Filter already-configured keys
        missing = [k for k in keys if not self._env_store.get(name, k)]
        if not missing:
            return f"All environment variables for '{name}' are already configured."

        token = self._env_store.create_setup_token(name, missing)
        url = f"{self._http_service.base_url}/secure/setup?token={token}"
        return f"Open this link to configure secrets for '{name}':\n\n{url}\n\nLink expires in 10 minutes."

    # ── HTTP handlers ───────────────────────────────────────────────

    async def _handle_form(self, request: web.Request) -> web.Response:
        """GET /secure/setup?token=... — render secret configuration form."""
        token = request.query.get("token", "")
        payload = self._env_store.decode_setup_token(token)
        if not payload:
            html = _ERROR_TEMPLATE.substitute(
                message="This link has expired or is invalid. Please request a new one."
            )
            return web.Response(text=html, content_type="text/html", status=400)

        skill_name = payload["skill_name"]
        keys = payload["keys"]
        fields = "\n    ".join(
            f'<label for="{k}">{k}</label>\n    '
            f'<input type="password" id="{k}" name="{k}" required placeholder="Enter {k}">'
            for k in keys
        )
        html = _FORM_TEMPLATE.substitute(skill_name=skill_name, token=token, fields=fields)
        return web.Response(text=html, content_type="text/html")

    async def _handle_submit(self, request: web.Request) -> web.Response:
        """POST /secure/setup — store submitted secrets."""
        data = await request.post()
        token = data.get("token", "")
        payload = self._env_store.decode_setup_token(token)
        if not payload:
            html = _ERROR_TEMPLATE.substitute(
                message="This link has expired or is invalid. Please request a new one."
            )
            return web.Response(text=html, content_type="text/html", status=400)

        skill_name = payload["skill_name"]
        keys = payload["keys"]
        count = 0
        for k in keys:
            value = data.get(k, "")
            if value:
                self._env_store.set(skill_name, k, value)
                count += 1

        logger.info("Secure data: saved {} secret(s) for '{}'", count, skill_name)
        html = _SUCCESS_TEMPLATE.substitute(count=count, skill_name=skill_name)
        return web.Response(text=html, content_type="text/html")
