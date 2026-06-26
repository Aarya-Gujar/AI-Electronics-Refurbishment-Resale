"""
protocol/bus.py
────────────────
Async Agent-to-Agent message bus built on asyncio.Queue.
Supports publish/subscribe, request-reply with timeout, and broadcast.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Callable, Dict, List, Optional

from loguru import logger

from protocol.message import AgentMessage, MessageType


# ── Message Bus ───────────────────────────────────────────────────────────────

class AgentBus:
    """
    Central async message broker.

    Each agent registers with a unique name and receives its own
    asyncio.Queue. The bus routes messages by recipient name.
    """

    def __init__(self) -> None:
        self._queues: Dict[str, asyncio.Queue[AgentMessage]] = {}
        self._middleware: List[Callable[[AgentMessage], AgentMessage]] = []
        self._pending_replies: Dict[str, asyncio.Future[AgentMessage]] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, agent_name: str) -> asyncio.Queue[AgentMessage]:
        """Register an agent and return its dedicated inbox queue."""
        if agent_name not in self._queues:
            self._queues[agent_name] = asyncio.Queue()
            logger.debug(f"[Bus] Agent registered: {agent_name}")
        return self._queues[agent_name]

    def deregister(self, agent_name: str) -> None:
        """Remove an agent's inbox from the bus."""
        self._queues.pop(agent_name, None)
        logger.debug(f"[Bus] Agent deregistered: {agent_name}")

    # ── Middleware ────────────────────────────────────────────────────────────

    def add_middleware(self, fn: Callable[[AgentMessage], AgentMessage]) -> None:
        """Add a message middleware (e.g. for logging, tracing, auth)."""
        self._middleware.append(fn)

    def _apply_middleware(self, msg: AgentMessage) -> AgentMessage:
        for fn in self._middleware:
            msg = fn(msg)
        return msg

    # ── Core Publish ──────────────────────────────────────────────────────────

    async def publish(self, message: AgentMessage) -> None:
        """
        Route a message to the target agent's inbox.
        If recipient is 'broadcast', deliver to all registered agents.
        """
        message = self._apply_middleware(message)

        # Check if this message is a response to a pending request-reply
        if (
            message.message_type in (MessageType.RESPONSE, MessageType.ERROR)
            and message.correlation_id
            and message.correlation_id in self._pending_replies
        ):
            future = self._pending_replies.pop(message.correlation_id)
            if not future.done():
                future.set_result(message)
            return

        if message.recipient == "broadcast":
            for name, q in self._queues.items():
                if name != message.sender:
                    await q.put(message)
            logger.debug(f"[Bus] Broadcast from {message.sender} → all agents")
        elif message.recipient in self._queues:
            await self._queues[message.recipient].put(message)
            logger.debug(
                f"[Bus] {message.sender} → {message.recipient} "
                f"({message.message_type.value})"
            )
        else:
            logger.warning(
                f"[Bus] Unroutable message: recipient '{message.recipient}' "
                f"not registered. Message id={message.id}"
            )

    # ── Request-Reply ─────────────────────────────────────────────────────────

    async def request(
        self,
        message: AgentMessage,
        timeout: float = 60.0,
    ) -> AgentMessage:
        """
        Send a REQUEST and await the correlated RESPONSE.

        Parameters
        ----------
        message : AgentMessage with message_type=REQUEST
        timeout : Seconds to wait before raising asyncio.TimeoutError

        Returns
        -------
        AgentMessage  The response message from the recipient agent.
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future[AgentMessage] = loop.create_future()
        self._pending_replies[message.id] = future

        await self.publish(message)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_replies.pop(message.id, None)
            raise asyncio.TimeoutError(
                f"[Bus] Request {message.id} to '{message.recipient}' "
                f"timed out after {timeout}s"
            )

    # ── Receive ───────────────────────────────────────────────────────────────

    async def receive(
        self, agent_name: str, timeout: Optional[float] = None
    ) -> AgentMessage:
        """
        Receive the next message from an agent's inbox.
        Raises asyncio.TimeoutError if timeout is set and no message arrives.
        """
        queue = self._queues.get(agent_name)
        if queue is None:
            raise KeyError(f"Agent '{agent_name}' is not registered on the bus.")

        if timeout is not None:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        return await queue.get()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def registered_agents(self) -> List[str]:
        return list(self._queues.keys())

    def queue_size(self, agent_name: str) -> int:
        q = self._queues.get(agent_name)
        return q.qsize() if q else 0


# ── Global Bus Singleton ──────────────────────────────────────────────────────

_bus: Optional[AgentBus] = None


def get_bus() -> AgentBus:
    """Return the global AgentBus singleton (created on first call)."""
    global _bus
    if _bus is None:
        _bus = AgentBus()
    return _bus


def reset_bus() -> None:
    """Reset the bus (useful for tests)."""
    global _bus
    _bus = None
