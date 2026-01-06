import asyncio
import asyncpg
from typing import Optional, Dict, Any
from ai_assistant.src.config_manager import ConfigManager
from ai_assistant.src.observability.logging_setup import (
    log_database_operation,
    log_configuration
)
from colordebug import (
    info, error, debug, critical,
    alog_function_call, alog_execution_time,
    atimer
)


class PostgresStorage:
    """
    Асинхронное хранилище для сохранения текстовых результатов в PostgreSQL.
    Полностью интегрировано с системой наблюдаемости.
    """

    def __init__(self, config: Dict[str, Any] = None):
        if not config:
            config = ConfigManager.load_config()
        
        self.config = config.get('storage', {}).get('postgres', {})
        self.pool = None
        
        if not self.config.get('enabled', False):
            info("PostgresStorage отключен в конфигурации", exp=True)

    @alog_function_call(exp=True)
    @alog_execution_time(exp=True)
    async def connect(self):
        """Подключение к PostgreSQL с автоматическим созданием таблицы."""
        debug("Вызвано подключение")
        if not self.config.get('enabled', False):
            debug("PostgresStorage отключено")
            return

        start_time = asyncio.get_event_loop().time()
        success_flag = False
        try:
            dsn_redacted = self.config['dsn'].split('@')[-1] if '@' in self.config['dsn'] else '***REDACTED***'
            info(f"Подключение к PostgreSQL: {dsn_redacted}", exp=True)

            self.pool = await asyncpg.create_pool(
                dsn=self.config['dsn'],
                min_size=self.config.get('min_connections', 1),
                max_size=self.config.get('max_connections', 10),
                command_timeout=self.config.get('timeout', 60),
            )
            debug(f"Pool created: {self.pool}")

            duration = asyncio.get_event_loop().time() - start_time
            log_database_operation("connect", "system", duration, True)
            info("Подключено к PostgreSQL", exp=True)

            success_flag = True
        except Exception as e:
            debug(f"Исключение в подключении: {e}")
            duration = asyncio.get_event_loop().time() - start_time
            log_database_operation("connect", "system", duration, False)
            error("Ошибка подключения к PostgreSQL", exception=e, exp=True)
            self.pool = None
        finally:
            if not success_flag:
                self.pool = None

    @alog_execution_time(exp=True)
    async def _create_tables(self):
        """Создание таблицы text_records, если не существует"""
        debug(f"_create_tables вызвано")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS text_records (
            id SERIAL PRIMARY KEY,
            text_content TEXT NOT NULL,
            version_metadata JSONB DEFAULT '{}',
            model_name VARCHAR(100),
            request_id VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW()
        );
        """
        start_time = asyncio.get_event_loop().time()
        try:
            if self.pool is not None:
                debug(f"Pool не None, получение соединения")
                async with self.pool.acquire() as conn:
                    debug(f"Подключено, обрабатываем запрос")
                    await conn.execute(create_table_query)
                    debug(f"Запрос обработан")
                duration = asyncio.get_event_loop().time() - start_time
                log_database_operation("create_table", "text_records", duration, True)
                info("Таблица text_records проверена/создана", exp=True)
            else:
                debug(f"Pool None")
                error("Пул соединений не инициализирован", exp=True)
        except Exception as e:
            debug(f"Ошибка в _create_tables: {e}")
            duration = asyncio.get_event_loop().time() - start_time
            log_database_operation("create_table", "text_records", duration, False)
            error("Ошибка при создании таблицы text_records", exception=e, exp=True)
            raise

    @alog_function_call(exp=True)
    @alog_execution_time(exp=True)
    async def save_text_record(
        self,
        text_content: str,
        version_metadata: Dict[str, Any] = None,
        model_name: str = None,
        request_id: str = None
    ) -> Optional[int]:
        """
        Сохраняет текст и метаданные в PostgreSQL.
        """
        if not self.pool:
            error("PostgresStorage не подключен", exp=True)
            return None

        start_time = asyncio.get_event_loop().time()
        try:
            query = """
            INSERT INTO text_records
                (text_content, version_metadata, model_name, request_id)
            VALUES
                ($1, $2, $3, $4)
            RETURNING id;
            """
            debug(f"Выполнение запроса: {query}")
            debug(f"Параметры запроса: text_content={text_content}, version_metadata={version_metadata}, model_name={model_name}, request_id={request_id}")

            result = await self.pool.fetchval(
                query,
                text_content,
                version_metadata or {},
                model_name,
                request_id
            )
            debug(f"Query result: {result}")

            duration = asyncio.get_event_loop().time() - start_time
            log_database_operation("insert", "text_records", duration, True)
            debug(f"Текст сохранён в PostgreSQL с ID={result}", exp=True)
            return result

        except Exception as e:
            debug(f"Exception in save_text_record: {e}")
            duration = asyncio.get_event_loop().time() - start_time
            log_database_operation("insert", "text_records", duration, False)
            error("Ошибка при сохранении текста в PostgreSQL", exception=e, exp=True)
            return None

    async def close(self):
        """Закрытие пула подключений."""
        if self.pool:
            await self.pool.close()
            info("Соединение с PostgreSQL закрыто", exp=True)

    async def health_check(self) -> bool:
        """Проверка доступности БД."""
        if not self.pool:
            return False
        try:
            await self.pool.fetchval("SELECT 1")
            return True
        except Exception as e:
            error("Проверка здоровья PostgreSQL провалена", exception=e, exp=False)
            return False
