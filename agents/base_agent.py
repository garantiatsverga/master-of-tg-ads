import time
from abc import ABC, abstractmethod
from typing import Any, Dict
from colordebug import *

try:
    from ai_assistant.src.security.security_checker import SecurityChecker
    from ai_assistant.src.observability.metric_collector import MetricsCollector
except ImportError:
    # Если на хакатоне пути поплывут, пусть будут просто Any
    SecurityChecker = Any
    MetricsCollector = Any



class AgentError(Exception):
    """Базовая ошибка агента"""
    pass


class BaseAgent(ABC):
    """
    Базовый класс для всех агентов системы.
    Реализует:
    - единый жизненный цикл обработки запроса
    - безопасность
    - метрики
    - логирование
    """

    def __init__(
        self,
        name: str,
        mcp_server,
        security_checker=None,
        metrics_collector=None,
    ):
        self.name = name
        self.mcp = mcp_server
        self.security = security_checker
        self.metrics = metrics_collector
        self._register_agent_permissions()

    # TEMPLATE METHOD
    async def handle(self, payload: Dict[str, Any]) -> Any:
        """
        Фиксированный алгоритм обработки запроса.
        Менять нельзя — расширять можно.
        """
        start_time = time.perf_counter()
        info(f"[{self.name}] Start handling request", exp=True, textwrapping=True, wrapint=80)

        try:
            # 1. Security
            if self.security:
                allowed = await self.security.check(payload)
                if not allowed:
                    raise AgentError("Security policy violation")

            # 2. Validation
            self.validate(payload)

            # 3. Core logic (реализуется в наследнике)
            result = await self.process(payload)

            # 4. Metrics
            if self.metrics:
                self.metrics.increment(f"{self.name}.success")

            return result

        except Exception as e:
            error(f"[{self.name}] Error: {e}", exp=True, textwrapping=True, wrapint=80)
            if self.metrics:
                self.metrics.increment(f"{self.name}.error")
            raise

        finally:
            duration = time.perf_counter() - start_time
            info(f"[{self.name}] Done in {duration:.3f}s", exp=True, textwrapping=True, wrapint=80)

    # HOOK METHODS

    def validate(self, payload: Dict[str, Any]) -> None:
        """
        Базовая валидация.
        Можно переопределять.
        """
        if not isinstance(payload, dict):
            raise AgentError("Payload must be a dict")

    @abstractmethod
    async def process(self, payload: Dict[str, Any]) -> Any:
        """
        Главная бизнес-логика агента.
        ОБЯЗАТЕЛЬНО реализуется в наследнике.
        """
        pass

    def _register_agent_permissions(self):
        """Регистрация разрешений для агента"""
        pass
