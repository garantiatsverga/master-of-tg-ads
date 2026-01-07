import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any
from colordebug import *
from ai_assistant.src.ai_assistant import AIAssistant

def check_dependencies():
    """Проверка и установка зависимостей."""
    # Проверяем, есть ли файл requirements.txt
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        error("Файл requirements.txt не найден", exp=True)
        sys.exit(1)
    
    # Проверяем, есть ли папка stable-diffusion-models
    models_dir = Path("stable-diffusion-models")
    if not models_dir.exists():
        warning("Папка stable-diffusion-models не найдена. Запуск установщика зависимостей...")
        try:
            # Запускаем установщик зависимостей
            from src.deps_installer import main as install_deps
            install_deps()
        except ImportError:
            error("Не удалось импортировать deps_installer. Пожалуйста, запустите src/deps_installer.py вручную")
            sys.exit(1)
        except Exception as e:
            error(f"Ошибка при установке зависимостей: {e}")
            sys.exit(1)

async def main():
    # Проверяем и устанавливаем зависимости
    check_dependencies()
    
    # Настраиваем логирование
    enable_file_logging("app.log", textwrapping=True, wrapint=80)
    info("Запуск конвейера Master of TG Ads", exp=True, textwrapping=True, wrapint=80)

    # Инициализируем AIAssistant
    assistant = AIAssistant()

    # Входные данные (Бриф от клиента)
    context: Dict[str, Any] = {
        "product": "Апельсиновый сок 'Солнечный'",
        "product_type": "Напитки",
        "audience": "Мамы детей от 3 до 7 лет",
        "goal": "Продажи через Telegram канал",
        "language": "ru"
    }

    try:
        # Запускаем конвейер через AIAssistant
        result = await assistant.run_advertising_pipeline(context)

        # Финальный результат
        info("Конвейер завершен успешно!", exp=True, textwrapping=True, wrapint=80)
        info("_"*30, exp=True, textwrapping=True, wrapint=80)
        info(f"СТАТУС ПРОВЕРКИ: {result.get('qa_status')}", exp=True, textwrapping=True, wrapint=80)
        info(f"ТЕКСТ: {result.get('final_advertising_text')}", exp=True, textwrapping=True, wrapint=80)
        info(f"БАННЕР: {result.get('banner_url')}", exp=True, textwrapping=True, wrapint=80)
        info(f"ОТЧЕТ QA: {result.get('qa_report')}", exp=True, textwrapping=True, wrapint=80)
        info("_"*30, exp=True, textwrapping=True, wrapint=80)

    except Exception as e:
        error(f"Критический сбой конвейера: {e}", exp=True, textwrapping=True, wrapint=80)

if __name__ == "__main__":
    asyncio.run(main())
