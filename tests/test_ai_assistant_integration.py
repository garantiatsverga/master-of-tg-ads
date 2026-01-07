import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
import sys
from pathlib import Path

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from ai_assistant.src.ai_assistant import AIAssistant


class TestAIAssistantIntegration(unittest.TestCase):
    """Интеграционные тесты для AIAssistant"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        # Создаем минимальную конфигурацию для тестов
        self.config = {
            'system': {
                'debug': False,
                'log_level': 'info'
            },
            'agents': {
                'workflow': []  # Без агентов для тестов
            },
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
            },
            'telegram_ads': {
                'specifications': {
                    'max_text_length': 160
                },
                'rule_files': {
                    'telegram_rules': './prompt_engine/telegram_rules.json',
                    'banned_patterns': './prompt_engine/banned_patterns.json'
                }
            }
        }

    @patch('ai_assistant.src.security.security_checker.SecurityChecker.check_ad_compliance')
    @patch('ai_assistant.src.llm.llm_router.LLMRouter.generate_banner_text')
    @patch('ai_assistant.src.security.security_checker.SecurityChecker.validate_image_prompt')
    @patch('ai_assistant.src.llm.llm_router.LLMRouter.generate_banner_image')
    @patch('ai_assistant.src.storage.postgres.PostgresStorage.save_text_record')
    @patch('ai_assistant.src.storage.s3.S3Storage.upload_image')
    async def test_full_processing_flow(self, mock_upload_image, mock_save_text, mock_gen_image, mock_validate_prompt, mock_gen_text, mock_security):
        """Интеграционный тест полного процесса обработки запроса"""
        # Настройка моков
        mock_security.return_value = (True, "Security check passed")
        mock_gen_text.return_value = "Test advertisement text"
        mock_validate_prompt.return_value = (True, "Prompt validated")
        mock_gen_image.return_value = MagicMock(spec=Image.Image)
        mock_save_text.return_value = 123
        mock_upload_image.return_value = "s3://bucket/images/test.png"

        # Создание ассистента
        assistant = AIAssistant()
        
        # Вызов основного метода
        result = await assistant.process_request(
            product_description="Test product for advertising",
            style_preference="professional",
            include_image=True
        )

        # Проверки
        self.assertTrue(result['success'])
        self.assertIn('request_id', result)
        self.assertIn('components', result)
        self.assertIn('ad_text', result['components'])
        self.assertEqual(result['components']['ad_text'], "Test advertisement text 🚀")
        self.assertIn('image', result['components'])
        self.assertTrue(result['components']['image_generated'])
        self.assertIn('image_url', result['components'])
        self.assertEqual(result['components']['image_url'], "s3://bucket/images/test.png")
        self.assertIn('image_storage', result['components'])
        self.assertEqual(result['components']['image_storage'], 's3')
        self.assertIn('text_storage_id', result['components'])
        self.assertEqual(result['components']['text_storage_id'], 123)
        self.assertIn('text_storage', result['components'])
        self.assertEqual(result['components']['text_storage'], 'postgres')
        self.assertIn('compliance_check', result)
        self.assertTrue(result['compliance_check']['passed'])
        self.assertIn('processing_time', result)
        self.assertIn('metrics', result)
        
        # Проверка вызовов хранилищ
        mock_save_text.assert_awaited_once()
        mock_upload_image.assert_awaited_once()

    @patch('ai_assistant.src.security.security_checker.SecurityChecker.check_ad_compliance')
    @patch('ai_assistant.src.llm.llm_router.LLMRouter.generate_banner_text')
    async def test_text_only_processing(self, mock_gen_text, mock_security):
        """Интеграционный тест обработки только текста"""
        # Настройка моков
        mock_security.return_value = (True, "Security check passed")
        mock_gen_text.return_value = "Professional ad text for product"

        # Создание ассистента
        assistant = AIAssistant()
        
        # Вызов метода
        result = await assistant.process_request(
            product_description="Test product",
            style_preference="professional",
            include_image=False
        )

        # Проверки
        self.assertTrue(result['success'])
        self.assertIn('ad_text', result['components'])
        self.assertEqual(result['components']['ad_text'], "Professional ad text for product")
        self.assertFalse(result['components']['image_generated'])

    @patch('ai_assistant.src.security.security_checker.SecurityChecker.check_ad_compliance')
    async def test_security_violation(self, mock_security):
        """Тест обработки нарушения безопасности"""
        # Настройка мока с нарушением
        mock_security.return_value = (False, "Contains banned words")

        # Создание ассистента
        assistant = AIAssistant()
        
        # Вызов метода
        result = await assistant.process_request(
            product_description="Bad product with banned content",
            style_preference="professional"
        )

        # Проверки
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], "Contains banned words")
        self.assertEqual(result['violation_type'], 'INPUT_VALIDATION')

    @patch('ai_assistant.src.security.security_checker.SecurityChecker.check_ad_compliance')
    @patch('ai_assistant.src.llm.llm_router.LLMRouter.generate_banner_text')
    @patch('ai_assistant.src.security.security_checker.SecurityChecker.validate_image_prompt')
    async def test_image_validation_failure(self, mock_validate_prompt, mock_gen_text, mock_security):
        """Тест неудачной валидации промпта для изображения"""
        # Настройка моков
        mock_security.return_value = (True, "Security check passed")
        mock_gen_text.return_value = "Test ad text"
        mock_validate_prompt.return_value = (False, "Prompt contains inappropriate content")

        # Создание ассистента
        assistant = AIAssistant()
        
        # Вызов метода
        result = await assistant.process_request(
            product_description="Test product",
            style_preference="professional",
            include_image=True
        )

        # Проверки
        self.assertTrue(result['success'])
        self.assertIn('ad_text', result['components'])
        self.assertFalse(result['components']['image_generated'])
        self.assertIn('image_validation_failed', result['components'])

    @patch('ai_assistant.src.security.security_checker.SecurityChecker.check_ad_compliance')
    @patch('ai_assistant.src.llm.text_llm_adapter.TextLLMAdapter.generate_multiple_variants')
    async def test_generate_text_only(self, mock_gen_variants, mock_security):
        """Тест генерации только текстовых вариантов"""
        # Настройка моков
        mock_security.return_value = (True, "Security check passed")
        mock_gen_variants.return_value = [
            "Variant 1: Great product!",
            "Variant 2: Amazing offer!",
            "Variant 3: Don't miss this!"
        ]

        # Создание ассистента
        assistant = AIAssistant()
        
        # Вызов метода
        result = await assistant.generate_text_only(
            product_description="Test product",
            style="professional",
            num_variants=3
        )

        # Проверки
        self.assertTrue(result['success'])
        self.assertEqual(result['total_generated'], 3)
        self.assertEqual(result['approved'], 3)
        self.assertEqual(len(result['variants']), 3)
        self.assertEqual(result['variants'][0]['status'], 'approved')


class TestAIAssistantE2E(unittest.TestCase):
    """E2E тесты для AIAssistant"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.config = {
            'system': {
                'debug': False,
                'log_level': 'info'
            },
            'agents': {
                'workflow': []
            },
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
            },
            'telegram_ads': {
                'specifications': {
                    'max_text_length': 160
                },
                'rule_files': {
                    'telegram_rules': './prompt_engine/telegram_rules.json',
                    'banned_patterns': './prompt_engine/banned_patterns.json'
                }
            }
        }

    @patch('ai_assistant.src.security.security_checker.SecurityChecker.check_ad_compliance')
    @patch('ai_assistant.src.llm.llm_router.LLMRouter.generate_banner_text')
    @patch('ai_assistant.src.security.security_checker.SecurityChecker.validate_image_prompt')
    @patch('ai_assistant.src.llm.llm_router.LLMRouter.generate_banner_image')
    @patch('ai_assistant.src.storage.postgres.PostgresStorage.save_text_record')
    @patch('ai_assistant.src.storage.s3.S3Storage.upload_image')
    async def test_complete_banner_generation_e2e(self, mock_upload_image, mock_save_text, mock_gen_image, mock_validate_prompt, mock_gen_text, mock_security):
        """E2E тест полной генерации баннера"""
        # Настройка моков
        mock_security.return_value = (True, "Security check passed")
        mock_gen_text.return_value = "New AI Course! Learn machine learning from scratch. Limited offer!"
        mock_validate_prompt.return_value = (True, "Prompt validated")
        mock_save_text.return_value = 456
        mock_upload_image.return_value = "s3://bucket/banners/course.png"
        
        # Создаем mock изображения
        mock_image = MagicMock(spec=Image.Image)
        mock_image.size = (1920, 1080)
        mock_gen_image.return_value = mock_image

        # Создание ассистента
        assistant = AIAssistant()
        
        # Вызов основного метода
        result = await assistant.process_request(
            product_description="Online course about artificial intelligence and machine learning for beginners",
            style_preference="creative",
            include_image=True,
            target_audience="students and professionals"
        )

        # Проверки
        self.assertTrue(result['success'])
        self.assertIn('request_id', result)
        self.assertIn('product_description', result)
        self.assertIn('style_preference', result)
        self.assertIn('target_audience', result)
        self.assertIn('components', result)
        
        # Проверка компонентов
        components = result['components']
        self.assertIn('ad_text', components)
        self.assertIn('image', components)
        self.assertTrue(components['image_generated'])
        self.assertIn('image_url', components)
        self.assertEqual(components['image_url'], "s3://bucket/banners/course.png")
        self.assertIn('image_storage', components)
        self.assertEqual(components['image_storage'], 's3')
        self.assertIn('text_storage_id', components)
        self.assertEqual(components['text_storage_id'], 456)
        self.assertIn('text_storage', components)
        self.assertEqual(components['text_storage'], 'postgres')
        
        # Проверка вызовов хранилищ
        mock_save_text.assert_awaited_once()
        mock_upload_image.assert_awaited_once()
        
        # Проверка текста
        ad_text = components['ad_text']
        self.assertIsInstance(ad_text, str)
        self.assertGreater(len(ad_text), 0)
        self.assertLessEqual(len(ad_text), 160)  # Максимальная длина для Telegram
        
        # Проверка изображения
        self.assertIsInstance(components['image'], Image.Image)
        self.assertEqual(components['image'].size, (1920, 1080))
        
        # Проверка соответствия
        self.assertIn('compliance_check', result)
        self.assertTrue(result['compliance_check']['passed'])
        
        # Проверка метрик
        self.assertIn('processing_time', result)
        self.assertIn('metrics', result)
        
        metrics = result['metrics']
        self.assertIn('total_queries', metrics)
        self.assertIn('successful_responses', metrics)
        self.assertIn('avg_response_time', metrics)
        self.assertIn('success_rate', metrics)
        
        # Проверка, что метрики обновлены
        self.assertEqual(metrics['total_queries'], 1)
        self.assertEqual(metrics['successful_responses'], 1)
        self.assertGreater(metrics['success_rate'], 0)

    @patch('ai_assistant.src.security.security_checker.SecurityChecker.check_ad_compliance')
    @patch('ai_assistant.src.llm.llm_router.LLMRouter.generate_banner_text')
    async def test_error_handling_e2e(self, mock_gen_text, mock_security):
        """E2E тест обработки ошибок"""
        # Настройка мока с ошибкой
        mock_security.return_value = (True, "Security check passed")
        mock_gen_text.side_effect = Exception("LLM service unavailable")

        # Создание ассистента
        assistant = AIAssistant()
        
        # Вызов метода
        result = await assistant.process_request(
            product_description="Test product",
            style_preference="professional"
        )

        # Проверки
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('error_type', result)
        self.assertEqual(result['error_type'], 'Exception')

    async def test_metrics_collection(self):
        """Тест сбора метрик"""
        # Создание ассистента
        assistant = AIAssistant()
        
        # Проверка начальных метрик
        initial_metrics = assistant.get_metrics()
        self.assertEqual(initial_metrics['total_queries'], 0)
        self.assertEqual(initial_metrics['successful_responses'], 0)
        
        # Сброс метрик
        assistant.reset_metrics()
        reset_metrics = assistant.get_metrics()
        self.assertEqual(reset_metrics['total_queries'], 0)


if __name__ == '__main__':
    unittest.main()