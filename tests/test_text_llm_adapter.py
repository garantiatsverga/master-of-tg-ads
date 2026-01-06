import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from ai_assistant.src.llm.text_llm_adapter import TextLLMAdapter


class TestTextLLMAdapter(unittest.TestCase):
    """Юнит-тесты для TextLLMAdapter"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.config = {
            'llm': {
                'gigachat': {
                    'api_key': 'test_api_key',
                    'base_url': 'https://test.api',
                    'timeout': 30,
                    'temperature': 0.7,
                    'max_tokens': 500
                }
            }
        }
        self.adapter = TextLLMAdapter(self.config)

    @patch('aiohttp.ClientSession.post')
    async def test_generate_ad_copy_success(self, mock_post):
        """Тест успешной генерации рекламного текста"""
        # Настройка мока
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Test advertisement text with emoji 🚀'
                }
            }]
        }
        mock_post.return_value.__aenter__.return_value = mock_response

        # Вызов метода
        result = await self.adapter.generate_ad_copy(
            product_info='Test product',
            style='professional',
            max_length=160
        )

        # Проверки
        self.assertEqual(result, 'Test advertisement text with emoji 🚀')
        mock_post.assert_called_once()

    @patch('aiohttp.ClientSession.post')
    async def test_generate_ad_copy_error(self, mock_post):
        """Тест обработки ошибки API"""
        # Настройка мока с ошибкой
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text.return_value = 'Internal Server Error'
        mock_post.return_value.__aenter__.return_value = mock_response

        # Проверка, что выбрасывается исключение
        with self.assertRaises(Exception) as context:
            await self.adapter.generate_ad_copy(
                product_info='Test product',
                style='professional',
                max_length=160
            )

        self.assertIn('GigaChat API error: 500 - Internal Server Error', str(context.exception))

    async def test_create_ad_prompt(self):
        """Тест создания промпта"""
        prompt = self.adapter._create_ad_prompt(
            product_info='Test product description',
            style='professional',
            max_length=160
        )

        # Проверки содержимого промпта
        self.assertIn('Test product description', prompt)
        self.assertIn('Профессиональный, деловой стиль', prompt)
        self.assertIn('160', prompt)

    @patch('aiohttp.ClientSession.post')
    async def test_generate_multiple_variants(self, mock_post):
        """Тест генерации нескольких вариантов"""
        # Настройка мока
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Variant text'
                }
            }]
        }
        mock_post.return_value.__aenter__.return_value = mock_response

        # Вызов метода
        variants = await self.adapter.generate_multiple_variants(
            product_info='Test product',
            num_variants=2,
            max_length=160
        )

        # Проверки
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0], 'Variant text')
        self.assertEqual(variants[1], 'Variant text')

    async def test_text_truncation(self):
        """Тест обрезки текста до максимальной длины"""
        # Настройка мока
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                'choices': [{
                    'message': {
                        'content': 'A' * 200  # Длинный текст
                    }
                }]
            }
            mock_post.return_value.__aenter__.return_value = mock_response

            # Вызов метода с ограничением
            result = await self.adapter.generate_ad_copy(
                product_info='Test product',
                style='professional',
                max_length=50
            )

            # Проверка, что текст обрезан
            self.assertEqual(len(result), 50)
            self.assertTrue(result.endswith('...'))


if __name__ == '__main__':
    unittest.main()