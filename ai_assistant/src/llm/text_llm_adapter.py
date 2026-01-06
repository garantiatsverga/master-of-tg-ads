from typing import List, AsyncGenerator
import aiohttp
import simdjson as sd
from config_manager import ConfigManager

class TextLLMAdapter:
    """Адаптер для работы с GigaChat API для генерации рекламных текстов"""
    
    def __init__(self, config=None):
        if not config:
            config = ConfigManager.load_config()
        
        self.config = config['llm']['gigachat']
        self.api_key = self.config['api_key']
        self.base_url = self.config['base_url']
        self.timeout = self.config.get('timeout', 120)
        
    async def generate_ad_copy(self, 
                             product_info: str,
                             style: str = "professional",
                             max_length: int = 160) -> str:
        """
        Генерация рекламного текста для баннера
        
        Args:
            product_info: Описание продукта/услуги
            style: Стиль текста (professional, creative, urgent, emotional)
            max_length: Максимальная длина текста (для Telegram Ads)
        
        Returns:
            Сгенерированный рекламный текст
        """
        
        prompt = self._create_ad_prompt(product_info, style, max_length)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "GigaChat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Ты опытный копирайтер для рекламных баннеров Telegram."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": self.config.get('temperature', 0.7),
                    "max_tokens": self.config.get('max_tokens', 500)
                },
                timeout=self.timeout
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    text = result['choices'][0]['message']['content'].strip()
                    
                    # Обрезаем до максимальной длины если нужно
                    if len(text) > max_length:
                        text = text[:max_length-3] + "..."
                    
                    return text
                else:
                    error_text = await response.text()
                    raise Exception(f"GigaChat API error: {response.status} - {error_text}")
    
    def _create_ad_prompt(self, product_info: str, style: str, max_length: int) -> str:
        """Создание промпта для генерации рекламного текста"""
        
        style_instructions = {
            "professional": "Профессиональный, деловой стиль. Акцент на выгоды и надежность.",
            "creative": "Креативный, запоминающийся стиль. Используй метафоры и яркие образы.",
            "urgent": "Срочное предложение. Создай ощущение дедлайна и ограниченности.",
            "emotional": "Эмоциональный стиль. Обращение к чувствам и желаниям клиента.",
            "clear": "Прямой и понятный стиль. Только факты и выгоды."
        }
        
        return f"""
        Сгенерируй текст для рекламного баннера в Telegram.
        
        О ПРОДУКТЕ:
        {product_info}
        
        ТРЕБОВАНИЯ:
        1. Стиль: {style_instructions.get(style, style_instructions['professional'])}
        2. Максимальная длина: {max_length} символов (ограничение Telegram Ads)
        3. Текст должен быть самодостаточным и цепляющим
        4. Включи призыв к действию (CTA)
        5. Выдели главную выгоду
        6. Избегай клише и шаблонных фраз
        
        ФОРМАТ:
        - Основной текст (до {max_length} символов)
        - Можно использовать эмоджи если уместно
        
        Пример хорошего текста:
        "🚀 Увеличь конверсию на 40%! Автоматизация рекламы в Telegram. Начни бесплатно!"
        
        Сгенерируй текст:
        """
    
    async def generate_multiple_variants(self,
                                       product_info: str,
                                       num_variants: int = 3,
                                       max_length: int = 160) -> List[str]:
        """Генерация нескольких вариантов текста"""
        variants = []
        
        styles = ["professional", "creative", "urgent", "emotional", "clear"]
        
        for i in range(min(num_variants, len(styles))):
            try:
                variant = await self.generate_ad_copy(
                    product_info=product_info,
                    style=styles[i],
                    max_length=max_length
                )
                variants.append(variant)
            except Exception as e:
                # Продолжаем генерировать остальные варианты при ошибке
                continue
        
        return variants