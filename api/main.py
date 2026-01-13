"""
Litestar API для MCP Banner Generator
Весь API в одном файле
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from contextlib import asynccontextmanager

from litestar import Litestar, post, get, Request, Response
from litestar.status_codes import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR
from litestar.exceptions import HTTPException
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
import structlog

# Импорты из проекта
import sys
api_dir = Path(__file__).parent
project_root = api_dir.parent
sys.path.append(str(project_root))

from ai_assistant.src.ai_assistant import AIAssistant
from colordebug import info, error, warning

# Настройка логирования
logger = structlog.get_logger()

# МОДЕЛИ
@dataclass
class BannerRequest:
    """Модель запроса на генерацию баннера"""
    product: str
    product_type: str = "product"
    audience: str = "general audience"
    goal: str = "sales"
    language: str = "ru"
    style: str = "professional"
    
    def to_context(self) -> Dict[str, Any]:
        """Конвертирует в контекст для AIAssistant"""
        return {
            "product": self.product,
            "product_type": self.product_type,
            "audience": self.audience,
            "goal": self.goal,
            "language": self.language,
            "style": self.style
        }

@dataclass
class BannerResponse:
    """Модель ответа с результатом генерации"""
    success: bool
    request_id: str
    banner_url: Optional[str] = None
    banner_path: Optional[str] = None
    banner_filename: Optional[str] = None
    final_advertising_text: Optional[str] = None
    qa_status: Optional[str] = None
    qa_report: List[str] = field(default_factory=list)
    processing_time: Optional[float] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class HealthResponse:
    """Статус здоровья API"""
    status: str
    version: str
    assistant_ready: bool
    uptime: float
    total_requests: int
    successful_requests: int
    average_processing_time: float
    queue_size: int = 0

@dataclass
class APIInfo:
    """Информация об API"""
    name: str
    version: str
    description: str
    endpoints: Dict[str, str]

# СОСТОЯНИЕ ПРИЛОЖЕНИЯ
class AppState:
    """Глобальное состояние приложения"""
    
    def __init__(self):
        self.start_time = time.time()
        self.total_requests = 0
        self.successful_requests = 0
        self.processing_times: List[float] = []
        self.assistant: Optional[AIAssistant] = None
        self.request_queue: asyncio.Queue = asyncio.Queue()
        
    @property
    def uptime(self) -> float:
        return time.time() - self.start_time
    
    @property
    def avg_processing_time(self) -> float:
        if not self.processing_times:
            return 0.0
        return sum(self.processing_times) / len(self.processing_times)
    
    @property
    def queue_size(self) -> int:
        return self.request_queue.qsize()
    
    def increment_requests(self, success: bool = True):
        self.total_requests += 1
        if success:
            self.successful_requests += 1
    
    def add_processing_time(self, duration: float):
        self.processing_times.append(duration)
        # Храним только последние 100 записей
        if len(self.processing_times) > 100:
            self.processing_times.pop(0)


# ИНИЦИАЛИЗАЦИЯ


async def init_assistant(state: AppState) -> None:
    """Инициализация ИИ-ассистент"""
    try:
        logger.info("Initializing ИИ-ассистент...")
        state.assistant = AIAssistant()
        logger.info("ИИ-ассистент успешно инициализирован")
    except Exception as e:
        logger.error(f"Не удалось инициализировать ИИ-ассистента: {e}")
        state.assistant = None

@asynccontextmanager
async def lifespan(app: Litestar):
    """Управление жизненным циклом приложения"""
    # Запуск
    state = AppState()
    app.state.state = state
    
    logger.info("Запускаем MCP Banner Generator API")
    await init_assistant(state)
    
    yield
    
    # Остановка
    logger.info("SЗакрываем MCP Banner Generator API")

# УТИЛИТЫ
def read_banner_file(banner_path: str) -> Optional[bytes]:
    """Чтение файла баннера"""
    try:
        path = Path(banner_path)
        if path.exists():
            return path.read_bytes()
    except Exception as e:
        logger.error(f"Error reading banner file: {e}")
    return None

def extract_banner_info(result: Dict[str, Any]) -> Dict[str, Any]:
    """Извлечение информации о баннере из результата"""
    banner_info = {}
    
    if result.get("banner_url", "").startswith("file://"):
        banner_path = result["banner_url"][7:]
        banner_info["banner_path"] = banner_path
        banner_info["banner_filename"] = Path(banner_path).name
        
        # Пытаемся прочитать файл
        banner_bytes = read_banner_file(banner_path)
        if banner_bytes:
            banner_info["banner_bytes"] = banner_bytes
    
    return banner_info

# КОНТРОЛЛЕРЫ
@post("/api/generate")
async def generate_banner(request: Request, data: BannerRequest) -> Response:
    """
    Генерация рекламного баннера
    
    Пример запроса:
    {
        "product": "Смартфон X100 Pro с камерой 108 МП",
        "product_type": "Электроника",
        "audience": "Молодежь 18-35 лет",
        "style": "professional"
    }
    """
    state: AppState = request.app.state.state
    request_id = f"req_{int(time.time())}_{hash(data.product) % 10000:04d}"
    
    logger.info(f"Обрабатываем запрос {request_id}", 
               product=data.product[:50],
               style=data.style)
    
    start_time = time.perf_counter()
    
    try:
        # Проверяем наличие ассистента
        if state.assistant is None:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ИИ-ассистент не инициализирован"
            )
        
        # Конвертируем запрос в контекст
        context = data.to_context()
        
        # Запускаем генерацию (помещаем в очередь)
        await state.request_queue.put((request_id, context))
        
        # Запускаем генерацию
        result = await state.assistant.run_advertising_pipeline(context)
        
        # Извлекаем информацию о баннере
        banner_info = extract_banner_info(result)
        
        # Создаем ответ
        processing_time = time.perf_counter() - start_time
        response = BannerResponse(
            success=result.get("pipeline_success", False),
            request_id=request_id,
            banner_url=result.get("banner_url"),
            banner_path=banner_info.get("banner_path"),
            banner_filename=banner_info.get("banner_filename"),
            final_advertising_text=result.get("final_advertising_text", ""),
            qa_status=result.get("qa_status"),
            qa_report=result.get("qa_report", []),
            processing_time=round(processing_time, 3)
        )
        
        # Обновляем статистику
        state.increment_requests(success=True)
        state.add_processing_time(processing_time)
        await state.request_queue.get()  # Убираем из очереди
        
        logger.info(f"Request {request_id} completed", 
                   time=f"{processing_time:.2f}s",
                   success=response.success)
        
        return Response(
            content=response.to_dict(),
            status_code=HTTP_200_OK
        )
        
    except Exception as e:
        processing_time = time.perf_counter() - start_time
        
        # Если был в очереди - убираем
        try:
            await state.request_queue.get()
        except:
            pass
        
        error_msg = f"Ошибка при обработке запроса {request_id}: {str(e)}"
        logger.error(error_msg)
        
        response = BannerResponse(
            success=False,
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
            processing_time=round(processing_time, 3)
        )
        
        return Response(
            content=response.to_dict(),
            status_code=HTTP_500_INTERNAL_SERVER_ERROR
        )

@get("/api/health")
async def health_check(request: Request) -> HealthResponse:
    """Проверка здоровья API"""
    state: AppState = request.app.state.state
    
    return HealthResponse(
        status="healthy" if state.assistant else "degraded",
        version="1.0.0",
        assistant_ready=state.assistant is not None,
        uptime=round(state.uptime, 2),
        total_requests=state.total_requests,
        successful_requests=state.successful_requests,
        average_processing_time=round(state.avg_processing_time, 3),
        queue_size=state.queue_size
    )

@get("/api/banners/{banner_filename:str}")
async def get_banner(banner_filename: str) -> Response:
    """
    Получение баннера по имени файла
    
    Пример: GET /api/banners/banner_smartphone_20240111_120000.png
    """
    # Ищем файл в generated_banners
    banners_dir = project_root / "generated_banners"
    banner_path = banners_dir / banner_filename
    
    if not banner_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Баннер '{banner_filename}' не найден"
        )
    
    try:
        banner_bytes = banner_path.read_bytes()
        return Response(
            content=banner_bytes,
            media_type="image/png"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка чтения баннера: {str(e)}"
        )

@get("/api/info")
async def api_info() -> APIInfo:
    """Информация об API"""
    return APIInfo(
        name="MCP Banner Generator API",
        version="1.0.0",
        description="API для генерации рекламных баннеров с помощью AI агентов",
        endpoints={
            "POST /api/generate": "Генерация баннера",
            "GET /api/health": "Проверка здоровья API",
            "GET /api/banners/{filename}": "Получение баннера по имени файла",
            "GET /api/info": "Информация об API (эта страница)",
            "GET /schema": "OpenAPI схема",
            "GET /docs": "Swagger документация"
        }
    )

@get("/")
async def root() -> Dict[str, Any]:
    """Корневой эндпоинт"""
    return {
        "message": "Добро пожаловать в MCP Banner Generator API",
        "docs": "/docs",
        "health": "/api/health",
        "info": "/api/info"
    }


# НАСТРОЙКА


cors_config = CORSConfig(
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=True,
    max_age=3600
)


# ПРИЛОЖЕНИЕ


app = Litestar(
    route_handlers=[
        generate_banner,
        health_check,
        get_banner,
        api_info,
        root
    ],
    lifespan=[lifespan],
    cors_config=cors_config,
    debug=True
)


# ЗАПУСК


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("MCP Banner Generator API")
    print("=" * 60)
    print(f"Корень проекта: {project_root}")
    print(f"Хост: 0.0.0.0:8000")
    print(f"Документация: http://localhost:8000/docs")
    print(f"Схема: http://localhost:8000/schema")
    print(f"Health check: http://localhost:8000/api/health")
    print(f"Информация: http://localhost:8000/api/info")
    print(f"Генерация: POST http://localhost:8000/api/generate")
    print("=" * 60)
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )