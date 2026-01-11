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
        Создание промптов с переводом на английский для Stable Diffusion
        """
        
        # Русский текст для копирайтера (оставляем русский)
        text_prompt = f"""
        Создай рекламный текст для смартфона {brief['product']}.
        Аудитория: {brief['audience']}.
        Акцент на камеру и дизайн.
        Максимум 160 символов, с эмодзи.
        """
        
        # АНГЛИЙСКИЙ промпт для Stable Diffusion (SD лучше понимает английский)
        image_prompt_en = f"""
        professional product photography of a modern smartphone,
        {brief['product']}, 
        emphasis on camera design and premium build quality,
        product shot on clean white background,
        studio lighting, sharp focus, highly detailed,
        commercial advertisement style,
        technology aesthetic, minimalist design,
        showcasing phone from multiple angles,
        reflective surfaces, metallic finish,
        telephoto lens visible, camera module highlighted,
        8k resolution, professional photo
        """
        
        # Русская версия (на всякий случай)
        image_prompt_ru = f"""
        профессиональная продуктовая фотография современного смартфона,
        {brief['product']},
        акцент на дизайн камеры и премиальное качество сборки,
        фото продукта на чистом белом фоне,
        студийное освещение, четкий фокус, высокая детализация,
        стиль коммерческой рекламы,
        технологичная эстетика, минималистичный дизайн
        """
        
        # Короткая английская версия для SD (макс 77 токенов)
        short_image_prompt = f"professional product photo of {brief['product']} smartphone, emphasis on camera design, clean white background, studio lighting, detailed, advertisement"
        
        return {
            "target_text_prompt": text_prompt.strip(),
            "target_image_prompt": short_image_prompt.strip(),  # Английский для SD
            "full_image_prompt_en": image_prompt_en.strip(),
            "full_image_prompt_ru": image_prompt_ru.strip(),
            "meta": {
                "product": brief["product"],
                "prompt_language": "en",
                "prompt_version": "v3_english_for_sd"
            }
        }