"""Persistent approval service for tool execution gating."""

import json
from pathlib import Path

from loguru import logger


class ApprovalService:
    """Persists granular 'always' approvals to workspace/approvals.json."""

    _KEY_EXTRACTORS: dict[str, str] = {
        "write_file": "path",
        "edit_file": "path",
        "read_file": "path",
        "exec": "command",
    }

    _EXEMPT_TOOLS = frozenset(("approve_tool", "list_approvals", "revoke_approval"))

    def __init__(self, workspace: Path, required: bool):
        self._path = workspace / "approvals.json"
        self._required = required
        self._data: dict[str, list[str]] = {}
        self._load()

    @classmethod
    def _extract_key(cls, tool_name: str, args: dict) -> str:
        """Extract a granular key from tool arguments."""
        param = cls._KEY_EXTRACTORS.get(tool_name)
        return args.get(param, "") if param else ""

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load approvals.json: {}", e)
                self._data = {}

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            logger.error("Failed to save approvals.json: {}", e)

    def needs_approval(self, tool_name: str, args: dict | None = None) -> bool:
        """Check if a tool call requires approval."""
        if not self._required:
            return False
        if tool_name in self._EXEMPT_TOOLS:
            return False
        return not self.is_approved(tool_name, args)

    def is_approved(self, tool_name: str, args: dict | None = None) -> bool:
        """Check if a tool call has permanent approval."""
        key = self._extract_key(tool_name, args) if args else ""
        return key in self._data.get(tool_name, [])

    def approve(self, tool_name: str, key: str) -> None:
        """Add permanent approval for a tool call."""
        self._data.setdefault(tool_name, [])
        if key not in self._data[tool_name]:
            self._data[tool_name].append(key)
            self._save()

    def revoke(self, tool_name: str | None = None, key: str | None = None) -> None:
        """Revoke approvals. No args = clear all. tool_name only = clear that tool. Both = clear specific."""
        if tool_name is None:
            self._data.clear()
        elif key is None:
            self._data.pop(tool_name, None)
        else:
            keys = self._data.get(tool_name, [])
            if key in keys:
                keys.remove(key)
                if not keys:
                    self._data.pop(tool_name, None)
        self._save()

    def list_all(self) -> dict[str, list[str]]:
        """Return all approvals for display."""
        return dict(self._data)
