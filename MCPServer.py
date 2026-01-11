import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Protocol, List  # Добавили List
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


#  TOOL INTERFACE (оставляем для совместимости, но не используем)

class BaseTool(ABC):
    """Контракт любого MCP-инструмента (оставляем для совместимости)"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass


#  TOOL REGISTRY (оставляем, но почти не используем)

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
    MCPServer v3 - Упрощенная версия без инструментов
    - Mediator для агентов
    - Policy-based
    - Production-ready
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        retry_policy: Optional[RetryPolicy] = None,
        cache_policy: Optional[CachePolicy] = None,
        security_checker: Optional[Any] = None,
    ):
        self.registry = registry or ToolRegistry()
        self.retry_policy = retry_policy or SimpleRetryPolicy()
        self.cache = cache_policy
        self.security = security_checker
        self._agent_permissions: Dict[str, List[str]] = {}
        
        warning("MCPServer работает в упрощенном режиме (инструменты упразднены)", exp=True)

    async def call(self, tool_name: str, agent_name: str = None, **kwargs) -> Any:
        """
        Упрощенный вызов - инструменты упразднены, используйте агентов напрямую
        """
        start_time = time.perf_counter()
        
        warning(f"Инструмент '{tool_name}' вызван, но инструменты упразднены. Используйте агентов напрямую.", exp=True)
        
        # Для обратной совместимости возвращаем заглушку
        if tool_name == "image.generate":
            return {
                "image_url": f"stub://{tool_name}/{hash(str(kwargs))}",
                "success": False,
                "error": "Инструменты упразднены. Используйте BannerDesignerAgent напрямую"
            }
        elif tool_name == "compliance.check":
            return {
                "is_approved": True,
                "issues": ["Проверка через инструменты упразднена. Используйте QAComplianceAgent напрямую"],
                "success": False
            }
        
        raise ToolNotFoundError(
            f"Инструмент '{tool_name}' упразднен. "
            f"Используйте агентов напрямую вместо вызовов через MCP."
        )

    def set_agent_permissions(self, agent_name: str, allowed_tools: List[str]) -> None:
        """Установить разрешения для агента (оставляем для совместимости)"""
        self._agent_permissions[agent_name] = allowed_tools
        debug(f"Разрешения для {agent_name}: {allowed_tools}", exp=True)

    def get_agent_permissions(self, agent_name: str) -> List[str]:
        """Получить разрешения для агента"""
        return self._agent_permissions.get(agent_name, [])
    
    def health_check(self) -> Dict[str, Any]:
        """Проверка состояния сервера"""
        return {
            "status": "running",
            "agents_registered": len(self._agent_permissions),
            "tools_registered": len(self.registry._tools),
            "mode": "simplified (no tools)"
        }