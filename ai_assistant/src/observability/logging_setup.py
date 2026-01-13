from colordebug import *
import os
from datetime import datetime
from pathlib import Path
import sys
import re

# Добавляем корень проекта в путь Python
sys.path.append(str(Path(__file__).parent.parent))

def safe_read_file(file_path, encoding='utf-8'):
    """
    Безопасное чтение файла с обработкой кодировки
    
    Args:
        file_path (str): Путь к файлу
        encoding (str): Кодировка по умолчанию
    
    Returns:
        str: Содержимое файла
    """
    encodings_to_try = ['utf-8', 'windows-1251', 'cp1251', 'iso-8859-1']
    
    for enc in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Ошибка при чтении файла {file_path} в кодировке {enc}: {e}")
            continue
    
    # Если ни одна кодировка не подходит, пытаемся прочитать в бинарном режиме
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            return content.decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path} в бинарном режиме: {e}")
        return ""

def safe_write_file(file_path, content, encoding='utf-8'):
    """
    Безопасная запись в файл с обработкой кодировки
    
    Args:
        file_path (str): Путь к файлу
        content (str): Содержимое для записи
        encoding (str): Кодировка для записи
    """
    try:
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Ошибка при записи в файл {file_path}: {e}")
        return False

# Значения конфигурации по умолчанию
DEFAULT_LOG_FILE = "app.log"
DEFAULT_MAX_LINES = 5000
DEFAULT_LOG_FORMAT = "text"
DEFAULT_LOG_LEVEL = "info"
DEFAULT_WRAP_WIDTH = 80

# Ключи чувствительных данных для сантизации
SENSITIVE_KEYS = [
    'password', 'token', 'api_key', 'secret', 
    'auth_key', 'credential', 'credit_card', 
    'social_security', 'private_key', 'jwt_token', 
    'encryption_key'
]

def sanitize_for_logging(text):
    """
    Быстрая сантизация чувствительных данных в тексте
    
    Args:
        text (str): Текст для санкции
    
    Returns:
        str: Санкционированный текст
    """
    if not isinstance(text, str):
        return text
    
    # Скрытие API ключей в различных форматах
    patterns = [
        (r'(api[_-]?key)[=:]\s*[\w-]+', r'\1=***REDACTED***'),
        (r'(token)[=:]\s*[\w\.-]+', r'\1=***REDACTED***'),
        (r'(secret)[=:]\s*[\w\.-]+', r'\1=***REDACTED***'),
        (r'(password)[=:]\s*\S+', r'\1=***REDACTED***'),
        (r'[\w\.-]+@[\w\.-]+\.[\w]+', '***EMAIL_REDACTED***'),  # Email
        (r'\b\d{16}\b', '***CARD_REDACTED***'),  # Кредитные карты
    ]
    
    sanitized_text = text
    for pattern, replacement in patterns:
        sanitized_text = re.sub(pattern, replacement, sanitized_text, flags=re.IGNORECASE)
    
    return sanitized_text

def setup_logging(
    log_file=DEFAULT_LOG_FILE,
    max_lines=DEFAULT_MAX_LINES,
    log_format=DEFAULT_LOG_FORMAT,
    log_level=DEFAULT_LOG_LEVEL,
    wrap_width=DEFAULT_WRAP_WIDTH,
    console_output=True,
    preserve_errors=True
):
    """
    Настройка конфигурации логирования для приложения.
    
    Аргументы:
        log_file (str): Путь к файлу лога
        max_lines (int): Максимальное количество строк перед ротацией лога
        log_format (str): Формат лога ('text' или 'json')
        log_level (str): Минимальный уровень лога для захвата
        wrap_width (int): Максимальная ширина строки для переноса текста
        console_output (bool): Включить вывод в консоль
        preserve_errors (bool): Сохранять сообщения об ошибках при ротации
    """
    # Установка формата лога
    set_log_format(log_format)
    
    # Установка уровня лога
    set_log_level(log_level)
    
    # Включение логирования в файл
    enable_file_logging(
        log_file,
        textwrapping=True,
        wrapint=wrap_width
    )
    
    # Конфигурация ротации лога
    set_max_log_lines(max_lines)
    enable_error_preservation(preserve_errors)
    
    # Конфигурация вывода в консоль
    if not console_output:
        disable_console_output()
    
    # Добавление ключей для сантизации чувствительных данных
    add_sensitive_keys(SENSITIVE_KEYS)
    
    # Логирование инициализации
    info(f"Логирование инициализировано: file={log_file}, format={log_format}, level={log_level}",
         exp=True, textwrapping=True, wrapint=wrap_width)
    
    # Проверка и исправление кодировки файла лога
    if os.path.exists(log_file):
        try:
            content = safe_read_file(log_file)
            if content:
                safe_write_file(log_file, content, encoding='utf-8')
        except Exception as e:
            print(f"Ошибка при исправлении кодировки файла лога: {e}")

def log_application_start():
    """
    Логирование информации о запуске приложения.
    """
    info("Приложение запускается", exp=True)
    debug(f"Текущая рабочая директория: {os.getcwd()}", exp=True)
    debug(f"Версия Python: {os.sys.version}", exp=True)
    debug(f"Время запуска: {datetime.now().isoformat()}", exp=True)

def log_application_shutdown():
    """
    Логирование информации о завершении работы приложения.
    """
    info("Приложение завершает работу", exp=True)
    debug(f"Время завершения: {datetime.now().isoformat()}", exp=True)

