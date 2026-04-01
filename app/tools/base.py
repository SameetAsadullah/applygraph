"""Base classes for MCP-style tools used by the workflow."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from app.telemetry.tracing import workflow_span


class ToolError(RuntimeError):
    """Raised when a tool fails to execute."""


class Tool(Protocol):
    name: str

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - protocol only
        ...


@dataclass
class BaseTool:
    name: str
    description: str

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self._execute(lambda: self.run(*args, **kwargs))

    async def run(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    async def _execute(self, handler: Callable[[], Awaitable[Any]]) -> Any:
        with workflow_span(f"tool.{self.name}") as span:
            try:
                result = await handler()
                span.set_attribute("tool.success", True)
                return result
            except Exception as exc:  # pragma: no cover - traced failure path
                span.set_attribute("tool.success", False)
                span.record_exception(exc)
                raise
