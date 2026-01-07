import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from ai_assistant.src.storage.postgres import PostgresStorage
from colordebug import debug


@pytest.fixture
def mock_config():
    return {
        "storage": {
            "postgres": {
                "enabled": True,
                "dsn": "postgresql://user:pass@localhost/testdb",
                "min_connections": 1,
                "max_connections": 5,
                "timeout": 30
            }
        }
    }


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    return pool


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_postgres_disabled(mock_config):
    """Тест: PostgresStorage не инициализируется, если отключён."""
    mock_config["storage"]["postgres"]["enabled"] = False

    with patch("ai_assistant.src.storage.postgres.info") as mock_info:
        storage = PostgresStorage(mock_config)
        await storage.connect()

        mock_info.assert_any_call("PostgresStorage отключен в конфигурации", exp=True)
        assert storage.pool is None


@pytest.mark.asyncio
async def test_connect_success(mock_config, mock_pool):
    """Тест: успешное подключение к PostgreSQL."""
    async def mock_create_pool(**kwargs):
        return mock_pool
  
    with patch("ai_assistant.src.storage.postgres.asyncpg.create_pool", side_effect=mock_create_pool) as mock_create_pool_patch, \
         patch("ai_assistant.src.storage.postgres.info") as mock_info, \
         patch("ai_assistant.src.storage.postgres.error") as mock_error, \
         patch("ai_assistant.src.storage.postgres.log_database_operation") as mock_log_db:

        debug(f"Mock pool type: {type(mock_pool)}")
        debug(f"Mock pool: {mock_pool}")
        storage = PostgresStorage(mock_config)
        debug(f"Storage pool before connect: {storage.pool}")
        await storage.connect()
        debug(f"Storage pool after connect: {storage.pool}")

        mock_create_pool_patch.assert_called_once()
        mock_info.assert_called()
        mock_log_db.assert_called()
        assert storage.pool is mock_pool


@pytest.mark.asyncio
async def test_connect_failure(mock_config):
    """Тест: ошибка подключения к PostgreSQL."""
    with patch("ai_assistant.src.storage.postgres.asyncpg.create_pool", side_effect=Exception("Подключение провалено")), \
         patch("ai_assistant.src.storage.postgres.error") as mock_error, \
         patch("ai_assistant.src.storage.postgres.critical") as mock_critical, \
         patch("ai_assistant.src.storage.postgres.log_database_operation") as mock_log_db:

        storage = PostgresStorage(mock_config)
        await storage.connect()

        mock_error.assert_any_call("Ошибка подключения к PostgreSQL", exception=ANY, exp=True)
        mock_log_db.assert_called_with("connect", "system", ANY, False)
        assert storage.pool is None


@pytest.mark.asyncio
async def test_create_tables_success(mock_config, mock_conn):
    """Тест: успешное создание таблицы."""
    with patch("ai_assistant.src.storage.postgres.asyncpg.create_pool") as mock_create_pool, \
         patch("ai_assistant.src.storage.postgres.info") as mock_info, \
         patch("ai_assistant.src.storage.postgres.log_database_operation") as mock_log_db:

        storage = PostgresStorage(mock_config)
        
        # Создаем мок для пула с правильным acquire
        mock_pool = MagicMock()
        
        # Создаем асинхронный контекстный менеджер для acquire
        mock_acquire_context = MagicMock()
        mock_acquire_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_acquire_context.__aexit__ = AsyncMock(return_value=False)
        
        # acquire должен быть обычным методом, возвращающим контекстный менеджер
        mock_pool.acquire.return_value = mock_acquire_context
        mock_conn.execute = AsyncMock()
        
        # Возвращаем мок пула из create_pool
        mock_create_pool.return_value = mock_pool
        storage.pool = mock_pool

        await storage._create_tables()

        # Проверяем, что execute был вызван
        mock_conn.execute.assert_called_once()
        mock_info.assert_any_call("Таблица text_records проверена/создана", exp=True)
        mock_log_db.assert_called_with("create_table", "text_records", ANY, True)


@pytest.mark.asyncio
async def test_save_text_record_success(mock_config, mock_pool):
    """Тест: успешное сохранение текста."""
    with patch("ai_assistant.src.storage.postgres.asyncpg.create_pool", return_value=mock_pool), \
         patch("ai_assistant.src.storage.postgres.debug") as mock_debug, \
         patch("ai_assistant.src.storage.postgres.log_database_operation") as mock_log_db:

        storage = PostgresStorage(mock_config)
        storage.pool = mock_pool
        mock_pool.fetchval = AsyncMock(return_value=123)

        result = await storage.save_text_record(
            text_content="Test ad text",
            version_metadata={"style": "creative"},
            model_name="GigaChat",
            request_id="req_1"
        )

        assert result == 123
        mock_debug.assert_any_call("Текст сохранён в PostgreSQL с ID=123", exp=True)
        mock_log_db.assert_called_with("insert", "text_records", ANY, True)


@pytest.mark.asyncio
async def test_save_text_record_pool_not_connected(mock_config):
    """Тест: ошибка при отсутствии подключения."""
    with patch("ai_assistant.src.storage.postgres.error") as mock_error, \
         patch("ai_assistant.src.storage.postgres.log_database_operation") as mock_log_db:

        storage = PostgresStorage(mock_config)
        # Не вызываем connect → pool = None

        result = await storage.save_text_record("Test", {}, "test", "req_1")

        assert result is None
        mock_error.assert_any_call("PostgresStorage не подключен", exp=True)


@pytest.mark.asyncio
async def test_close_called(mock_config, mock_pool):
    """Тест: закрытие пула подключений."""
    with patch("ai_assistant.src.storage.postgres.asyncpg.create_pool", return_value=mock_pool), \
         patch("ai_assistant.src.storage.postgres.info") as mock_info:

        storage = PostgresStorage(mock_config)
        storage.pool = mock_pool
        await storage.close()

        mock_pool.close.assert_called_once()
        mock_info.assert_any_call("Соединение с PostgreSQL закрыто", exp=True)
