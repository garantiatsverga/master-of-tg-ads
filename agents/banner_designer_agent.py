from typing import Dict, Any
from agents.base_agent import BaseAgent
from colordebug import *

class BannerDesignerAgent(BaseAgent):
    """
    Его задача на основе графического промпта создать баннер 
    и вернуть ссылку на готовое изображение.
    """

    def __init__(
        self,
        mcp_server,
        security_checker=None,
        metrics_collector=None,
    ):
        # Передаем всё BaseAgent.
        # Теперь защита и замеряется по времени.
        super().__init__(
            name="BannerDesignerAgent",
            mcp_server=mcp_server,
            security_checker=security_checker,
            metrics_collector=metrics_collector
        )

    def _register_agent_permissions(self):
        """Регистрация разрешений для BannerDesignerAgent"""
        self.mcp.set_agent_permissions(self.name, ["image.generate"])

    def validate(self, payload: Dict[str, Any]) -> None:
        """Проверяем, есть ли у нас ТЗ для картинки"""
        super().validate(payload)
        
        if "target_image_prompt" not in payload:
            raise ValueError(
                "Ошибка: В контексте отсутствует 'target_image_prompt'. "
                "Дизайнеру нечего рисовать!"
            )

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной процесс:
        1. Извлечь графический промпт.
        2. Вызвать ImageGenTool через MCP.
        3. Сохранить ссылку на результат.
        """
        
        image_prompt = context.get("target_image_prompt")
        
        try:
            # Обращаемся к генерации изображений
            # Этот инструмент зарегистрирован в MCPServer.py под именем "image.generate"
            response = await self.mcp.call(
                "image.generate",
                agent_name=self.name,
                prompt=image_prompt,
                size="1024x1024",
                quality="standard"
            )
            # Получаем URL сгенерированного изображения
            image_url = response.get("image_url", "")
        except Exception as e:
            error(f"[{self.name}] Ошибка при генерации баннера: {e}", exp=True, textwrapping=True, wrapint=80)
            image_url = ""

        if not image_url:
            error(f"[{self.name}] Инструмент вернул пустую ссылку на изображение", exp=True, textwrapping=True, wrapint=80)
            context["error"] = "Ошибка генерации баннера"
        else:
            # Записываем результат в общий журнал
            context["banner_url"] = image_url
            info(f"[{self.name}] Баннер успешно создан: {image_url}", exp=True, textwrapping=True, wrapint=80)
        
        return context
