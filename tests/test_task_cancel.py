"""Tests for /stop task cancellation and delegate tool."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_loop():
    """Create a minimal AgentLoop with mocked dependencies."""
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    workspace = MagicMock()
    workspace.__truediv__ = MagicMock(return_value=MagicMock())

    with patch("nanobot.agent.loop.ContextBuilder"), \
         patch("nanobot.agent.loop.SessionManager"), \
         patch("nanobot.agent.loop.SubagentManager"):
        loop = AgentLoop(bus=bus, provider=provider, workspace=workspace)
    return loop, bus


class TestHandleStop:
    @pytest.mark.asyncio
    async def test_stop_no_active_task(self):
        from nanobot.bus.events import InboundMessage

        loop, bus = _make_loop()
        msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="/stop")
        await loop._handle_stop(msg)
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert "No active task" in out.content

    @pytest.mark.asyncio
    async def test_stop_cancels_active_task(self):
        from nanobot.bus.events import InboundMessage

        loop, bus = _make_loop()
        cancelled = asyncio.Event()

        async def slow_task():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        task = asyncio.create_task(slow_task())
        await asyncio.sleep(0)
        loop._active_tasks["test:c1"] = [task]

        msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="/stop")
        await loop._handle_stop(msg)

        assert cancelled.is_set()
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert "stopped" in out.content.lower()

    @pytest.mark.asyncio
    async def test_stop_cancels_multiple_tasks(self):
        from nanobot.bus.events import InboundMessage

        loop, bus = _make_loop()
        events = [asyncio.Event(), asyncio.Event()]

        async def slow(idx):
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                events[idx].set()
                raise

        tasks = [asyncio.create_task(slow(i)) for i in range(2)]
        await asyncio.sleep(0)
        loop._active_tasks["test:c1"] = tasks

        msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="/stop")
        await loop._handle_stop(msg)

        assert all(e.is_set() for e in events)
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert "2 task" in out.content


class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_processes_and_publishes(self):
        from nanobot.bus.events import InboundMessage, OutboundMessage

        loop, bus = _make_loop()
        msg = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="hello")
        loop._process_message = AsyncMock(
            return_value=OutboundMessage(channel="test", chat_id="c1", content="hi")
        )
        await loop._dispatch(msg)
        out = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
        assert out.content == "hi"

    @pytest.mark.asyncio
    async def test_processing_lock_serializes(self):
        from nanobot.bus.events import InboundMessage, OutboundMessage

        loop, bus = _make_loop()
        order = []

        async def mock_process(m, **kwargs):
            order.append(f"start-{m.content}")
            await asyncio.sleep(0.05)
            order.append(f"end-{m.content}")
            return OutboundMessage(channel="test", chat_id="c1", content=m.content)

        loop._process_message = mock_process
        msg1 = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="a")
        msg2 = InboundMessage(channel="test", sender_id="u1", chat_id="c1", content="b")

        t1 = asyncio.create_task(loop._dispatch(msg1))
        t2 = asyncio.create_task(loop._dispatch(msg2))
        await asyncio.gather(t1, t2)
        assert order == ["start-a", "end-a", "start-b", "end-b"]


class TestDelegate:
    @pytest.mark.asyncio
    async def test_delegate_returns_result(self, tmp_path):
        """Sub-agent returns text directly to coordinator."""
        from nanobot.agent.subagent import SubagentManager

        provider = MagicMock()
        provider.get_default_model.return_value = "test-model"

        # Mock LLM to return text response (no tool calls)
        response = MagicMock()
        response.has_tool_calls = False
        response.content = "The answer is 42."
        provider.chat_with_retry = AsyncMock(return_value=response)

        mgr = SubagentManager(provider=provider, workspace=tmp_path)

        result = await mgr.delegate(task="What is the answer?", label="test")
        assert result == "The answer is 42."

    @pytest.mark.asyncio
    async def test_delegate_max_iterations(self, tmp_path):
        """Sub-agent returns fallback after hitting max iterations."""
        from nanobot.agent.subagent import SubagentManager

        provider = MagicMock()
        provider.get_default_model.return_value = "test-model"

        # Always return tool calls (never returns text)
        tool_call = MagicMock()
        tool_call.id = "tc1"
        tool_call.name = "exec"
        tool_call.arguments = {"command": "echo hi"}

        response = MagicMock()
        response.has_tool_calls = True
        response.tool_calls = [tool_call]
        response.content = ""
        provider.chat_with_retry = AsyncMock(return_value=response)

        mgr = SubagentManager(provider=provider, workspace=tmp_path)
        # Patch the internally-built tools so exec resolves
        mock_tools = MagicMock()
        mock_tools.get_definitions.return_value = [
            {"type": "function", "function": {"name": "exec"}}
        ]
        mock_tools.execute = AsyncMock(return_value="hi")

        with patch("nanobot.agent.subagent.ToolRegistry", return_value=mock_tools), \
             patch("nanobot.agent.subagent.ReadFileTool"), \
             patch("nanobot.agent.subagent.WriteFileTool"), \
             patch("nanobot.agent.subagent.EditFileTool"), \
             patch("nanobot.agent.subagent.ListDirTool"), \
             patch("nanobot.agent.subagent.ExecTool"):
            result = await mgr.delegate(task="loop forever")

        assert "no final response" in result.lower()
        assert provider.chat_with_retry.call_count == 15
