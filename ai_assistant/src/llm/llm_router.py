from typing import List, Optional
from PIL import Image
from .text_llm_adapter import TextLLMAdapter
from .image_llm_adapter import StableDiffusionAdapter
from config_manager import ConfigManager

class LLMRouter:
    """Маршрутизатор для текстовых и графических запросов"""
     
    def __init__(self, config=None):
        if not config:
            config = ConfigManager.load_config()
        
        self.text_adapter = TextLLMAdapter(config)
        self.image_adapter = StableDiffusionAdapter(config)
    
    async def generate_banner_text(self,
                                 product_description: str,
                                 style: str = "professional") -> str:
        """Генерация текста для баннера через GigaChat"""
        return await self.text_adapter.generate_ad_copy(
            product_info=product_description,
            style=style,
            max_length=160
        )
    
    async def generate_banner_image(self,
                                  image_prompt: str) -> Image:
        """Генерация изображения баннера через SD"""
        return await self.image_adapter.generate_image(image_prompt)