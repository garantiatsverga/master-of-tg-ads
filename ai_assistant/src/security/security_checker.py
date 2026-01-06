import re
import simdjson as sd
from typing import Dict, Any, Tuple, List, Optional
from pathlib import Path
from datetime import datetime

from colordebug import (
    info, warning, error, success, debug,
    log_value, log_dict,
    enable_file_logging, enable_console_output, set_log_format
)

class SecurityChecker:
    """Проверка безопасности"""
    
    def __init__(self, config: Dict[str, Any], log_file: str = "security_checks.log"):
        self.config = config
        
        # Настраиваем colordebug
        enable_console_output()  # Отключаем консольный вывод
        set_log_format('text')    # Текст. формат
        enable_file_logging(log_file, textwrapping=False, wrapint=0)
        
        # Загружаем правила
        self.telegram_rules = self._load_rules_file(
            config['telegram_ads']['rule_files']['telegram_rules']
        )
        
        # Статистика
        self.check_stats = {
            'total_checks': 0,
            'passed': 0,
            'failed': 0,
            'violations_by_category': {}
        }
        
        info("Инициализирован с правилами Telegram")
    
    # def _print_to_console(self, message: str, level: str = "INFO"):
    #     """Ручной вывод в консоль"""
    #     colors = {
    #         'INFO': '\033[94m',      # синий
    #         'SUCCESS': '\033[92m',   # зеленый
    #         'WARNING': '\033[93m',   # желтый
    #         'ERROR': '\033[91m',     # красный
    #         'DEBUG': '\033[90m',     # серый
    #         'RESET': '\033[0m'
    #     }
        
    #     color_code = colors.get(level, colors['INFO'])
    #     print(f"{color_code}[{level}] {message}{colors['RESET']}")
    
    def _load_rules_file(self, path: str) -> Dict[str, Any]:
        """Загрузка файла правил"""
        try:
            full_path = Path(path)
            if not full_path.exists():
                full_path = Path(__file__).parent.parent.parent / path
            
            with open(full_path, 'r', encoding='utf-8') as f:
                rules = sd.load(f)
                
                info(f"Загружены правила из {full_path}")
                log_value("rules_loaded_from", str(full_path))
                log_value("rules_version", rules.get('version', 'unknown'))
                
                return rules
                
        except Exception as e:
            error(f"Ошибка загрузки правил {path}: {e}")
            log_value("error_type", type(e).__name__)
            log_value("error_details", str(e))
            
            return {}
    
    async def check_ad_compliance(
        self, 
        ad_text: str, 
        ad_link: str = None,
        user_context: Optional[Dict] = None,
        verbose: bool = False
    ) -> Tuple[bool, str]:
        """
        Проверка рекламы
        
        Args:
            verbose: True - детальные сообщения в консоль
                    False - только общие сообщения
        """
        self.check_stats['total_checks'] += 1
        check_id = f"check_{self.check_stats['total_checks']}"
        
        info(f"Начало проверки #{check_id}")
        log_value("check_id", check_id)
        log_value("text_length", len(ad_text))
        log_value("text_preview", ad_text[:100] + "..." if len(ad_text) > 100 else ad_text)
        
        if user_context:
            log_dict(user_context, "user_context")
        
        # 1. Проверка длины текста
        if len(ad_text) > 160:
            violation_msg = f"Текст превышает 160 символов ({len(ad_text)})"
            
            self._log_violation_to_file(
                violation_type="TEXT_LENGTH",
                ad_text=ad_text,
                details=violation_msg,
                check_id=check_id,
                user_context=user_context
            )
            
            self.check_stats['failed'] += 1
            
            # Консольное сообщение
            if verbose:
                error(f"Нарушение: длина текста {len(ad_text)} символов (макс. 160)")
                user_message = "Текст объявления слишком длинный"
            else:
                warning("Текст объявления слишком длинный")
                user_message = "Текст объявления слишком длинный"
            
            return False, user_message
        
        # 2. Проверка по паттернам
        pattern_result = self._quick_pattern_check(ad_text)
        if not pattern_result[0]:
            self._log_violation_to_file(
                violation_type="PATTERN_VIOLATION",
                ad_text=ad_text,
                details=pattern_result[1],
                check_id=check_id,
                user_context=user_context
            )
            
            self.check_stats['failed'] += 1
            
            if verbose:
                error(f"Нарушение: {pattern_result[1]}")
                user_message = f"Нарушение: {pattern_result[1]}"
            else:
                warning("Нарушение правил платформы")
                user_message = "Нарушение правил платформы"
            
            return False, user_message
        
        # 3. Проверка ссылки
        if ad_link:
            link_result = self._check_link_compliance(ad_link)
            if not link_result[0]:
                self._log_violation_to_file(
                    violation_type="LINK_VIOLATION",
                    ad_text=ad_text,
                    details=link_result[1],
                    check_id=check_id,
                    user_context=user_context
                )
                
                self.check_stats['failed'] += 1
                
                if verbose:
                    error(f"Нарушение: {link_result[1]}")
                    user_message = f"Нарушение: {link_result[1]}"
                else:
                    warning("Проблема со ссылкой в объявлении")
                    user_message = "Проблема со ссылкой в объявлении"
                
                return False, user_message
        
        # 4. Проверка правил Telegram
        telegram_result = self._check_telegram_rules(ad_text)
        if not telegram_result[0]:
            self._log_violation_to_file(
                violation_type="TELEGRAM_RULE",
                ad_text=ad_text,
                details=telegram_result[1],
                check_id=check_id,
                user_context=user_context
            )
            
            self.check_stats['failed'] += 1
            
            if verbose:
                error(f"Нарушение правил Telegram: {telegram_result[1]}")
                user_message = f"Нарушение правил Telegram: {telegram_result[1]}"
            else:
                warning("Нарушение правил платформы")
                user_message = "Нарушение правил платформы"
            
            return False, user_message
        
        # 5. Успешная проверка
        self.check_stats['passed'] += 1
        
        info(f"Проверка #{check_id} пройдена")
        log_value("check_result", "PASSED")
        
        # Консоль
        if verbose:
            success(f"Проверка #{check_id} пройдена")
            user_message = f"Проверка #{check_id} пройдена"
        else:
            success("Реклама соответствует правилам")
            user_message = "Реклама соответствует правилам"
        
        return True, user_message
    
    def _quick_pattern_check(self, text: str) -> Tuple[bool, str]:
        """Быстрая проверка паттернов"""
        text_lower = text.lower()
        
        profanity_words = ['сука', 'пидор', 'гомик', 'блядь', 'хуй', 'пизда', 'ебать']
        for word in profanity_words:
            if word in text_lower:
                debug(f"Найдена нецензурная лексика: {word}")
                log_value("matched_word", word)
                log_value("text_fragment", text)
                return False, f"Нецензурная лексика: {word}"
        
        return True, ""
    
    def _check_link_compliance(self, link: str) -> Tuple[bool, str]:
        """Проверка ссылки"""
        if 'bit.ly' in link or 'tinyurl' in link:
            warning(f"Обнаружена запрещенная ссылка: {link}")
            log_value("link_type", "shortener")
            log_value("link_url", link)
            return False, "Запрещенный формат ссылки"
        
        return True, ""
    
    def _check_telegram_rules(self, ad_text: str) -> Tuple[bool, str]:
        """Проверка по правилам Telegram"""
        text_lower = ad_text.lower()
        
        prohibited_categories = {
            'алкоголь': ['алкоголь', 'вино', 'водка', 'пиво', 'спирт'],
            'наркотики': ['наркотик', 'марихуана', 'героин', 'кокаин'],
            'оружие': ['оружие', 'пистолет', 'автомат', 'нож', 'пуля'],
        }
        
        for category, keywords in prohibited_categories.items():
            for keyword in keywords:
                if keyword in text_lower:
                    log_value("prohibited_category", category)
                    log_value("matched_keyword", keyword)
                    log_value("text_fragment", ad_text)
                    return False, f"Запрещенная категория: {category}"
        
        return True, ""
    
    def _log_violation_to_file(
        self,
        violation_type: str,
        ad_text: str,
        details: str,
        check_id: str,
        user_context: Optional[Dict] = None
    ):
        """Логирование нарушения в файл"""
        if violation_type not in self.check_stats['violations_by_category']:
            self.check_stats['violations_by_category'][violation_type] = 0
        self.check_stats['violations_by_category'][violation_type] += 1
        
        error(f"Нарушение типа {violation_type} в проверке #{check_id}")
        
        log_value("violation_type", violation_type)
        log_value("violation_details", details)
        log_value("check_id", check_id)
        log_value("full_ad_text", ad_text)
        log_value("text_length", len(ad_text))
        log_value("timestamp", datetime.now().isoformat())
        
        if user_context:
            log_dict(user_context, "violation_context", exp=True)
    
    async def validate_image_prompt(
        self, 
        sd_prompt: str, 
        verbose: bool = False
    ) -> Tuple[bool, str]:
        """Валидация промптов SD"""
        info("Проверка промпта для Stable Diffusion")
        log_value("sd_prompt", sd_prompt)
        
        prompt_lower = sd_prompt.lower()
        dangerous_words = {
            'nude': 'обнаженное тело',
            'naked': 'обнаженный',
            'blood': 'кровь',
            'gore': 'кровавые сцены',
            'violence': 'насилие',
            'weapon': 'оружие',
        }
        
        for en_word, ru_desc in dangerous_words.items():
            if en_word in prompt_lower:
                warning(f"Промпт содержит опасное слово: {en_word} ({ru_desc})")
                log_value("dangerous_word", en_word)
                log_value("dangerous_desc", ru_desc)
                log_value("prompt_fragment", sd_prompt)
                
                if verbose:
                    error(f"Промпт содержит {ru_desc}")
                    user_message = f"Промпт содержит {ru_desc}"
                else:
                    warning("Промпт содержит запрещенный контент")
                    user_message = "Промпт содержит запрещенный контент"
                
                return False, user_message
        
        info("Промпт безопасен для генерации")
        
        if verbose:
            success("Промпт безопасен для генерации")
            user_message = "Промпт безопасен для генерации"
        else:
            success("Промпт безопасен")
            user_message = "Промпт безопасен для генерации"
            
        return True, user_message
    
    def get_check_statistics(self) -> Dict[str, Any]:
        """Статистика проверок"""
        stats = self.check_stats.copy()
        
        if stats['total_checks'] > 0:
            stats['pass_rate'] = (stats['passed'] / stats['total_checks']) * 100
        else:
            stats['pass_rate'] = 0
        
        info("Статистика проверок")
        log_dict(stats, "security_check_stats")
        
        return stats