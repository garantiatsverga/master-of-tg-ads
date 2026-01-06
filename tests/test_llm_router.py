import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
import sys
from pathlib import Path

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from ai_assistant.src.llm.llm_router import LLMRouter


class TestLLMRouter(unittest.TestCase):
    """Юнит-тесты для LLMRouter"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.config = {
            'llm': {
                'gigachat': {
                    'api_key': 'test_api_key',
                    'base_url': 'https://test.api',
                    'timeout': 30
                }
            },
            'stable_diffusion': {
                'base_url': 'http://test.sd',
                'width': 1920,
                'height': 1080
            }
        }
        self.router = LLMRouter(self.config)

    @patch('ai_assistant.src.llm.text_llm_adapter.TextLLMAdapter.generate_ad_copy')
    async def test_generate_banner_text(self, mock_generate):
        """Тест генерации текста для баннера"""
        # Настройка мока
        mock_generate.return_value = 'Test banner text'

        # Вызов метода
        result = await self.router.generate_banner_text(
            product_description='Test product',
            style='professional'
        )

        # Проверки
        self.assertEqual(result, 'Test banner text')
        mock_generate.assert_called_once()

    @patch('ai_assistant.src.llm.image_llm_adapter.StableDiffusionAdapter.generate_image')
    async def test_generate_banner_image(self, mock_generate):
        """Тест генерации изображения для баннера"""
        # Создаем тестовое изображение
        test_image = MagicMock(spec=Image.Image)
        mock_generate.return_value = test_image

        # Вызов метода
        result = await self.router.generate_banner_image(
            image_prompt='test prompt'
        )

        # Проверки
        self.assertEqual(result, test_image)
        mock_generate.assert_called_once_with('test prompt')


class TestLLMRouterIntegration(unittest.TestCase):
    """Интеграционные тесты для LLMRouter"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.config = {
            'llm': {
                'gigachat': {
                    'api_key': 'test_api_key',
                    'base_url': 'https://test.api',
                    'timeout': 30
                }
            },
            'stable_diffusion': {
                'base_url': 'http://test.sd',
                'width': 1920,
                'height': 1080
            }
        }
        self.router = LLMRouter(self.config)

    @patch('ai_assistant.src.llm.text_llm_adapter.TextLLMAdapter.generate_ad_copy')
    @patch('ai_assistant.src.llm.image_llm_adapter.StableDiffusionAdapter.generate_image')
    async def test_full_banner_generation(self, mock_image_gen, mock_text_gen):
        """Интеграционный тест полной генерации баннера"""
        # Настройка моков
        mock_text_gen.return_value = 'Amazing product! Buy now! 🚀'
        test_image = MagicMock(spec=Image.Image)
        mock_image_gen.return_value = test_image

        # Генерация текста
        text_result = await self.router.generate_banner_text(
            product_description='Test product with great features',
            style='creative'
        )

        # Генерация изображения
        image_result = await self.router.generate_banner_image(
            image_prompt='A futuristic product in space'
        )

        # Проверки
        self.assertEqual(text_result, 'Amazing product! Buy now! 🚀')
        self.assertEqual(image_result, test_image)
        
        # Проверка, что оба метода были вызваны
        mock_text_gen.assert_called_once()
        mock_image_gen.assert_called_once()


if __name__ == '__main__':
    unittest.main()