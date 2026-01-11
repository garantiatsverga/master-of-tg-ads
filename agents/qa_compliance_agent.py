from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from colordebug import *
import re
import asyncio

class QAComplianceAgent(BaseAgent):
    """
    Агент проверки качества и соответствия правилам.
    """
    
    def __init__(
        self,
        mcp_server=None,  # Не нужен
        security_checker=None,
        metrics_collector=None,
        rules: Dict[str, Any] = None
    ):
        super().__init__(
            name="QAComplianceAgent",
            mcp_server=mcp_server,
            security_checker=security_checker,
            metrics_collector=metrics_collector
        )
        
        # Правила проверки
        self.rules = rules or self._get_default_rules()
        
        checks_count = len(self.rules.get('checks', [])) if isinstance(self.rules, dict) else 0
        info(f"[{self.name}] Инициализирован с {checks_count} проверками", exp=True)
    
    def _register_agent_permissions(self):
        """Разрешения не нужны"""
        pass
    
    def _get_default_rules(self) -> Dict[str, Any]:
        """Правила проверки по умолчанию"""
        return {
            "version": "1.0",
            "checks": [
                {
                    "name": "text_length",
                    "description": "Длина текста не более 160 символов",
                    "check": lambda x: len(x) <= 160,
                    "error": "Текст слишком длинный (макс. 160 символов)"
                },
                {
                    "name": "no_profanity",
                    "description": "Отсутствие нецензурной лексики",
                    "check": lambda x: not any(word in x.lower() for word in [
                        'сука', 'блядь', 'хуй', 'пизда', 'ебать'
                    ]),
                    "error": "Обнаружена нецензурная лексика"
                },
                {
                    "name": "no_scam_keywords",
                    "description": "Отсутствие мошеннических фраз",
                    "check": lambda x: not any(phrase in x.lower() for phrase in [
                        '100% гарантия', 'быстро разбогатеть', 
                        'легкие деньги', 'без риска'
                    ]),
                    "error": "Обнаружены мошеннические фразы"
                }
            ]
        }
    
    async def _check_text_compliance(self, text: str) -> List[str]:
        """Проверка текста на соответствие правилам"""
        issues = []
        
        # Безопасный доступ к правилам
        if not isinstance(self.rules, dict):
            warning(f"[{self.name}] Правила имеют некорректный формат: {type(self.rules)}", exp=True)
            return ["Ошибка формата правил"]
        
        # Получаем checks безопасно
        checks = self.rules.get('checks', [])
        if not checks:
            # Используем дефолтные проверки
            checks = self._get_default_rules()["checks"]
            warning(f"[{self.name}] Использую дефолтные проверки", exp=True)
        
        for rule in checks:
            try:
                if isinstance(rule, dict) and 'check' in rule:
                    # Если правило имеет функцию проверки
                    if not rule["check"](text):
                        issues.append(f"{rule.get('name', 'unnamed')}: {rule.get('error', 'Нарушение правила')}")
                elif isinstance(rule, dict) and 'name' in rule:
                    # Простые правила по имени
                    rule_name = rule['name']
                    if rule_name == 'text_length':
                        max_chars = rule.get('max_chars', 160)
                        if len(text) > max_chars:
                            issues.append(f"text_length: Текст слишком длинный ({len(text)} > {max_chars})")
                    elif rule_name == 'no_profanity':
                        # Проверка нецензурной лексики
                        profanity = ['сука', 'блядь', 'хуй', 'пизда', 'ебать']
                        for word in profanity:
                            if word in text.lower():
                                issues.append(f"no_profanity: Обнаружена нецензурная лексика")
                                break
                    elif rule_name == 'has_cta':
                        # Проверка призыва к действию
                        cta_words = ['купи', 'закажи', 'подпишись', 'узнай', 'получи', 'переходи', 'жми']
                        if not any(word in text.lower() for word in cta_words):
                            issues.append(f"has_cta: Отсутствует призыв к действию")
                            
            except Exception as e:
                warning(f"[{self.name}] Ошибка проверки правила {rule}: {e}", exp=True)
        
        return issues
    
    async def _check_image_compliance(self, image_url: str) -> List[str]:
        """Проверка изображения (заглушка, в реальности проверяем контент)"""
        issues = []
        
        # Простая проверка формата URL
        if not image_url or not image_url.startswith(('http://', 'https://', 'file://')):
            issues.append("Некорректный URL изображения")
        
        # В реальной системе здесь была бы проверка контента изображения
        # через CV модели
        
        return issues
    
    def validate(self, payload: Dict[str, Any]) -> None:
        """Проверяем наличие материалов для проверки"""
        super().validate(payload)
        
        required = ["final_advertising_text"]
        missing = [f for f in required if f not in payload]
        
        if missing:
            raise ValueError(
                f"[{self.name}] Нечего проверять. Отсутствуют: {missing}"
            )
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Проверка качества и соответствия правилам
        """
        ad_text = context.get("final_advertising_text", "")
        banner_url = context.get("banner_url", "")
        
        info(f"[{self.name}] Проверка контента...", exp=True)
        
        # 1. Проверка текста
        text_issues = await self._check_text_compliance(ad_text)
        
        # 2. Проверка изображения (если есть)
        image_issues = []
        if banner_url:
            image_issues = await self._check_image_compliance(banner_url)
        
        # 3. Объединяем все проблемы
        all_issues = text_issues + image_issues
        
        # 4. Выносим вердикт
        is_approved = len(all_issues) == 0
        
        # 5. Записываем результат
        context["qa_status"] = "APPROVED" if is_approved else "REJECTED"
        context["qa_report"] = all_issues
        
        # БЕЗОПАСНЫЙ РАСЧЕТ ПРОЙДЕННЫХ ПРОВЕРОК:
        try:
            # Получаем checks безопасно
            if isinstance(self.rules, dict) and 'checks' in self.rules:
                total_checks = len(self.rules['checks'])
            else:
                total_checks = len(self._get_default_rules()['checks'])
            
            context["qa_checks_passed"] = total_checks - len(text_issues)
            context["qa_total_checks"] = total_checks
        except:
            # Если не удалось посчитать
            context["qa_checks_passed"] = "N/A"
            context["qa_total_checks"] = "N/A"
        
        if not is_approved:
            warning(f"[{self.name}] Контент НЕ прошел проверку:", exp=True)
            for issue in all_issues:
                warning(f"  - {issue}", exp=True)
        else:
            success(f"[{self.name}] Контент соответствует всем правилам!", exp=True)
        
        return context