"""Delegate tool for coordinator/sub-agent pattern."""

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class DelegateTool(Tool):
    """Tool to delegate a task to a sub-agent that returns results to the coordinator."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "delegate"

    @property
    def description(self) -> str:
        return (
            "Delegate a task to a sub-agent. The sub-agent completes the task "
            "and returns results directly to you. Use this for complex subtasks "
            "that benefit from focused execution. Multiple delegate calls in a "
            "single response will run in parallel."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed task description for the sub-agent",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for logging/display",
                },
            },
            "required": ["task"],
        }

    async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        """Delegate a task to a sub-agent and return its result."""
        return await self._manager.delegate(task=task, label=label)
