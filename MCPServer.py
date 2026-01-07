import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Protocol
from colordebug import *


# ERRORS

class MCPError(Exception):
    """Базовая ошибка MCP"""


class ToolNotFoundError(MCPError):
    pass


class ToolExecutionError(MCPError):
    pass


class SecurityError(MCPError):
    pass


#  TOOL INTERFACE

class BaseTool(ABC):
    """Контракт любого MCP-инструмента"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass


#  TOOL REGISTRY

class ToolRegistry:
    """Реестр инструментов (Single Responsibility)"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' is not registered")
        return self._tools[name]


# POLICIES

class RetryPolicy(Protocol):
    async def run(self, operation, *, tool_name: str) -> Any:
        ...


class CachePolicy(Protocol):
    def get(self, key: str) -> Optional[Any]:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


## Retry Policy

class SimpleRetryPolicy:
    """Production-safe retry с backoff"""

    def __init__(self, retries: int = 3, delay: float = 1.0):
        self.retries = retries
        self.delay = delay

    async def run(self, operation, *, tool_name: str) -> Any:
        last_exc = None

        for attempt in range(1, self.retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_exc = e
                warning(
                    f"[RetryPolicy] {tool_name} failed "
                    f"(attempt {attempt}/{self.retries}): {e}",
                    exp=True, textwrapping=True, wrapint=80
                )
                if attempt < self.retries:
                    await asyncio.sleep(self.delay)

        raise ToolExecutionError(
            f"Tool '{tool_name}' failed after {self.retries} retries"
        ) from last_exc


## Cache Policy

class InMemoryCachePolicy:
    """Простой cache, легко заменить на Redis"""

    def __init__(self):
        self._store: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value


# MCP SERVER

class MCPServer:
    """
    MCPServer v3
    - Mediator
    - Policy-based
    - Production-ready
    """

    def __init__(
        self,
        registry: ToolRegistry,
        retry_policy: RetryPolicy,
        cache_policy: Optional[CachePolicy] = None,
        security_checker: Optional[Any] = None,
    ):
        self.registry = registry
        self.retry_policy = retry_policy
        self.cache = cache_policy
        self.security = security_checker
        self.logger = None
        self._agent_permissions: Dict[str, List[str]] = {}

    async def call(self, tool_name: str, agent_name: str = None, **kwargs) -> Any:
        start_time = time.perf_counter()

        cache_key = f"{tool_name}:{hash(frozenset(kwargs.items()))}"

        # 1. Cache
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                info(f"[CACHE HIT] {tool_name}", exp=True, textwrapping=True, wrapint=80)
                return cached

        # 2. Check agent permissions
        if agent_name and self._agent_permissions:
            allowed_tools = self._agent_permissions.get(agent_name, [])
            if tool_name not in allowed_tools:
                raise SecurityError(f"Agent '{agent_name}' is not allowed to use tool '{tool_name}'")

        # 3. Security
        if self.security:
            allowed = await self.security.check(kwargs)
            if not allowed:
                raise SecurityError(f"Access denied for tool '{tool_name}'")

        # 4. Tool lookup
        tool = self.registry.get(tool_name)

        # 4. Execution via RetryPolicy
        async def operation():
            info(f"[MCP] Executing {tool_name}", exp=True, textwrapping=True, wrapint=80)
            return await tool.execute(**kwargs)

        result = await self.retry_policy.run(operation, tool_name=tool_name)

        # 5. Save to cache
        if self.cache:
            self.cache.set(cache_key, result)

        duration = time.perf_counter() - start_time
        info(f"[MCP] {tool_name} completed in {duration:.3f}s", exp=True, textwrapping=True, wrapint=80)

        return result

    def set_agent_permissions(self, agent_name: str, allowed_tools: List[str]) -> None:
        """Установить разрешения для агента"""
        self._agent_permissions[agent_name] = allowed_tools

    def get_agent_permissions(self, agent_name: str) -> List[str]:
        """Получить разрешения для агента"""
        return self._agent_permissions.get(agent_name, [])
