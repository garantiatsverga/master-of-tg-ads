from typing import Dict, Any
from agents.base_agent import BaseAgent
from colordebug import *

class CopywriterAgent(BaseAgent):
    """
    Его задачапревратить текстовое ТЗ (prompt) в финальный рекламный пост.
    """

    def __init__(
        self,
        mcp_server,
        security_checker=None,
        metrics_collector=None,
    ):
        # Называем агента и передаем зависимости base_agent
        super().__init__(
            name="CopywriterAgent",
            mcp_server=mcp_server,
            security_checker=security_checker,
            metrics_collector=metrics_collector
        )

    def _register_agent_permissions(self):
        """Регистрация разрешений для CopywriterAgent"""
        self.mcp.set_agent_permissions(self.name, ["text.generate"])

    def validate(self, payload: Dict[str, Any]) -> None:
        """Проверяем, принес ли нам PromptAgent проект для работы"""
        super().validate(payload)
        
        if "target_text_prompt" not in payload:
            raise ValueError("Ошибка: В контексте отсутствует 'target_text_prompt'. Копирайтеру нечего писать!")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной процесс:
        1. Берем промпт.
        2. Временно отключаем генерацию текста через API GigaChat.
        3. Возвращаем фиктивный текст.
        """
        
        text_prompt = context.get("target_text_prompt")
        
        # Временно отключаем генерацию текста через API GigaChat
        final_text = "Текст временно отключен"
        
        # Записываем результат в общий журнал (контекст)
        context["final_advertising_text"] = final_text
        
        return context
