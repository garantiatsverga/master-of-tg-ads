import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
from io import BytesIO
import base64
import sys
from pathlib import Path

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from ai_assistant.src.llm.image_llm_adapter import StableDiffusionAdapter


class TestStableDiffusionAdapter(unittest.TestCase):
    """Юнит-тесты для StableDiffusionAdapter"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.config = {
            'stable_diffusion': {
                'base_url': 'http://test.sd',
                'width': 1920,
                'height': 1080,
                'negative_prompt': 'bad quality',
                'steps': 25,
                'cfg_scale': 7.5,
                'sampler': 'Euler a',
                'upscaler': 'ESRGAN_4x',
                'timeout': 600
            }
        }
        self.adapter = StableDiffusionAdapter(self.config)

    @patch('aiohttp.ClientSession.post')
    async def test_generate_image_success(self, mock_post):
        """Тест успешной генерации изображения"""
        # Создаем тестовое изображение
        test_image = Image.new('RGB', (100, 100), color='red')
        buffered = BytesIO()
        test_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Настройка мока
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'images': [img_base64],
            'parameters': {'seed': 12345}
        }
        mock_post.return_value.__aenter__.return_value = mock_response

        # Вызов метода
        result = await self.adapter.generate_image(
            prompt='test prompt',
            negative_prompt='test negative',
            steps=30
        )

        # Проверки
        self.assertIsInstance(result, Image.Image)
        self.assertEqual(result.size, (100, 100))
        self.assertIn('sd_params', result.info)
        self.assertEqual(result.info['sd_params']['prompt'], 'test prompt')

    @patch('aiohttp.ClientSession.post')
    async def test_generate_image_error(self, mock_post):
        """Тест обработки ошибки API"""
        # Настройка мока с ошибкой
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text.return_value = 'Bad Request'
        mock_post.return_value.__aenter__.return_value = mock_response

        # Проверка, что выбрасывается исключение
        with self.assertRaises(Exception) as context:
            await self.adapter.generate_image(prompt='test prompt')

        self.assertIn('SD-ошибка: 400 - Bad Request', str(context.exception))

    @patch('aiohttp.ClientSession.post')
    async def test_upscale_image(self, mock_post):
        """Тест апскейла изображения"""
        # Создаем тестовое изображение
        test_image = Image.new('RGB', (100, 100), color='blue')
        buffered = BytesIO()
        test_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Настройка мока
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'image': img_base64
        }
        mock_post.return_value.__aenter__.return_value = mock_response

        # Вызов метода
        result = await self.adapter.upscale_image(test_image, scale_factor=2.0)

        # Проверки
        self.assertIsInstance(result, Image.Image)
        self.assertEqual(result.size, (100, 100))

    @patch('aiohttp.ClientSession.post')
    async def test_img2img(self, mock_post):
        """Тест img2img преобразования"""
        # Создаем тестовое изображение
        test_image = Image.new('RGB', (100, 100), color='green')
        buffered = BytesIO()
        test_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Настройка мока
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'images': [img_base64]
        }
        mock_post.return_value.__aenter__.return_value = mock_response

        # Вызов метода
        result = await self.adapter.img2img(
            init_image=test_image,
            prompt='test prompt',
            denoising_strength=0.75
        )

        # Проверки
        self.assertIsInstance(result, Image.Image)
        self.assertEqual(result.size, (100, 100))


if __name__ == '__main__':
    unittest.main()