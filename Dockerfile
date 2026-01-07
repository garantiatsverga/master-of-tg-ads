# Dockerfile для AI Assistant

FROM python:3.12-slim

# Устанавливаем зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
WORKDIR /app
COPY . .

# Устанавливаем зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем дополнительные утилиты
RUN pip install simdjson colordebug

# Устанавливаем зависимости для Stable Diffusion
RUN pip install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    xformers \
    && rm -rf /var/lib/apt/lists/*

# Клонируем Stable Diffusion WebUI
RUN git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git

# Устанавливаем зависимости для Stable Diffusion
RUN pip install --no-cache-dir -r stable-diffusion-webui/requirements.txt

# Порт для приложения
EXPOSE 8000

# Команда для запуска приложения
CMD ["python", "run.py"]