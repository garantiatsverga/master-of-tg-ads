"""
Клиент для работы с MCP Banner Generator API
"""
import requests
import json
from typing import Dict, Any, Optional
from pathlib import Path
import time

class BannerAPIClient:
    """Клиент для взаимодействия с API генерации баннеров"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
    def generate(
        self,
        product: str,
        product_type: str = "product",
        audience: str = "general audience",
        style: str = "professional",
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Генерация баннера
        
        Args:
            product: Описание продукта
            product_type: Тип продукта
            audience: Целевая аудитория
            style: Стиль рекламы
            timeout: Таймаут в секундах
            
        Returns:
            Результат генерации
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "product": product,
            "product_type": product_type,
            "audience": audience,
            "style": style
        }
        
        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Таймаут запроса - генерация заняла слишком много времени",
                "processing_time": timeout
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": f"Не удалось подключиться к API {self.base_url}"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Ошибка запроса: {str(e)}"
            }
    
    def get_banner(self, banner_filename: str) -> Optional[bytes]:
        """
        Получение баннера по имени файла
        
        Args:
            banner_filename: Имя файла баннера
            
        Returns:
            Байты изображения или None
        """
        url = f"{self.base_url}/api/banners/{banner_filename}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Проверяем что это изображение
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type:
                return response.content
            else:
                # Если не изображение, пробуем прочитать как JSON
                try:
                    return response.json()
                except:
                    return response.content
                    
        except requests.exceptions.RequestException:
            return None
    
    def health(self) -> Dict[str, Any]:
        """Проверка здоровья API"""
        url = f"{self.base_url}/api/health"
        
        try:
            response = self.session.get(url, timeout=5)
            return response.json()
        except:
            return {
                "status": "unavailable",
                "assistant_ready": False,
                "error": "API недоступен"
            }
    
    def info(self) -> Dict[str, Any]:
        """Получение информации об API"""
        url = f"{self.base_url}/api/info"
        
        try:
            response = self.session.get(url, timeout=5)
            return response.json()
        except:
            return {
                "name": "MCP Banner Generator API",
                "error": "API недоступен"
            }
    
    def download_banner(self, response: Dict[str, Any]) -> Optional[bytes]:
        """
        Скачивание баннера из ответа
        
        Args:
            response: Ответ от API generate
            
        Returns:
            Байты изображения или None
        """
        if not response.get("success"):
            return None
        
        banner_filename = response.get("banner_filename")
        if not banner_filename:
            return None
        
        return self.get_banner(banner_filename)
    
    def format_result(self, response: Dict[str, Any]) -> str:
        """
        Форматирование результата для отображения
        
        Args:
            response: Ответ от API
            
        Returns:
            Форматированная строка
        """
        if response.get("success"):
            text = response.get("final_advertising_text", "")
            time = response.get("processing_time", 0)
            return f"✅ Успешно ({time:.1f}с)\n📄 {text}"
        else:
            error = response.get("error", "Неизвестная ошибка")
            return f"❌ Ошибка: {error}"

# Синглтон клиента
_client_instance = None

def get_client(base_url: str = "http://localhost:8000") -> BannerAPIClient:
    """Получение экземпляра клиента (синглтон)"""
    global _client_instance
    if _client_instance is None:
        _client_instance = BannerAPIClient(base_url)
    return _client_instance

def test_connection(base_url: str = "http://localhost:8000") -> bool:
    """Тестирование подключения к API"""
    try:
        client = BannerAPIClient(base_url)
        health = client.health()
        return health.get("status") in ["healthy", "degraded"]
    except:
        return False