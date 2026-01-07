# Гайд по установке и настройке Stable Diffusion

Этот гайд поможет вам установить и настроить Stable Diffusion для работы с текущей конфигурацией проекта.

## Метод 1: Автоматическая установка через скрипт (рекомендуется)

1. Клонируйте репозиторий проекта:
   ```bash
   git clone https://github.com/garantiatsverga/master-of-tg-ads.git
   cd master-of-tg-ads
   ```

2. Запустите скрипт установки зависимостей:
   ```bash
   python src/deps_installer.py
   ```
   Этот скрипт автоматически:
   - Проверит и установит все необходимые зависимости
   - Скачает и настроит Stable Diffusion
   - Создаст файл .env на основе .env.example
   - Установит все Python зависимости

3. Запустите все сервисы с помощью Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Дождитесь запуска всех сервисов

## Метод 2: Установка через Docker Compose

1. Убедитесь, что у вас установлен Docker и Docker Compose
2. Установите NVIDIA Container Toolkit для поддержки GPU в Docker:
   ```bash
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
   && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
   && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   sudo systemctl restart docker
   ```
3. Клонируйте репозиторий проекта
4. Создайте папку для моделей Stable Diffusion:
   ```bash
   mkdir -p stable-diffusion-models
   ```
5. Скачайте модель Stable Diffusion (например, runwayml/stable-diffusion-v1-5) и поместите ее в папку `stable-diffusion-models`
6. Запустите все сервисы с помощью Docker Compose:
   ```bash
   docker-compose up -d
   ```
7. Дождитесь запуска всех сервисов

## Метод 2: Ручная установка

### Шаг 1: Установка Python и зависимостей

1. Установите Python 3.10 или новее с официального сайта: https://www.python.org/downloads/
2. Убедитесь, что Python добавлен в PATH
3. Установите Git: https://git-scm.com/downloads

## Шаг 2: Установка Stable Diffusion WebUI (AUTOMATIC1111)

1. Клонируйте репозиторий AUTOMATIC1111:
   ```bash
   git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
   cd stable-diffusion-webui
   ```

2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Скачайте модель Stable Diffusion (например, runwayml/stable-diffusion-v1-5):
   - Скачайте файл модели (например, `v1-5-pruned-emaonly.ckpt`) с Hugging Face
   - Поместите его в папку `stable-diffusion-webui/models/Stable-diffusion/`

## Шаг 3: Настройка конфигурации

1. Откройте файл `config.yaml` в проекте
2. Обновите раздел `stable_diffusion`:
   ```yaml
   stable_diffusion:
     provider: 'local'
     model: 'runwayml/stable-diffusion-v1-5'
     device: 'cuda'
     base_url: 'http://localhost:7860'
     width: 1920
     height: 1080
     steps: 25
     timeout: 300
   ```

## Шаг 4: Запуск Stable Diffusion WebUI

### Для Docker Compose:
1. Убедитесь, что все сервисы запущены:
   ```bash
   docker-compose ps
   ```
2. Проверьте логи Stable Diffusion:
   ```bash
   docker-compose logs stable-diffusion
   ```

### Для ручной установки:
1. Перейдите в папку с Stable Diffusion WebUI:
   ```bash
   cd stable-diffusion-webui
   ```

2. Запустите WebUI:
   ```bash
   python launch.py --api --listen
   ```

   - Флаг `--api` включает API-режим
   - Флаг `--listen` позволяет подключаться с других устройств

3. Дождитесь запуска. Вы увидите сообщение:
   ```
   Running on local URL:  http://localhost:7860
   ```

## Шаг 5: Проверка подключения

1. Откройте браузер и перейдите по адресу: http://localhost:7860
2. Убедитесь, что WebUI работает
3. Проверьте, что API доступен, открыв: http://localhost:7860/docs

## Шаг 6: Настройка проекта

1. Убедитесь, что в файле `config.yaml` указан правильный `base_url`:
   ```yaml
   base_url: 'http://localhost:7860'
   ```

2. Запустите ваше приложение:
   ```bash
   streamlit run ui/streamlit_app.py
   ```

## Шаг 7: Тестирование

1. Откройте приложение Streamlit в браузере
2. Введите промпт для генерации баннера
3. Убедитесь, что изображение генерируется и апскейлится корректно

## Устранение неполадок

### Проблема: Stable Diffusion не запускается
- **Решение**: Убедитесь, что у вас установлены все зависимости и драйверы NVIDIA
- **Решение**: Проверьте, что у вас достаточно памяти на видеокарте

### Проблема: API не доступен
- **Решение**: Убедитесь, что Stable Diffusion запущен с флагом `--api`
- **Решение**: Проверьте, что порт 7860 не занят другим приложением

### Проблема: Изображение не генерируется
- **Решение**: Проверьте, что модель находится в правильной папке
- **Решение**: Убедитесь, что у вас достаточно памяти на видеокарте

## Дополнительные рекомендации

1. Для улучшения качества изображений можно использовать дополнительные модели (например, ESRGAN для апскейла)
2. Для ускорения генерации можно использовать флаг `--xformers` при запуске Stable Diffusion
3. Для экономии памяти можно использовать флаг `--medvram` или `--lowvram`

## Docker Compose конфигурация

В файле `docker-compose.yml` уже настроен сервис Stable Diffusion:

```yaml
stable-diffusion:
  image: ghcr.io/automatic1111/stable-diffusion-webui:latest
  container_name: ai_assistant_stable_diffusion
  environment:
    - CLIP_STOP_AT_LAST_LAYERS=2
  ports:
    - "7860:7860"
  volumes:
    - ./stable-diffusion-models:/stable-diffusion-webui/models/Stable-diffusion
  command: --api --listen --port 7860
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  networks:
    - ai_network
```

### Особенности конфигурации:
- Используется официальный образ AUTOMATIC1111
- Порт 7860 открыт для доступа к API
- Модели загружаются из папки `stable-diffusion-models`
- API запускается с флагами `--api --listen`
- Требуется GPU с поддержкой CUDA

## Полезные ссылки

- Официальный репозиторий AUTOMATIC1111: https://github.com/AUTOMATIC1111/stable-diffusion-webui
- Модели Stable Diffusion на Hugging Face: https://huggingface.co/runwayml/stable-diffusion-v1-5
- Документация по API: https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API
- Docker образ AUTOMATIC1111: https://github.com/AUTOMATIC1111/stable-diffusion-webui/pkgs/container/stable-diffusion-webui

Теперь вы готовы использовать Stable Diffusion для генерации баннеров в вашем проекте!