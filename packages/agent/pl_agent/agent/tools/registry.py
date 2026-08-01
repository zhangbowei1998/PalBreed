"""Tool registry — execute tools by name from LLM tool_calls."""

from __future__ import annotations

import json

from .base import Tool, ToolError


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ToolError("tool.name cannot be empty")
        self._tools[tool.name] = tool

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def to_openai_functions(self) -> list[dict]:
        return [tool.to_openai_function() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict | str) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"unknown tool: {name}")
        try:
            if isinstance(arguments, str):
                parsed = json.loads(arguments) if arguments.strip() else {}
            elif isinstance(arguments, dict):
                parsed = arguments
            else:
                raise ToolError(f"invalid arguments for {name}")
            result = await tool.run(**parsed)
            return {"name": name, "result": result}
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ToolError(f"tool {name} failed: {exc}") from exc
