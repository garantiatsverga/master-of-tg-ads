from typing import Dict, Any
from agents.base_agent import BaseAgent
from colordebug import *

class PromptAgent(BaseAgent):
    """
    Он создает промпты для остальных
    """

    def __init__(
        self,
        mcp_server, # Передаем сервер
        rules,
        templates,
        security_checker=None,
        metrics_collector=None,
    ):
        # 1. Передаем всё base_agent
        super().__init__(
            name="PromptAgent",
            mcp_server=mcp_server,
            security_checker=security_checker,
            metrics_collector=metrics_collector
        )
        self.rules = rules
        self.templates = templates

    def _register_agent_permissions(self):
        """Регистрация разрешений для PromptAgent"""
        # PromptAgent не вызывает инструменты MCP, поэтому пустой список
        self.mcp.set_agent_permissions(self.name, [])

    # 2. Внедряем свою валидацию в заготовленный слот
    def validate(self, payload: Dict[str, Any]) -> None:
        super().validate(payload) # Проверка, что это dict
        
        required_fields = ["product", "product_type", "audience", "goal"]
        missing = [f for f in required_fields if f not in payload]
        
        if missing:
            raise ValueError(f"Ошибка брифа: отсутствуют поля {missing}")

    # 3. Реализуем ТОЛЬКО бизнес-логику
    async def process(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """
        Метод вызывается автоматически внутри BaseAgent.handle()
        после всех проверок безопасности и валидации
        """
        
        # Шаг 1: Применяем экспертные правила
        rules_context = self.rules.get("ad_policies_and_guidelines", {})
        
        # Шаг 2: Выбираем нужный шаблон
        template = self.templates.get("default_template", {})
        
        # Шаг 3: Строим промпты (ТЗ) для следующих агентов
        text_prompt = (
            f"Создайте рекламный текст для продукта '{brief['product']}' "
            f"для аудитории '{brief['audience']}'. "
            f"Цель: {brief['goal']}. "
            f"Тип продукта: {brief['product_type']}. "
            f"Язык: {brief.get('language', 'ru')}. "
            f"Правила: {rules_context.get('description', '')}"
        )
        image_prompt = (
            f"Создайте баннер для продукта '{brief['product']}' "
            f"для аудитории '{brief['audience']}'. "
            f"Цель: {brief['goal']}. "
            f"Тип продукта: {brief['product_type']}. "
            f"Стиль: яркий, привлекательный, соответствующий правилам Telegram Ads"
        )

        # Возвращаем обогащенный контекст
        return {
            "target_text_prompt": text_prompt,
            "target_image_prompt": image_prompt,
            "meta": {
                "product": brief["product"],
                "audience": brief["audience"],
                "format": "telegram_ads"
            }
        }
