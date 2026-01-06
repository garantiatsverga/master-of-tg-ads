"""Тестовый скрипт БЕЗ настройки стандартного logging"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from ai_assistant.src.security.security_checker import SecurityChecker

from colordebug import (
    info, warning, error, success, debug,
    enable_console_output, set_log_format
)

# Настраиваем colordebug для консольного вывода
enable_console_output()
set_log_format('text')

# Конфигурация
config = {
    "telegram_ads": {
        "rule_files": {
            "telegram_rules": "./prompt_engine/telegram_rules.json",
            "banned_patterns": "./prompt_engine/banned_patterns.json"
        }
    }
}

async def run_tests():
    """Запуск тестов"""
    print("\n" + "_"*30)
    info("Консоль: общие сообщения")
    info("Файл security_checks.log: детальные логи")
    print("_"*30)
    
    checker = SecurityChecker(config, log_file="security_checks.log")
    
    info("\n1. Тест нормального текста (verbose=True):")
    result, msg = await checker.check_ad_compliance(
        "Супер предложение! Купите сейчас!",
        verbose=True
    )
    info(f"   Результат: {'ДА' if result else 'НЕТ'} - {msg}")
    
    info("\n2. Тест с нарушением (verbose=False):")
    result, msg = await checker.check_ad_compliance(
        "Это блядь отличное предложение!",
        verbose=False
    )
    info(f"   Результат: {'ДА' if result else 'НЕТ'} - {msg}")
    
    info("\n3. Тест промпта SD:")
    result, msg = await checker.validate_image_prompt(
        "A beautiful landscape with mountains",
        verbose=True
    )
    info(f"   Результат: {'ДА' if result else 'НЕТ'} - {msg}")
    
    print("\n" + "_"*30)
    info("Статистика проверок:")
    stats = checker.get_check_statistics()
    info(f"   Всего проверок: {stats['total_checks']}")
    info(f"   Успешно: {stats['passed']}")
    info(f"   Неудачно: {stats['failed']}")
    info(f"   Успешность: {stats['pass_rate']:.1f}%")
    print("_"*30)
    
    success("\nетальные логи сохранены в security_checks.log")

if __name__ == "__main__":
    asyncio.run(run_tests())