def log_module_initialization(module_name):
    """
    Логирование инициализации модуля.
    
    Аргументы:
        module_name (str): Название инициализируемого модуля
    """
    info(f"Инициализация модуля: {module_name}", exp=True, 
         textwrapping=True, wrapint=DEFAULT_WRAP_WIDTH)

def log_api_request(method, endpoint, status_code, duration):
    """
    Логирование информации о запросе к API.
    
    Аргументы:
        method (str): HTTP метод (GET, POST и т.д.)
        endpoint (str): Конечная точка API (будет санкционирована)
        status_code (int): HTTP статус код
        duration (float): Длительность запроса в секундах
    """
    # Санкция чувствительных данных в эндпоинте
    safe_endpoint = sanitize_for_logging(endpoint)
    
    # Используем log_value из colordebug для структурированного логирования
    log_value("method", method, exp=True)
    log_value("endpoint", safe_endpoint, exp=True)
    log_value("status_code", status_code, exp=True)
    log_value("duration_ms", f"{duration*1000:.2f}", exp=True)

def log_database_operation(operation, table, duration, success_flag):
    """
    Логирование информации об операции с базой данных.
    
    Аргументы:
        operation (str): Тип операции (query, insert, update, delete)
        table (str): Название таблицы базы данных
        duration (float): Длительность операции в секундах
        success_flag (bool): Успешность операции
    """
    # Используем timer из colordebug для измерения времени
    with timer(f"База данных {operation} на {table}", exp=True):
        if success_flag:
            success(f"Операция {operation} на таблице {table} выполнена успешно", 
                   exp=True, textwrapping=True, wrapint=DEFAULT_WRAP_WIDTH)
        else:
            error(f"Операция {operation} на таблице {table} завершилась с ошибкой", 
                 exp=True, textwrapping=True, wrapint=DEFAULT_WRAP_WIDTH)

def log_ai_operation(model_name, operation_type, input_length, output_length, duration):
    """
    Логирование информации об операции ИИ/ML.
    
    Аргументы:
        model_name (str): Название модели ИИ
        operation_type (str): Тип операции (inference, training и т.д.)
        input_length (int): Длина входных данных
        output_length (int): Длина выходных данных
        duration (float): Длительность операции в секундах
    """
    info(f"Операция ИИ: {model_name} - {operation_type}", 
         exp=True, textwrapping=True, wrapint=DEFAULT_WRAP_WIDTH)
    log_value("input_length", input_length, exp=True)
    log_value("output_length", output_length, exp=True)
    log_value("duration_ms", f"{duration*1000:.2f}", exp=True)

def log_security_event(event_type, user_id, ip_address, details):
    """
    Логирование событий, связанных с безопасностью.
    
    Аргументы:
        event_type (str): Тип события безопасности
        user_id (str): Идентификатор пользователя, связанного с событием
        ip_address (str): IP-адрес запроса
        details (str): Дополнительные детали о событии
    """
    warning(f"Событие безопасности: {event_type}", 
           exp=True, textwrapping=True, wrapint=DEFAULT_WRAP_WIDTH)
    log_value("user_id", user_id, exp=True)
    log_value("ip_address", ip_address, exp=True)
    log_value("details", sanitize_for_logging(details), exp=True)  # Сантизация деталей

def log_performance_metrics(metrics):
    """
    Логирование метрик производительности.
    
    Аргументы:
        metrics (dict): Словарь метрик производительности
    """
    info("Метрики производительности", exp=True, textwrapping=True, wrapint=DEFAULT_WRAP_WIDTH)
    # Используем log_dict из colordebug для красивого вывода словаря
    log_dict(metrics, "Метрики", exp=True)

def log_configuration(config):
    """
    Логирование конфигурации приложения.
    
    Аргументы:
        config (dict): Словарь конфигурации приложения
    """
    info("Конфигурация приложения", exp=True, textwrapping=True, wrapint=DEFAULT_WRAP_WIDTH)
    
    # Создаем безопасную копию конфигурации для логирования
    safe_config = {}
    for key, value in config.items():
        if isinstance(value, dict):
            safe_config[key] = {}
            for subkey, subvalue in value.items():
                if any(sensitive in subkey.lower() for sensitive in SENSITIVE_KEYS):
                    safe_config[key][subkey] = "***REDACTED***"
                else:
                    safe_config[key][subkey] = subvalue
        else:
            safe_config[key] = value
    
    log_dict(safe_config, "Конфигурация", exp=True)

# Пример использования
if __name__ == "__main__":
    # Настройка логирования для хакатона
    setup_logging(
        log_file="hackathon.log",
        max_lines=1000,
        log_format="text",
        log_level="debug",
        wrap_width=80,
        console_output=True,
        preserve_errors=True
    )
    
    # Логирование запуска приложения
    log_application_start()
    
    # Примеры логов с сантизацией
    info("Это информационное сообщение", exp=True)
    success("Операция выполнена успешно", exp=True)
    warning("Это предупреждающее сообщение", exp=True)
    
    # Пример с чувствительными данными
    sensitive_request = "https://api.example.com/auth?api_key=sk_live_1234567890&token=abc123"
    log_api_request("POST", sensitive_request, 200, 0.15)
    
    # Пример с переносом текста
    long_message = "Это очень длинное сообщение, демонстрирующее функциональность переноса текста в библиотеке colordebug. Оно должно быть перенесено на несколько строк в соответствии с указанной шириной."
    info(long_message, exp=True, textwrapping=True, wrapint=40)
    
    # Логирование завершения работы приложения
    log_application_shutdown()