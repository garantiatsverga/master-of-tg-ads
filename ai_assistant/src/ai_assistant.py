import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import sys
import simdjson as sd

# Добавляем пути для импортов
sys.path.append(str(Path(__file__).parent.parent))

from colordebug import info, success, warning, error, debug
from ai_assistant.src.observability.logging_setup import (
    setup_logging, log_application_start, log_module_initialization
)
from ai_assistant.src.config_manager import ConfigManager
from ai_assistant.src.security.security_checker import SecurityChecker
from ai_assistant.src.llm.llm_router import LLMRouter
from ai_assistant.src.observability.metric_collector import MetricsCollector
from ai_assistant.src.storage.postgres import PostgresStorage
from ai_assistant.src.storage.s3 import S3Storage
from MCPServer import MCPServer, ToolRegistry, SimpleRetryPolicy, InMemoryCachePolicy

# Импорты для агентов
from agents.prompt_agent import PromptAgent
from agents.copywriter_agent import CopywriterAgent
from agents.banner_designer_agent import BannerDesignerAgent
from agents.qa_compliance_agent import QAComplianceAgent


class AIAssistant:
    """
    Главный оркестратор AI ассистента для создания рекламных баннеров.
    Управляет всем процессом от идеи до финальной проверки.
    """
    
    def __init__(self, config_path: str = None):
        """
        Инициализация AI ассистента.
         
        Args:
            config_path: Путь к конфигурационному файлу
        """
        log_application_start()
        
        # Загрузка конфигурации
        self.config = ConfigManager.load_config(config_path)
        log_module_initialization("ConfigManager")
        
        # Настройка логирования
        setup_logging(
            log_file=self.config.get('system', {}).get('log_file', 'ai_assistant.log'),
            log_level=self.config.get('system', {}).get('log_level', 'info'),
            console_output=True
        )
        
        # Инициализация компонентов
        self.security_checker = SecurityChecker(self.config)
        log_module_initialization("SecurityChecker")
        
        self.llm_router = LLMRouter(self.config)
        log_module_initialization("LLMRouter")
        
        self.metrics_collector = MetricsCollector()
        log_module_initialization("MetricsCollector")
        
        # Инициализация хранилищ
        self.postgres_storage = PostgresStorage(self.config)
        log_module_initialization("PostgresStorage")
        
        self.s3_storage = S3Storage(self.config)
        log_module_initialization("S3Storage")
        
        # Инициализация агентов
        self.agents = {}
        self._initialize_agents()
        
        info("ИИ-ассистент успешно инициализирован", exp=True)
        info("_"*30, exp=True)
        
        # Подключение к хранилищам
        asyncio.create_task(self._connect_storage())

    
    def _initialize_agents(self):
        """Инициализация специализированных агентов"""
        try:
            workflow_agents = self.config.get('agents', {}).get('workflow', [])
             
            for agent_name in workflow_agents:
                if agent_name == 'prompt_agent':
                    self.agents['prompt_agent'] = PromptAgent(self.config)
                elif agent_name == 'copywriter':
                    self.agents['copywriter'] = CopywriterAgent(self.config)
                elif agent_name == 'banner_designer':
                    self.agents['banner_designer'] = BannerDesignerAgent(self.config)
                elif agent_name == 'qa_compliance':
                    self.agents['qa_compliance'] = QAComplianceAgent(self.config)
                 
                log_module_initialization(f"Agent: {agent_name}")
             
            info(f"Загружено {len(self.agents)} специализированных агентов", exp=True)
             
        except Exception as e:
            error(f"Ошибка инициализации агентов: {e}", exp=True)
            warning("Продолжение в базовом режиме без агентов", exp=True)
            self.agents = {}
        
    
    async def _connect_storage(self):
        """Подключение к хранилищам данных"""
        try:
            # Подключение к PostgreSQL
            if self.postgres_storage.config.get('enabled', False):
                await self.postgres_storage.connect()
                await self.postgres_storage._create_tables()
                success("PostgreSQL хранилище подключено и готово", exp=True)
            
            # Настройка S3
            if self.s3_storage.config.get('enabled', False):
                await self.s3_storage.setup()
                success("S3 хранилище настроено и готово", exp=True)
                
        except Exception as e:
            error(f"Ошибка подключения к хранилищам: {e}", exp=True)
            warning("Продолжение работы без хранилищ", exp=True)
    
    async def process_request(
        self,
        product_description: str,
        target_audience: str = None,
        style_preference: str = "professional",
        include_image: bool = True,
        user_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Основной метод обработки запроса на создание рекламного баннера.
        
        Args:
            product_description: Описание продукта/услуги
            target_audience: Целевая аудитория (опционально)
            style_preference: Предпочтительный стиль (professional, creative, urgent, emotional)
            include_image: Включать ли генерацию изображения
            user_context: Контекст пользователя для проверок безопасности
            
        Returns:
            Словарь с результатами генерации
        """
        request_id = f"req_{int(asyncio.get_event_loop().time())}"
        
        info(f"Начало обработки запроса {request_id}", exp=True)
        debug(f"Продукт: {product_description[:100]}...", exp=True)
        debug(f"Стиль: {style_preference}, Изображение: {include_image}", exp=True)
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 1. Безопасность входных данных
            security_result, security_message = await self.security_checker.check_ad_compliance(
                ad_text=product_description,
                user_context=user_context,
                verbose=False
            )
            
            if not security_result:
                error(f"Запрос {request_id} отклонен по соображениям безопасности", exp=True)
                return {
                    'success': False,
                    'request_id': request_id,
                    'error': security_message,
                    'violation_type': 'INPUT_VALIDATION'
                }
            
            success("Проверка безопасности пройдена", exp=True)
            
            result = {
                'success': True,
                'request_id': request_id,
                'product_description': product_description,
                'style_preference': style_preference,
                'target_audience': target_audience,
                'components': {}
            }
            
            # 2. Использование специализированных агентов или базовой логики
            if self.agents:
                await self._process_with_agents(product_description, style_preference, result)
            else:
                await self._process_basic(product_description, style_preference, include_image, result)
            
            # 3. Финальная проверка на соответствие правилам Telegram
            if 'ad_text' in result['components']:
                final_check, final_message = await self.security_checker.check_ad_compliance(
                    ad_text=result['components']['ad_text'],
                    user_context=user_context,
                    verbose=True
                )
                
                if not final_check:
                    warning(f"Финальная проверка не пройдена: {final_message}", exp=True)
                    result['compliance_check'] = {
                        'passed': False,
                        'message': final_message
                    }
                else:
                    result['compliance_check'] = {
                        'passed': True,
                        'message': "Соответствует правилам Telegram Ads"
                    }
            
            # 4. Сбор метрик
            end_time = asyncio.get_event_loop().time()
            response_time = end_time - start_time
            
            self.metrics_collector.log_query(
                question=product_description[:50],
                intent="banner_generation",
                response_time=response_time,
                success=result['success']
            )
            
            # 5. Логирование результата
            if result['success']:
                success(f"Запрос {request_id} успешно обработан за {response_time:.2f} сек", exp=True)
                result['processing_time'] = f"{response_time:.2f} сек"
                result['metrics'] = self.metrics_collector.get_metrics()
            else:
                error(f"Запрос {request_id} завершен с ошибкой", exp=True)
            
            return result
            
        except Exception as e:
            error(f"Критическая ошибка при обработке запроса {request_id}: {e}", exp=True)
            
            return {
                'success': False,
                'request_id': request_id,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    async def _process_with_agents(
        self,
        product_description: str,
        style_preference: str,
        result: Dict[str, Any]
    ):
        """Обработка запроса с использованием специализированных агентов"""
        info("Использование специализированных агентов", exp=True)
        
        # Агент промптов
        if 'prompt_agent' in self.agents:
            prompt_result = await self.agents['prompt_agent'].generate_specification(
                product_description=product_description,
                style=style_preference
            )
            result['components']['specification'] = prompt_result
        
        # Копирайтер агент
        if 'copywriter' in self.agents:
            copy_result = await self.agents['copywriter'].generate_ad_copy(
                product_description=product_description,
                style=style_preference
            )
            result['components']['ad_text'] = copy_result
        
        # Дизайнер агент
        if 'banner_designer' in self.agents:
            design_result = await self.agents['banner_designer'].design_banner(
                product_description=product_description,
                style=style_preference
            )
            result['components']['design'] = design_result
        
        # Агент проверки качества
        if 'qa_compliance' in self.agents and 'ad_text' in result['components']:
            qa_result = await self.agents['qa_compliance'].check_compliance(
                ad_text=result['components']['ad_text'],
                design_data=result['components'].get('design')
            )
            result['components']['qa_check'] = qa_result
        
        # Сохранение текста в PostgreSQL
        if 'ad_text' in result['components']:
            # Экранирование данных для предотвращения SQL-инъекций
            text_content = result['components']['ad_text'].replace("'", "''")
            request_id = result['request_id'].replace("'", "''")
            style_preference_safe = style_preference.replace("'", "''")
            
            text_id = await self.postgres_storage.save_text_record(
                text_content=text_content,
                version_metadata={
                    'request_id': request_id,
                    'style': style_preference_safe,
                    'model': 'text_llm'
                },
                model_name='text_llm',
                request_id=request_id
            )
            if text_id:
                result['components']['text_storage_id'] = text_id
                result['components']['text_storage'] = 'postgres'
                success("Текст сохранен в PostgreSQL", exp=True)
    
    async def _process_basic(
        self,
        product_description: str,
        style_preference: str,
        include_image: bool,
        result: Dict[str, Any]
    ):
        """Базовая обработка запроса (без специализированных агентов)"""
        info("Использование базовой логики", exp=True)
        
        # Генерация текста через LLM-роутер
        try:
            ad_text = await self.llm_router.generate_banner_text(
                product_description=product_description,
                style=style_preference
            )
            result['components']['ad_text'] = ad_text
            success("Текст баннера сгенерирован", exp=True)
            
            # Валидация промпта для изображения
            if include_image:
                prompt_valid, prompt_message = await self.security_checker.validate_image_prompt(
                    sd_prompt=product_description,
                    verbose=True
                )
                
                if prompt_valid:
                    # Генерация изображения
                    try:
                        image = await self.llm_router.generate_banner_image(
                            image_prompt=product_description
                        )
                        result['components']['image'] = image
                        result['components']['image_generated'] = True
                        success("Изображение баннера сгенерировано", exp=True)
                    except Exception as e:
                        warning(f"Ошибка генерации изображения: {e}", exp=True)
                        result['components']['image_generated'] = False
                        result['components']['image_error'] = str(e)
                else:
                    warning(f"Промпт не прошел валидацию: {prompt_message}", exp=True)
                    result['components']['image_generated'] = False
                    result['components']['image_validation_failed'] = prompt_message
            else:
                result['components']['image_generated'] = False
            
            # Сохранение сгенерированного изображения в S3
            if include_image and 'image' in result['components']:
                image_url = await self.s3_storage.upload_image(result['components']['image'])
                if image_url:
                    result['components']['image_url'] = image_url
                    result['components']['image_storage'] = 's3'
                    success("Изображение сохранено в S3", exp=True)
                 
        except Exception as e:
            error(f"Ошибка при генерации контента: {e}", exp=True)
            raise
    
    async def generate_text_only(
        self,
        product_description: str,
        style: str = "professional",
        num_variants: int = 1
    ) -> Dict[str, Any]:
        """
        Генерация только текстовых вариантов.
        
        Args:
            product_description: Описание продукта
            style: Стиль текста
            num_variants: Количество вариантов
            
        Returns:
            Словарь с текстовыми вариантами
        """
        info(f"Генерация текстовых вариантов (стиль: {style})", exp=True)
        
        try:
            # Используем базовый адаптер для множественной генерации
            from ai_assistant.src.llm.text_llm_adapter import TextLLMAdapter
            adapter = TextLLMAdapter(self.config)
            
            variants = await adapter.generate_multiple_variants(
                product_info=product_description,
                num_variants=num_variants
            )
            
            # Проверка каждого варианта
            validated_variants = []
            for i, variant in enumerate(variants):
                check_result, check_message = await self.security_checker.check_ad_compliance(
                    ad_text=variant,
                    verbose=False
                )
                
                if check_result:
                    validated_variants.append({
                        'text': variant,
                        'length': len(variant),
                        'status': 'approved'
                    })
                else:
                    validated_variants.append({
                        'text': variant,
                        'length': len(variant),
                        'status': 'rejected',
                        'reason': check_message
                    })
            
            result = {
                'success': True,
                'total_generated': len(variants),
                'approved': len([v for v in validated_variants if v['status'] == 'approved']),
                'variants': validated_variants
            }
            
            success(f"Сгенерировано {len(variants)} текстовых вариантов", exp=True)
            return result
            
        except Exception as e:
            error(f"Ошибка генерации текстовых вариантов: {e}", exp=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Получение текущих метрик производительности.
        
        Returns:
            Словарь с метриками
        """
        return self.metrics_collector.get_metrics()
    
    def get_config(self) -> Dict[str, Any]:
        """
        Получение текущей конфигурации.
        
        Returns:
            Текущая конфигурация
        """
        return self.config.copy()
    
    def reset_metrics(self) -> None:
        """
        Сброс метрик производительности.
        """
        self.metrics_collector.reset_metrics()
        info("Метрики сброшены", exp=True)

    async def run_advertising_pipeline(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запуск конвейера создания рекламных материалов.
        
        Args:
            context: Контекст с входными данными для конвейера
            
        Returns:
            Словарь с результатами работы конвейера
        """
        info("Запуск конвейера создания рекламных материалов", exp=True, textwrapping=True, wrapint=80)
        
        # Инициализация MCPServer
        registry = ToolRegistry()
        retry_policy = SimpleRetryPolicy()
        cache_policy = InMemoryCachePolicy()
        mcp_server = MCPServer(
            registry=registry,
            retry_policy=retry_policy,
            cache_policy=cache_policy,
            security_checker=self.security_checker
        )
        
        # Загрузка правил и шаблонов
        with open('prompt_engine/telegram_rules.json', 'rb') as f:
            rules = sd.load(f)
        with open('prompt_engine/prompt_templates.json', 'rb') as f:
            templates = sd.load(f)
        
        # Инициализация агентов
        agents = {
            "architect": PromptAgent(mcp_server=mcp_server, rules=rules, templates=templates),
            "writer": CopywriterAgent(mcp_server=mcp_server),
            "designer": BannerDesignerAgent(mcp_server=mcp_server),
            "inspector": QAComplianceAgent(mcp_server=mcp_server)
        }

        # Регистрация разрешений для агентов
        mcp_server.set_agent_permissions("CopywriterAgent", ["text.generate"])
        mcp_server.set_agent_permissions("BannerDesignerAgent", ["image.generate"])
        mcp_server.set_agent_permissions("QAComplianceAgent", ["compliance.check"])
        mcp_server.set_agent_permissions("PromptAgent", [])
        
        try:
            # Шаг 1: Архитектор создает ТЗ
            context = await agents["architect"].handle(context)
            
            # Шаг 2: Копирайтер пишет текст
            context = await agents["writer"].handle(context)
            
            # Шаг 3: Дизайнер рисует баннер
            context = await agents["designer"].handle(context)
            
            # Шаг 4: Инспектор выносит вердикт
            context = await agents["inspector"].handle(context)
            
            # Финальный результат
            success("Конвейер завершен успешно!", exp=True, textwrapping=True, wrapint=80)
            return context
            
        except Exception as e:
            error(f"Критический сбой конвейера: {e}", exp=True, textwrapping=True, wrapint=80)
            raise


async def main_example():
    """Пример использования ИИ-ассистента"""
    # Инициализация ассистента
    assistant = AIAssistant()
    
    # Пример продукта
    product_desc = "Новый курс по машинному обучению для начинающих. Включает практические задания, видеоуроки и сертификат."
    
    # Обработка запроса
    result = await assistant.process_request(
        product_description=product_desc,
        style_preference="professional",
        include_image=True
    )
    
    # Вывод результатов
    if result['success']:
        print(f"\nЗапрос {result['request_id']} выполнен успешно!")
        print(f"Время обработки: {result.get('processing_time', 'N/A')}")
        
        if 'ad_text' in result.get('components', {}):
            print(f"\nТекст баннера:")
            print(f"{result['components']['ad_text']}")
        
        if 'image_generated' in result.get('components', {}):
            if result['components']['image_generated']:
                print(f"\nИзображение: сгенерировано успешно")
            else:
                print(f"\nИзображение: не сгенерировано")
        
        if 'compliance_check' in result:
            status = "ДА" if result['compliance_check']['passed'] else "НЕТ"
            print(f"\n{status} Проверка на соответствие: {result['compliance_check']['message']}")
    
    else:
        print(f"\nОшибка: {result.get('error', 'Unknown error')}")
    
    # Показать метрики
    metrics = assistant.get_metrics()
    print(f"\nМетрики:")
    print(f"Всего запросов: {metrics.get('total_queries', 0)}")
    print(f"Успешных: {metrics.get('successful_responses', 0)}")
    print(f"Среднее время: {metrics.get('avg_response_time', 0):.2f} сек")


if __name__ == "__main__":
    # Запуск примера
    asyncio.run(main_example())