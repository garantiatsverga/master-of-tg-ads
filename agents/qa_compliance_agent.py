from typing import Dict, Any
from agents.base_agent import BaseAgent
from colordebug import *

class QAComplianceAgent(BaseAgent):
    """
    Проверяет финальный контент (текст и баннер) на соответствие 
    правилам площадки и исходному брифу.
    """

    def __init__(
        self,
        mcp_server,
        security_checker=None,
        metrics_collector=None,
    ):
        # Надеваем BaseAgent.
        # Нужна защита и учет времени
        super().__init__(
            name="QAComplianceAgent",
            mcp_server=mcp_server,
            security_checker=security_checker,
            metrics_collector=metrics_collector
        )

    def _register_agent_permissions(self):
        """Регистрация разрешений для QAComplianceAgent"""
        self.mcp.set_agent_permissions(self.name, ["compliance.check"])

    def validate(self, payload: Dict[str, Any]) -> None:
        """Проверяем, принесли ли нам готовые материалы на проверку"""
        super().validate(payload)
        
        # Нужны и текст, и картинка, чтобы вынести вердикт
        required = ["final_advertising_text", "banner_url"]
        missing = [f for f in required if f not in payload]
        
        if missing:
            raise ValueError(f"Ошибка QA: Нечего проверять. Отсутствуют: {missing}")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной процесс:
        1. Собрать финальный контент.
        2. Отправить его на проверку инструменту compliance.check.
        3. Вынести вердикт: PASS или FAIL.
        """
        
        ad_text = context.get("final_advertising_text")
        ad_image = context.get("banner_url")
        
        try:
            # Обращаемся к "экспертной системе" через mcp
            # Инструмент compliance.check анализирует текст и картинку по базе правил
            response = await self.mcp.call(
                "compliance.check",
                agent_name=self.name,
                text=ad_text,
                image_url=ad_image,
                rules_version="tg_ads_2026"
            )
            is_approved = response.get("is_approved", False)
            issues = response.get("issues", [])
        except Exception as e:
            error(f"[{self.name}] Ошибка при проверке контента: {e}", exp=True, textwrapping=True, wrapint=80)
            is_approved = False
            issues = ["Ошибка при проверке контента"]

        # Записываем результат проверки
        context["qa_status"] = "APPROVED" if is_approved else "REJECTED"
        context["qa_report"] = issues

        if not is_approved:
            warning(f"[{self.name}] Контент НЕ прошел проверку: {issues}", exp=True, textwrapping=True, wrapint=80)
        else:
            info(f"[{self.name}] Контент полностью соответствует правилам", exp=True, textwrapping=True, wrapint=80)
        
        return context
