# Dockerfile для AI Assistant

FROM python:3.12-slim

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
WORKDIR /app
COPY . .

# Устанавливаем зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем дополнительные утилиты
RUN pip install simdjson colordebug

# Порт для приложения
EXPOSE 8000

# Команда для запуска приложения
CMD ["python", "run.py"]