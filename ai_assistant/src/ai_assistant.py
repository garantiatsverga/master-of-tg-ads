import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import sys
import simdjson as sd
import os

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
    Упрощенная версия без инструментов MCP.
    """
    
    def __init__(self, config_path: str = None):
        """
        Инициализация AI ассистента.
         
        Args:
            config_path: Путь к конфигурационному файлу
        """
        log_application_start()
        
        # Определяем базовый путь
        self.base_dir = Path(__file__).parent.parent
        
        # Если config_path не указан, ищем относительно base_dir
        if config_path is None:
            config_path = str(self.base_dir / 'config.yaml')
        
        # Загрузка конфигурации
        self.config = ConfigManager.load_config(config_path)
        log_module_initialization("ConfigManager")
        
        # Настройка логирования
        log_file_path = str(self.base_dir / self.config.get('system', {}).get('log_file', 'ai_assistant.log'))
        setup_logging(
            log_file=log_file_path,
            log_level=self.config.get('system', {}).get('log_level', 'info'),
            console_output=True
        )
        
        # Проверка и исправление кодировки файла лога
        from ai_assistant.src.observability.logging_setup import safe_read_file, safe_write_file
        if os.path.exists(log_file_path):
            try:
                content = safe_read_file(log_file_path)
                if content:
                    safe_write_file(log_file_path, content, encoding='utf-8')
            except Exception as e:
                print(f"Ошибка при исправлении кодировки файла лога: {e}")
        
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
        """Инициализация специализированных агентов (без инструментов)"""
        try:
            workflow_agents = self.config.get('agents', {}).get('workflow', [])
            
            # Создание MCPServer (упрощенный, без инструментов)
            mcp_server = MCPServer(
                registry=ToolRegistry(),  # Пустой реестр
                retry_policy=SimpleRetryPolicy(),
                cache_policy=InMemoryCachePolicy(),
                security_checker=self.security_checker
            )
            
            info(f"Инициализация {len(workflow_agents)} агентов...", exp=True)
            
            for agent_name in workflow_agents:
                if agent_name == 'prompt_agent':
                    # Используем пути относительно текущей директории
                    rules_path = Path('prompt_engine/telegram_rules.json')
                    templates_path = Path('prompt_engine/prompt_templates.json')
                    
                    # Если файлы в другой директории, ищем их
                    if not rules_path.exists():
                        # Пробуем другие возможные пути
                        possible_paths = [
                            Path('prompt_engine/telegram_rules.json'),
                            Path('/content/master-of-tg-ads/prompt_engine/telegram_rules.json'),
                            Path(__file__).parent.parent / 'prompt_engine' / 'telegram_rules.json',
                            Path.cwd() / 'prompt_engine' / 'telegram_rules.json'
                        ]
                        
                        for path in possible_paths:
                            if path.exists():
                                rules_path = path
                                info(f"Найден файл правил: {rules_path}", exp=True)
                                break
                    
                    if not templates_path.exists():
                        # Пробуем другие возможные пути
                        possible_paths = [
                            Path('prompt_engine/prompt_templates.json'),
                            Path('/content/master-of-tg-ads/prompt_engine/prompt_templates.json'),
                            Path(__file__).parent.parent / 'prompt_engine' / 'prompt_templates.json',
                            Path.cwd() / 'prompt_engine' / 'prompt_templates.json'
                        ]
                        
                        for path in possible_paths:
                            if path.exists():
                                templates_path = path
                                break
                    
                    # Если файла prompt_templates.json нет, создаем минимальный
                    if not templates_path.exists():
                        warning(f"Файл {templates_path} не найден, создаю минимальный шаблон", exp=True)
                        templates_path.parent.mkdir(parents=True, exist_ok=True)
                        minimal_template = {
                            "default_template": {
                                "text_prompt": "Создай рекламный текст для {product}. Аудитория: {audience}. Цель: {goal}. Стиль: {style}",
                                "image_prompt": "Создай баннер для {product}. Аудитория: {audience}. Стиль: яркий, привлекательный"
                            }
                        }
                        with open(templates_path, 'w') as f:
                            import json
                            json.dump(minimal_template, f, indent=2, ensure_ascii=False)
                    
                    if not rules_path.exists():
                        error(f"Файл правил не найден. Проверенные пути: {possible_paths}", exp=True)
                        # Создаем минимальные правила
                        warning("Создаю минимальные правила...", exp=True)
                        minimal_rules = {
                            "version": "1.0",
                            "description": "Минимальные правила для тестирования",
                            "checks": [
                                {"name": "text_length", "max_chars": 160},
                                {"name": "no_profanity", "enabled": True}
                            ]
                        }
                        rules_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(rules_path, 'w') as f:
                            json.dump(minimal_rules, f, indent=2, ensure_ascii=False)
                        info(f"Созданы минимальные правила: {rules_path}", exp=True)
                    
                    with open(rules_path, 'rb') as f:
                        rules = sd.load(f)
                    
                    if templates_path.exists():
                        with open(templates_path, 'rb') as f:
                            templates = sd.load(f)
                    else:
                        templates = {"default_template": {"text_prompt": "", "image_prompt": ""}}
                    
                    self.agents['prompt_agent'] = PromptAgent(
                        mcp_server=mcp_server,
                        rules=rules,
                        templates=templates,
                        security_checker=self.security_checker,
                        metrics_collector=self.metrics_collector
                    )
                    
                elif agent_name == 'copywriter':
                    self.agents['copywriter'] = CopywriterAgent(
                        mcp_server=mcp_server,
                        security_checker=self.security_checker,
                        metrics_collector=self.metrics_collector
                    )
                    
                elif agent_name == 'banner_designer':
                    # Передаем конфигурацию Stable Diffusion
                    sd_config = self.config.get('stable_diffusion', {})
                    
                    # Обновляем конфиг для segmind/tiny-sd
                    sd_config.update({
                        'base_model': "segmind/tiny-sd",
                        'upscale_model': "stabilityai/stable-diffusion-x4-upscaler",
                        'lowres_width': 640,
                        'lowres_height': 360,
                        'hires_width': 1920,
                        'hires_height': 1080,
                        'steps': 20,
                        'upscale_steps': 20,
                        'guidance_scale': 7.5
                    })
                    
                    self.agents['banner_designer'] = BannerDesignerAgent(
                        mcp_server=mcp_server,  # Передаем, но не используется
                        security_checker=self.security_checker,
                        metrics_collector=self.metrics_collector,
                        config=sd_config
                    )
                    
                elif agent_name == 'qa_compliance':
                    # Загружаем правила для QA
                    rules_path = Path('prompt_engine/telegram_rules.json')
                    if not rules_path.exists():
                        # Создаем минимальные правила
                        minimal_rules = {
                            "checks": [
                                {"name": "text_length", "max_chars": 160},
                                {"name": "no_profanity", "enabled": True}
                            ]
                        }
                        with open(rules_path, 'w') as f:
                            import json
                            json.dump(minimal_rules, f, indent=2, ensure_ascii=False)
                    
                    with open(rules_path, 'rb') as f:
                        rules = sd.load(f)
                    
                    self.agents['qa_compliance'] = QAComplianceAgent(
                        mcp_server=mcp_server,  # Передаем, но не используется
                        security_checker=self.security_checker,
                        metrics_collector=self.metrics_collector,
                        rules=rules
                    )
                
                log_module_initialization(f"Agent: {agent_name}")
                success(f"Агент {agent_name} инициализирован", exp=True)
            
            info(f"Загружено {len(self.agents)} специализированных агентов", exp=True)
            
            # Регистрация разрешений для агентов (для совместимости)
            mcp_server.set_agent_permissions("PromptAgent", [])
            mcp_server.set_agent_permissions("CopywriterAgent", [])
            mcp_server.set_agent_permissions("BannerDesignerAgent", [])
            mcp_server.set_agent_permissions("QAComplianceAgent", [])
            
        except Exception as e:
            error(f"Ошибка инициализации агентов: {e}", exp=True)
            import traceback
            traceback.print_exc()
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
            import traceback
            traceback.print_exc()
            
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
        
        # Создаем контекст для конвейера
        context = {
            "product": product_description,
            "product_type": "product",  # Можно извлечь из описания
            "audience": result['target_audience'] or "общая аудитория",
            "goal": "продажи",
            "language": "ru",
            "style": style_preference
        }
        
        # Запускаем конвейер агентов
        try:
            # 1. PromptAgent создает ТЗ
            if 'prompt_agent' in self.agents:
                info("Шаг 1: PromptAgent создает ТЗ", exp=True)
                context = await self.agents['prompt_agent'].handle(context)
                result['components']['specification'] = context
            
            # 2. CopywriterAgent пишет текст
            if 'copywriter' in self.agents:
                info("Шаг 2: CopywriterAgent пишет текст", exp=True)
                context = await self.agents['copywriter'].handle(context)
                result['components']['ad_text'] = context.get('final_advertising_text', '')
            
            # 3. BannerDesignerAgent создает баннер
            if 'banner_designer' in self.agents:
                info("Шаг 3: BannerDesignerAgent создает баннер", exp=True)
                context = await self.agents['banner_designer'].handle(context)
                result['components']['banner_url'] = context.get('banner_url', '')
                result['components']['banner_generated'] = context.get('banner_generated', False)
            
            # 4. QAComplianceAgent проверяет
            if 'qa_compliance' in self.agents:
                info("Шаг 4: QAComplianceAgent проверяет качество", exp=True)
                context = await self.agents['qa_compliance'].handle(context)
                result['components']['qa_status'] = context.get('qa_status', 'UNKNOWN')
                result['components']['qa_report'] = context.get('qa_report', [])
            
            # Сохраняем полный контекст
            result['components']['pipeline_context'] = context
            
        except Exception as e:
            error(f"Ошибка в конвейере агентов: {e}", exp=True)
            import traceback
            traceback.print_exc()
            raise
    
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
        Упрощенная версия без инструментов MCP.
        """
        info("Запуск конвейера создания рекламных материалов", exp=True, textwrapping=True, wrapint=80)
        
        # Создаем упрощенный MCPServer
        mcp_server = MCPServer(
            registry=ToolRegistry(),  # Пустой реестр
            retry_policy=SimpleRetryPolicy(retries=2, delay=0.5),
            cache_policy=InMemoryCachePolicy(),
            security_checker=self.security_checker
        )
        
        # Используем пути относительно текущей директории
        rules_path = Path('prompt_engine/telegram_rules.json')
        templates_path = Path('prompt_engine/prompt_templates.json')
        
        # Проверяем существование файлов
        if not rules_path.exists():
            # Пробуем альтернативные пути
            possible_paths = [
                Path('prompt_engine/telegram_rules.json'),
                Path('/content/master-of-tg-ads/prompt_engine/telegram_rules.json'),
                Path.cwd() / 'prompt_engine' / 'telegram_rules.json',
                Path(__file__).parent.parent / 'prompt_engine' / 'telegram_rules.json'
            ]
            
            found = False
            for path in possible_paths:
                if path.exists():
                    rules_path = path
                    info(f"Найден файл правил: {rules_path}", exp=True)
                    found = True
                    break
            
            if not found:
                # Создаем минимальные правила
                warning("Файл правил не найден, создаю минимальные...", exp=True)
                rules_path = Path.cwd() / 'prompt_engine' / 'telegram_rules.json'
                rules_path.parent.mkdir(parents=True, exist_ok=True)
                
                minimal_rules = {
                    "version": "1.0",
                    "description": "Минимальные правила для тестирования",
                    "checks": [
                        {"name": "text_length", "max_chars": 160},
                        {"name": "no_profanity", "enabled": True}
                    ]
                }
                
                with open(rules_path, 'w') as f:
                    import json
                    json.dump(minimal_rules, f, indent=2, ensure_ascii=False)
        
        if not templates_path.exists():
            # Создаем минимальный шаблон
            warning("Файл шаблонов не найден, создаю минимальный...", exp=True)
            templates_path = Path.cwd() / 'prompt_engine' / 'prompt_templates.json'
            templates_path.parent.mkdir(parents=True, exist_ok=True)
            
            minimal_template = {
                "default_template": {
                    "text_prompt": "Создай рекламный текст для {product}. Аудитория: {audience}. Цель: {goal}",
                    "image_prompt": "Создай баннер для {product}. Аудитория: {audience}"
                }
            }
            
            with open(templates_path, 'w') as f:
                import json
                json.dump(minimal_template, f, indent=2, ensure_ascii=False)
        
        # Загружаем правила и шаблоны
        with open(rules_path, 'rb') as f:
            rules = sd.load(f)
        with open(templates_path, 'rb') as f:
            templates = sd.load(f)
        
        # Конфигурация для BannerDesignerAgent
        sd_config = self.config.get('stable_diffusion', {}).copy()
        sd_config.update({
            'base_model': "segmind/tiny-sd",
            'upscale_model': "stabilityai/stable-diffusion-x4-upscaler",
            'lowres_width': 640,
            'lowres_height': 360,
            'hires_width': 1920,
            'hires_height': 1080,
            'steps': 20,
            'upscale_steps': 20,
            'guidance_scale': 7.5
        })
        
        # Инициализация агентов
        try:
            agents = {
                "architect": PromptAgent(
                    mcp_server=mcp_server,
                    rules=rules,
                    templates=templates,
                    security_checker=self.security_checker,
                    metrics_collector=self.metrics_collector
                ),
                "writer": CopywriterAgent(
                    mcp_server=mcp_server,
                    security_checker=self.security_checker,
                    metrics_collector=self.metrics_collector
                ),
                "designer": BannerDesignerAgent(
                    mcp_server=mcp_server,
                    security_checker=self.security_checker,
                    metrics_collector=self.metrics_collector,
                    config=sd_config
                ),
                "inspector": QAComplianceAgent(
                    mcp_server=mcp_server,
                    security_checker=self.security_checker,
                    metrics_collector=self.metrics_collector,
                    rules=rules
                )
            }
        except Exception as e:
            error(f"Ошибка инициализации агентов: {e}", exp=True)
            raise
        
        try:
            # Шаг 1: Архитектор создает ТЗ
            info("Шаг 1: Архитектор создает ТЗ", exp=True, textwrapping=True, wrapint=80)
            context = await agents["architect"].handle(context)
            
            # Шаг 2: Копирайтер пишет текст
            info("Шаг 2: Копирайтер пишет текст", exp=True, textwrapping=True, wrapint=80)
            context = await agents["writer"].handle(context)
            
            # Шаг 3: Дизайнер рисует баннер
            info("Шаг 3: Дизайнер рисует баннер", exp=True, textwrapping=True, wrapint=80)
            context = await agents["designer"].handle(context)
            
            # Шаг 4: Инспектор выносит вердикт
            info("Шаг 4: Инспектор проверяет качество", exp=True, textwrapping=True, wrapint=80)
            context = await agents["inspector"].handle(context)
            
            # Финальный результат
            success("Конвейер завершен успешно!", exp=True, textwrapping=True, wrapint=80)
            
            # Форматируем результат
            result = {
                "qa_status": context.get("qa_status", "UNKNOWN"),
                "final_advertising_text": context.get("final_advertising_text", ""),
                "banner_url": context.get("banner_url", ""),
                "qa_report": context.get("qa_report", []),
                "pipeline_success": True,
                "components": {
                    "specification": context.get("target_text_prompt", ""),
                    "banner_generated": context.get("banner_generated", False)
                }
            }
            
            return result
            
        except Exception as e:
            error(f"Критический сбой конвейера: {e}", exp=True, textwrapping=True, wrapint=80)
            import traceback
            traceback.print_exc()
            raise


# Пример использования
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
        
        if 'banner_generated' in result.get('components', {}):
            if result['components']['banner_generated']:
                print(f"\nИзображение: сгенерировано успешно")
                print(f"URL: {result['components'].get('banner_url', 'N/A')}")
            else:
                print(f"\nИзображение: не сгенерировано")
        
        if 'qa_status' in result.get('components', {}):
            status = result['components']['qa_status']
            print(f"\nСтатус QA: {status}")
    
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