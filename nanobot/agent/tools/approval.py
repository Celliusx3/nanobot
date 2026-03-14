"""Tools for managing tool execution approvals."""

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.services.approval import ApprovalService


class ApproveToolTool(Tool):
    """Grant permanent execution permission for a specific tool."""

    def __init__(self, store: "ApprovalService"):
        self._store = store

    @property
    def name(self) -> str:
        return "approve_tool"

    @property
    def description(self) -> str:
        return "Grant permanent execution permission for a tool. Call this after the user confirms approval."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool to approve (e.g. exec, write_file).",
                },
                "key": {
                    "type": "string",
                    "description": "Granular key such as file path or command.",
                },
            },
            "required": ["tool_name", "key"],
        }

    async def execute(self, tool_name: str, key: str = "", **kwargs: Any) -> str:
        self._store.approve(tool_name, key)
        if key:
            return f"Approved: {tool_name}({key})"
        return f"Approved: {tool_name}"


class ListApprovalsTool(Tool):
    """List all current tool execution approvals."""

    def __init__(self, store: "ApprovalService"):
        self._store = store

    @property
    def name(self) -> str:
        return "list_approvals"

    @property
    def description(self) -> str:
        return "List all currently stored tool execution approvals."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        approvals = self._store.list_all()
        if not approvals:
            return "No approvals currently stored."
        lines = []
        for tool_name, keys in approvals.items():
            for k in keys:
                lines.append(f"  {tool_name}({k})" if k else f"  {tool_name}")
        return "Current approvals:\n" + "\n".join(lines)


class RevokeApprovalTool(Tool):
    """Revoke tool execution approvals."""

    def __init__(self, store: "ApprovalService"):
        self._store = store

    @property
    def name(self) -> str:
        return "revoke_approval"

    @property
    def description(self) -> str:
        return "Revoke tool execution approvals. Omit both parameters to clear all approvals."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Tool name to revoke. Omit to revoke all.",
                },
                "key": {
                    "type": "string",
                    "description": "Specific key to revoke. Omit to revoke all approvals for the tool.",
                },
            },
        }

    async def execute(self, tool_name: str | None = None, key: str | None = None, **kwargs: Any) -> str:
        self._store.revoke(tool_name, key)
        if tool_name and key:
            return f"Revoked: {tool_name}({key})"
        if tool_name:
            return f"Revoked all approvals for {tool_name}."
        return "All approvals cleared."
