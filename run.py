import asyncio
from typing import Dict, Any
from colordebug import *
from ai_assistant.src.ai_assistant import AIAssistant

async def main():
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
