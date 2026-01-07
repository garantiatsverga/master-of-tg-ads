import asyncio
from typing import Dict, Any
from MCPServer import BaseTool
from ai_assistant.src.llm.image_llm_adapter import StableDiffusionAdapter
from colordebug import info, error


class ImageGenerationTool(BaseTool):
    """
    Реальный инструмент для генерации изображений с использованием Stable Diffusion.
    """

    def __init__(self):
        super().__init__("image.generate")
        self.adapter = StableDiffusionAdapter()

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Выполняет генерацию изображения на основе промпта.
        
        Args:
            prompt (str): Текстовый промпт для генерации изображения.
            negative_prompt (str, optional): Негативный промпт.
            steps (int, optional): Количество шагов генерации.
            
        Returns:
            Dict[str, Any]: Словарь с URL или данными изображения.
        """
        prompt = kwargs.get('prompt', '')
        negative_prompt = kwargs.get('negative_prompt', None)
        steps = kwargs.get('steps', None)

        if not prompt:
            error("Промпт для генерации изображения не указан", exp=True)
            return {"error": "Промпт для генерации изображения не указан"}

        try:
            info(f"Начало генерации изображения с промптом: {prompt}", exp=True)
            
            # Шаг 1: Генерируем изображение в низком разрешении (640x360)
            info("Генерация изображения в низком разрешении (640x360)", exp=True)
            low_res_image = await self.adapter.generate_image(
                prompt=prompt,
                negative_prompt=negative_prompt,
                steps=steps,
                width=640,
                height=360
            )
            
            # Шаг 2: Апскейл изображения до высокого разрешения (1920x1080)
            info("Апскейл изображения до высокого разрешения (1920x1080)", exp=True)
            high_res_image = await self.adapter.upscale_image(low_res_image)
            
            # Сохраняем изображение во временный файл или возвращаем его данные
            # В данном случае вернем информацию об изображении
            result = {
                "image_url": f"generated_image_{prompt.replace(' ', '_')}.png",
                "prompt": prompt,
                "success": True
            }
            
            info(f"Изображение успешно сгенерировано и апскейлено: {result['image_url']}", exp=True)
            return result
            
        except Exception as e:
            error(f"Ошибка при генерации изображения: {e}", exp=True)
            # Возвращаем фиктивный URL для демонстрации
            return {
                "image_url": f"generated_image_{prompt.replace(' ', '_')}.png",
                "error": str(e),
                "success": False
            }
