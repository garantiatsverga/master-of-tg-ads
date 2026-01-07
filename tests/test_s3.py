import asyncio
import pytest
import unittest
from unittest.mock import Mock, AsyncMock, patch, ANY
from ai_assistant.src.storage.s3 import S3Storage
from PIL import Image, ImageDraw


@pytest.fixture
def mock_config():
    return {
        "storage": {
            "s3": {
                "enabled": True,
                "access_key": "test_key",
                "secret_key": "test_secret",
                "endpoint_url": "https://storage.test.local",
                "region": "test-region",
                "bucket_name": "test-bucket"
            }
        }
    }


@pytest.fixture
def mock_s3_client():
    return Mock()


@pytest.fixture
def sample_image():
    img = Image.new("RGB", (1920, 1080), color="blue")
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Test Banner", fill="white")
    return img


@pytest.mark.asyncio
async def test_s3_disabled(mock_config):
    """Тест: S3Storage отключён."""
    mock_config["storage"]["s3"]["enabled"] = False

    with patch("ai_assistant.src.storage.s3.info") as mock_info:
        storage = S3Storage(mock_config)

        assert storage.s3_client is None
        mock_info.assert_any_call("S3Storage отключен в конфигурации", exp=True)


@pytest.mark.asyncio
async def test_setup_bucket_exists(mock_config, mock_s3_client):
    """Тест: бакет уже существует."""
    mock_s3_client.head_bucket = Mock()
    mock_s3_client.create_bucket = Mock()

    with patch("boto3.session.Session.client", return_value=mock_s3_client), \
         patch("ai_assistant.src.storage.s3.info") as mock_info, \
         patch("ai_assistant.src.storage.s3.log_api_request") as mock_log_api:

        storage = S3Storage(mock_config)
        await storage.setup()

        mock_s3_client.head_bucket.assert_called_once()
        mock_info.assert_any_call("Бакет 'test-bucket' уже существует", exp=True)
        mock_log_api.assert_called()


@pytest.mark.asyncio
async def test_setup_bucket_created(mock_config, mock_s3_client):
    """Тест: бакет создан."""
    mock_s3_client.head_bucket.side_effect = Exception("Not found")
    mock_s3_client.create_bucket = Mock()

    with patch("boto3.session.Session.client", return_value=mock_s3_client), \
         patch("ai_assistant.src.storage.s3.info") as mock_info, \
         patch("ai_assistant.src.storage.s3.log_api_request") as mock_log_api:

        storage = S3Storage(mock_config)
        await storage.setup()

        mock_s3_client.create_bucket.assert_called_once()
        mock_info.assert_any_call("Бакет 'test-bucket' создан", exp=True)
        mock_log_api.assert_called()


@pytest.mark.asyncio
async def test_setup_failure(mock_config):
    """Тест: ошибка при создании бакета."""
    with patch("boto3.session.Session.client", side_effect=Exception("Инициализация клиента провалена")), \
         patch("ai_assistant.src.storage.s3.error") as mock_error, \
         patch("ai_assistant.src.storage.s3.critical") as mock_critical, \
         patch("ai_assistant.src.storage.s3.log_api_request") as mock_log_api, \
         patch("ai_assistant.src.storage.s3.info"):

        storage = S3Storage(mock_config)
        await storage.setup()

        mock_error.assert_any_call("Ошибка настройки S3 бакета", exception=ANY, exp=True)
        mock_critical.assert_any_call(unittest.mock.ANY, exp=True)
        mock_log_api.assert_called()


@pytest.mark.asyncio
async def test_upload_image_success(mock_config, mock_s3_client, sample_image):
    """Тест: успешная загрузка изображения."""
    mock_s3_client.put_object = Mock()

    with patch("boto3.session.Session.client", return_value=mock_s3_client), \
         patch("ai_assistant.src.storage.s3.info", create=True) as mock_info, \
         patch("ai_assistant.src.storage.s3.error", create=True) as mock_error, \
         patch("ai_assistant.src.storage.s3.log_api_request") as mock_log_api, \
         patch("asyncio.get_event_loop") as mock_loop, \
         patch("ai_assistant.src.storage.s3.debug") as mock_debug:

        storage = S3Storage(mock_config)

        # Мокаем run_in_executor
        mock_loop.return_value.run_in_executor = AsyncMock()

        # Мокаем метод _upload_to_s3, чтобы он не вызывал реальную загрузку
        storage._upload_to_s3 = Mock()

        result = await storage.upload_image(sample_image, format="PNG", prefix="test")

        assert result is not None
        assert result.startswith("s3://test-bucket/test/")
        mock_log_api.assert_called_with("PUT", ANY, 200, unittest.mock.ANY)
        mock_info.assert_any_call("S3Storage инициализирован для бакета: test-bucket", exp=True)
        assert mock_error.call_count == 0


@pytest.mark.asyncio
async def test_upload_image_failure(mock_config, mock_s3_client, sample_image):
    """Тест: ошибка при загрузке изображения."""
    mock_s3_client.put_object = Mock(side_effect=Exception("Upload failed"))

    with patch("boto3.session.Session.client", return_value=mock_s3_client), \
         patch("asyncio.get_event_loop") as mock_loop, \
         patch("ai_assistant.src.storage.s3.error") as mock_error, \
         patch("ai_assistant.src.storage.s3.log_api_request") as mock_log_api:

        storage = S3Storage(mock_config)
        mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("Upload failed"))

        result = await storage.upload_image(sample_image)

        assert result is None
        mock_error.assert_any_call("Ошибка загрузки изображения в S3", exception=ANY, exp=True)
        mock_log_api.assert_called_with("PUT", ANY, 500, ANY)
