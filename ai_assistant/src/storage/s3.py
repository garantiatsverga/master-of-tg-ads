import asyncio
import boto3
import uuid
from io import BytesIO
from typing import Optional, Dict, Any
from ai_assistant.src.config_manager import ConfigManager
from ai_assistant.src.observability.logging_setup import (
    log_api_request,
    sanitize_for_logging
)
from colordebug import (
    info, error, debug, critical,
    alog_function_call, alog_execution_time,
    atimer
)
from PIL import Image


class S3Storage:
    """
    Асинхронный интерфейс для загрузки изображений в S3.
    Полностью интегрирован с системой наблюдаемости.
    """

    def __init__(self, config: Dict[str, Any] = None):
        if not config:
            config = ConfigManager.load_config()
         
        self.config = config.get('storage', {}).get('s3', {})
        self.s3_client = None
         
        if not self.config.get('enabled', False):
            info("S3Storage отключен в конфигурации", exp=True)
            return
         
        self.bucket_name = self.config['bucket_name']
        self.endpoint_url = self.config.get('endpoint_url')

        try:
            session = boto3.session.Session(
                aws_access_key_id=self.config['access_key'],
                aws_secret_access_key=self.config['secret_key'],
                region_name=self.config.get('region', 'ru-central1')
            )
            self.s3_client = session.client('s3', endpoint_url=self.endpoint_url)
            
            info(f"S3Storage инициализирован для бакета: {self.bucket_name}", exp=True)
        except Exception as e:
            error(f"Ошибка инициализации S3Storage: {e}", exp=True)
            self.s3_client = None

    @alog_function_call(exp=True)
    @alog_execution_time(exp=True)
    async def setup(self):
        """Проверка и создание бакета."""
        if not self.config.get('enabled', False):
            return

        start_time = asyncio.get_event_loop().time()
        try:
            await asyncio.get_event_loop().run_in_executor(None, self._check_or_create_bucket)
            duration = asyncio.get_event_loop().time() - start_time
            log_api_request("S3", f"setup bucket {self.bucket_name}", 200, duration)
        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            log_api_request("S3", f"setup bucket {self.bucket_name}", 500, duration)
            error("Ошибка настройки S3 бакета", exception=e, exp=True)
            critical(f"Критическая ошибка S3: {e}", exp=True)

    def _check_or_create_bucket(self):
        """Синхронная проверка и создание бакета."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            info(f"Бакет '{self.bucket_name}' уже существует", exp=True)
        except Exception:
            try:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': self.config.get('region')
                    } if self.config.get('region') != 'us-east-1' else None
                )
                info(f"Бакет '{self.bucket_name}' создан", exp=True)
            except Exception as e:
                error(f"Не удалось создать бакет '{self.bucket_name}'", exception=e, exp=True)
                raise

    @alog_function_call(exp=True)
    @alog_execution_time(exp=True)
    async def upload_image(
        self,
        image: Image.Image,
        format: str = "PNG",
        prefix: str = "banners"
    ) -> Optional[str]:
        """
        Загружает изображение в S3.
        """
        debug(f"upload_image вызвано с метаданными format={format}, prefix={prefix}")
        if not self.config.get('enabled', False):
            debug("S3Storage отключено")
            return None

        file_key = f"{prefix}/{uuid.uuid4()}.{format.lower()}"
        debug(f"file_key сгенерирован: {file_key}")
        buffer = BytesIO()
        method = "PUT"
        endpoint = f"/{self.bucket_name}/{file_key}"
        debug(f"endpoint: {endpoint}")

        start_time = asyncio.get_event_loop().time()
        try:
            debug("Сохранение изображения в буфер")
            image.save(buffer, format=format, optimize=True)
            buffer.seek(0)
            debug(f"Размер буйера после сохранения: {len(buffer.getvalue())}")

            debug("Вызов run_in_executor для _upload_to_s3")
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._upload_to_s3,
                buffer,
                file_key,
                format
            )
            debug("run_in_executor выполнен")

            duration = asyncio.get_event_loop().time() - start_time
            log_api_request(method, sanitize_for_logging(endpoint), 200, duration)
            url = f"s3://{self.bucket_name}/{file_key}"
            debug(f"URL сгенерирован: {url}")
            debug(f"Изображение загружено: {url}", exp=True)
            return url

        except Exception as e:
            debug(f"Произошло недоразумение: {e}")
            duration = asyncio.get_event_loop().time() - start_time
            log_api_request(method, sanitize_for_logging(endpoint), 500, duration)
            error("Ошибка загрузки изображения в S3", exception=e, exp=True)
            return None

    def _upload_to_s3(self, buffer: BytesIO, file_key: str, format: str):
        content_type = "image/png" if format == "PNG" else "image/jpeg"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=file_key,
            Body=buffer,
            ContentType=content_type
        )

    async def health_check(self) -> bool:
        """Проверка доступности S3."""
        if not self.config.get('enabled', False):
            return False
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.s3_client.head_bucket,
                {'Bucket': self.bucket_name}
            )
            return True
        except Exception as e:
            error("Проверка здоровья S3 провалена", exception=e, exp=False)
            return False
