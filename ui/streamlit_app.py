import streamlit as st
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Добавляем корень проекта в путь Python
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from agents.banner_designer_agent import BannerDesignerAgent
from MCPServer import MCPServer, ToolRegistry, SimpleRetryPolicy, InMemoryCachePolicy
from ai_assistant.src.ai_assistant import AIAssistant

# Настройка темной темы
st.set_page_config(
    page_title="MCP-генератор баннеров",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Загрузка внешнего CSS файла
def load_css():
    """Загружает внешний CSS файл"""
    with open("ui/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Применяем кастомные стили
load_css()


# Импортируем реальный инструмент для генерации изображений
from agents.tools.image_generation_tool import ImageGenerationTool


# Инициализация MCP Server и агента
def init_mcp_server():
    """Инициализация MCP сервера и агента"""
    registry = ToolRegistry()
    retry_policy = SimpleRetryPolicy()
    cache_policy = InMemoryCachePolicy()
    
    # Регистрируем реальный инструмент для генерации изображений
    registry.register(ImageGenerationTool())
    
    mcp_server = MCPServer(
        registry=registry,
        retry_policy=retry_policy,
        cache_policy=cache_policy
    )
    
    # Создаем агента
    banner_agent = BannerDesignerAgent(mcp_server=mcp_server)
    
    return mcp_server, banner_agent


# Инициализация AI Assistant
def init_ai_assistant():
    """Инициализация AI ассистента"""
    assistant = AIAssistant()
    return assistant

# Функция для генерации баннера
async def generate_banner(prompt: str) -> Dict[str, Any]:
    """Асинхронная функция для генерации баннера"""
    print(f"Generating banner for prompt: {prompt}")
    assistant = init_ai_assistant()
    
    try:
        result = await assistant.process_request(
            product_description=prompt,
            style_preference="professional",
            include_image=True
        )
        print(f"Banner generation result: {result}")
        return result
    except Exception as e:
        print(f"Error during banner generation: {e}")
        return {"error": str(e)}


# Основной интерфейс
st.title("MCP-генератор баннеров")

# Инициализация состояния чата
if "messages" not in st.session_state:
    st.session_state.messages = []

# Отображение сообщений чата
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Ввод пользователя
prompt = st.chat_input("Введите описание баннера...")

if prompt:
    # Добавляем сообщение пользователя в чат
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Отображаем сообщение пользователя
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Отображаем индикатор загрузки
    with st.chat_message("bot"):
        with st.spinner("Генерация баннера..."):
            # Асинхронный вызов генерации баннера
            result = asyncio.run(generate_banner(prompt))
            
            if result.get("success", False):
                ad_text = result.get("components", {}).get("ad_text", "Текст не сгенерирован")
                image_url = result.get("components", {}).get("image_url", "Изображение не сгенерировано")
                response = f"Баннер успешно сгенерирован! 🎉\n\nТекст: {ad_text}\n\nИзображение: {image_url}"
            else:
                response = f"Ошибка при генерации баннера: {result.get('error', 'Неизвестная ошибка')}"
            
            st.markdown(response)
    
    # Добавляем ответ бота в историю чата
    st.session_state.messages.append({"role": "bot", "content": response})

