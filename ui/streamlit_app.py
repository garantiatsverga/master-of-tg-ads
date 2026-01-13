"""
Streamlit интерфейс для MCP Banner Generator
Использует API клиент
"""
import streamlit as st
import time
from pathlib import Path
import sys

# Добавляем путь к API клиенту
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

try:
    from api.client import get_client, test_connection
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False
    st.error("API клиент не найден")

# Настройка страницы
st.set_page_config(
    page_title="MCP-генератор баннеров",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Загрузка стилей
def load_css():
    try:
        css_path = Path(__file__).parent / "styles.css"
        with open(css_path, 'r', encoding='utf-8') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except:
        st.warning("Стили не загружены")

load_css()

# Инициализация состояния
def init_state():
    defaults = {
        'history': [],
        'current_result': None,
        'product_input': '',
        'api_base_url': 'http://localhost:8000',
        'connection_checked': False
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

def main():
    st.title("MCP-генератор баннеров")
    st.markdown("---")
    
    # Проверка доступности API
    if not API_AVAILABLE:
        st.error("""
        API клиент недоступен.
        
        Убедитесь, что:
        1. Файл `api/client.py` существует
        2. API сервер запущен: `python api/main.py`
        3. Правильно настроены пути импорта
        """)
        return
    
    # Настройка подключения
    with st.sidebar:
        st.header("Настройки подключения")
        
        api_url = st.text_input(
            "URL API",
            value=st.session_state.api_base_url,
            help="Адрес API сервера"
        )
        
        if api_url != st.session_state.api_base_url:
            st.session_state.api_base_url = api_url
            st.session_state.connection_checked = False
        
        # Проверка подключения
        if st.button("🔌 Проверить подключение", use_container_width=True):
            with st.spinner("Проверка..."):
                if test_connection(api_url):
                    st.success("Подключение успешно")
                    st.session_state.connection_checked = True
                else:
                    st.error("Не удалось подключиться к API")
                    st.session_state.connection_checked = False
        
        if st.session_state.connection_checked:
            client = get_client(api_url)
            health = client.health()
            
            st.divider()
            st.header("Настройки генерации")
            
            style = st.selectbox(
                "Стиль",
                ["professional", "creative", "urgent", "emotional"],
                index=0
            )
            
            audience = st.text_input(
                "Аудитория",
                value="Молодежь 18-35 лет"
            )
            
            product_type = st.selectbox(
                "Тип продукта",
                ["Товар", "Услуга", "Курс", "Приложение", "Другое"]
            )
            
            st.divider()
            
            # Примеры
            st.header("Примеры")
            
            examples = [
                "Смартфон с камерой 108 МП",
                "Онлайн-курс по Python",
                "Фитнес-абонемент со скидкой",
                "Дизайнерские кроссовки"
            ]
            
            for ex in examples:
                if st.button(f"{ex}", use_container_width=True):
                    st.session_state.product_input = ex
                    st.rerun()
            
            st.divider()
            
            # Статистика
            if health.get("total_requests", 0) > 0:
                st.metric("Всего запросов", health["total_requests"])
                st.metric("Успешных", health["successful_requests"])
                st.metric("Среднее время", f"{health.get('average_processing_time', 0):.1f}с")
                if health.get("queue_size", 0) > 0:
                    st.warning(f"В очереди: {health['queue_size']}")
    
    # Основной интерфейс
    if not st.session_state.connection_checked:
        st.warning("Проверьте подключение к API в сайдбаре")
        return
    
    client = get_client(st.session_state.api_base_url)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Ввод промпта
        product_input = st.text_area(
            "**Опишите продукт для рекламы:**",
            value=st.session_state.product_input,
            placeholder="Например: Новый смартфон X100 Pro с камерой 108 МП, ночной съемкой и премиальным дизайном...",
            height=120,
            key="product_text_area"
        )
        
        # Обновляем состояние
        if product_input != st.session_state.product_input:
            st.session_state.product_input = product_input
        
        # Кнопки
        col_btn1, col_btn2 = st.columns([3, 1])
        
        with col_btn1:
            generate_clicked = st.button(
                "**Сгенерировать баннер**",
                type="primary",
                use_container_width=True,
                disabled=not product_input.strip()
            )
        
        with col_btn2:
            if st.button("Сбросить", use_container_width=True):
                st.session_state.current_result = None
                st.rerun()
        
        # Обработка генерации
        if generate_clicked and product_input.strip():
            with st.spinner("Генерация баннера... Это может занять 1-2 минуты"):
                result = client.generate(
                    product=product_input,
                    product_type=st.session_state.get('product_type', 'Товар'),
                    audience=st.session_state.get('audience', 'general audience'),
                    style=st.session_state.get('style', 'professional')
                )
                
                st.session_state.current_result = result
                
                # Добавляем в историю
                st.session_state.history.insert(0, {
                    "timestamp": time.strftime("%H:%M:%S"),
                    "prompt": product_input,
                    "result": result
                })
                
                st.rerun()
        
        # Отображение результата
        if st.session_state.current_result:
            show_result(st.session_state.current_result, client)
    
    with col2:
        show_history()

def show_result(result: dict, client):
    """Отображение результата генерации"""
    if result.get("success"):
        st.success("**Баннер успешно создан!**")
        st.markdown("---")
        
        # Две колонки
        col_text, col_image = st.columns([1, 1])
        
        with col_text:
            st.subheader("**Рекламный текст:**")
            
            ad_text = result.get("final_advertising_text", "")
            if ad_text:
                st.info(ad_text)
                
                # Кнопка копирования
                if st.button("Копировать текст", key="copy_text"):
                    st.write("Текст скопирован")
            else:
                st.warning("Текст не сгенерирован")
            
            # QA статус
            qa_status = result.get("qa_status", "UNKNOWN")
            if qa_status == "APPROVED":
                st.success(f"**Проверка качества:** {qa_status}")
            else:
                st.warning(f"**Проверка качества:** {qa_status}")
            
            # Детали
            with st.expander(" Детали"):
                st.json(result)
        
        with col_image:
            st.subheader("**Баннер:**")
            
            banner_filename = result.get("banner_filename")
            if banner_filename:
                # Пытаемся получить баннер
                banner_bytes = client.get_banner(banner_filename)
                
                if banner_bytes and isinstance(banner_bytes, bytes):
                    st.image(banner_bytes, use_column_width=True)
                    
                    # Кнопка скачивания
                    st.download_button(
                        "Скачать баннер",
                        data=banner_bytes,
                        file_name=banner_filename,
                        mime="image/png",
                        use_container_width=True
                    )
                else:
                    st.info(f"Файл: {banner_filename}")
                    st.info("Используйте кнопку скачивания в деталях")
            else:
                st.warning("Баннер не сгенерирован")
    
    else:
        st.error(f"**Ошибка:** {result.get('error', 'Неизвестная ошибка')}")
        
        if st.button("Попробовать снова", key="retry"):
            st.session_state.current_result = None
            st.rerun()

def show_history():
    """Отображение истории"""
    st.subheader("**История**")
    
    if st.session_state.history:
        for i, item in enumerate(st.session_state.history[:5]):
            with st.expander(f"#{i+1}: {item['prompt'][:30]}...", expanded=(i==0)):
                st.caption(f"{item['timestamp']}")
                
                if item['result'].get('success'):
                    st.success("Успешно")
                    text = item['result'].get('final_advertising_text', '')[:50]
                    if text:
                        st.caption(f"{text}...")
                else:
                    st.error("Ошибка")
                
                if st.button(f"Загрузить #{i+1}", key=f"load_{i}"):
                    st.session_state.current_result = item['result']
                    st.rerun()
    else:
        st.info("История пуста")
    
    st.divider()
    
    # Быстрые действия
    if st.button("Очистить историю", use_container_width=True):
        st.session_state.history = []
        st.rerun()
    
    if st.button("Информация об API", use_container_width=True):
        client = get_client(st.session_state.api_base_url)
        info = client.info()
        st.json(info)

# Футер
st.markdown("---")
st.caption("🎨 MCP Generator v1.0 | ⚡ Litestar API | Streamlit UI")

if __name__ == "__main__":
    main()