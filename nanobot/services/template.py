"""TemplateService — Jinja2 rendering service for agent prompts."""

import time
from datetime import datetime
from importlib.resources import files as pkg_files

from jinja2 import Environment, FileSystemLoader


class TemplateService:
    """Jinja2 template rendering service for agent prompts."""

    RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"

    def __init__(self) -> None:
        template_dir = str(pkg_files("nanobot") / "templates")
        self._env = Environment(
            loader=FileSystemLoader(template_dir),
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **kwargs: object) -> str:
        """Render a named .j2 template with the given variables."""
        return self._env.get_template(template_name).render(**kwargs)

    def render_runtime_context(
        self, channel: str | None = None, chat_id: str | None = None
    ) -> str:
        """Render the runtime metadata block."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        return self.render(
            "prompts/runtime_context.j2",
            runtime_context_tag=self.RUNTIME_CONTEXT_TAG,
            current_time=now,
            timezone=tz,
            channel=channel,
            chat_id=chat_id,
        )
