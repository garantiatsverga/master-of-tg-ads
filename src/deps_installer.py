#!/usr/bin/env python3
"""
Скрипт для установки зависимостей проекта, включая Stable Diffusion.
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path


def check_python_version():
    """Проверка версии Python."""
    if sys.version_info < (3, 10):
        print("Ошибка: Требуется Python 3.10 или новее")
        sys.exit(1)
    print("✓ Python версии 3.10+ установлен")


def install_python_dependencies():
    """Установка Python зависимостей."""
    print("\nУстановка Python зависимостей...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("✓ Python зависимости установлены")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке Python зависимостей: {e}")
        sys.exit(1)


def check_git():
    """Проверка установки Git."""
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        print("✓ Git установлен")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Ошибка: Git не установлен. Пожалуйста, установите Git с https://git-scm.com/downloads")
        sys.exit(1)


def check_docker_compose():
    """Проверка установки Docker Compose."""
    try:
        subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
        print("✓ Docker Compose установлен")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Ошибка: Docker Compose не установлен. Пожалуйста, установите Docker Compose")
        sys.exit(1)


def check_nvidia_gpu():
    """Проверка наличия NVIDIA GPU."""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ NVIDIA GPU обнаружен")
            print(result.stdout)
        else:
            print("Внимание: NVIDIA GPU не обнаружен. Stable Diffusion будет работать медленно на CPU")
    except FileNotFoundError:
        print("Внимание: nvidia-smi не найден. Возможно, драйверы NVIDIA не установлены")


def download_stable_diffusion_model():
    """Скачивание модели Stable Diffusion."""
    model_dir = Path("stable-diffusion-models")
    model_dir.mkdir(exist_ok=True)
    
    model_url = "https://huggingface.co/segmind/tiny-sd/resolve/main/tiny-sd.ckpt"
    model_path = model_dir / "tiny-sd.ckpt"
    
    if model_path.exists():
        print(f"✓ Модель Stable Diffusion уже существует: {model_path}")
        return
    
    print("\nСкачивание модели Stable Diffusion...")
    try:
        # Используем wget или curl для скачивания
        if shutil.which("wget"):
            subprocess.run(["wget", "-O", str(model_path), model_url], check=True)
        elif shutil.which("curl"):
            subprocess.run(["curl", "-L", "-o", str(model_path), model_url], check=True)
        else:
            print("Ошибка: Для скачивания модели требуется wget или curl")
            sys.exit(1)
        
        print(f"✓ Модель Stable Diffusion скачана: {model_path}")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при скачивании модели: {e}")
        sys.exit(1)


def setup_stable_diffusion():
    """Настройка Stable Diffusion."""
    print("\nНастройка Stable Diffusion...")
    
    # Проверяем, есть ли папка stable-diffusion-webui
    sd_dir = Path("stable-diffusion-webui")
    if not sd_dir.exists():
        print("Клонирование репозитория Stable Diffusion WebUI...")
        try:
            subprocess.run(["git", "clone", "https://github.com/AUTOMATIC1111/stable-diffusion-webui.git"], check=True)
            print("✓ Репозиторий Stable Diffusion WebUI клонирован")
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при клонировании репозитория: {e}")
            sys.exit(1)
    else:
        print("✓ Папка Stable Diffusion WebUI уже существует")
    
    # Устанавливаем зависимости для Stable Diffusion
    print("Установка зависимостей для Stable Diffusion...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "stable-diffusion-webui/requirements.txt"],
            check=True,
            cwd="stable-diffusion-webui"
        )
        print("✓ Зависимости для Stable Diffusion установлены")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке зависимостей для Stable Diffusion: {e}")
        sys.exit(1)
    
    # Скачиваем модель
    download_stable_diffusion_model()


def create_env_file():
    """Создание файла .env на основе .env.example."""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists() and env_example.exists():
        print("\nСоздание файла .env на основе .env.example...")
        shutil.copy(env_example, env_file)
        print("✓ Файл .env создан")
    elif env_file.exists():
        print("✓ Файл .env уже существует")
    else:
        print("Внимание: Файл .env.example не найден")


def main():
    """Основная функция установки зависимостей."""
    print("=" * 60)
    print("Установка зависимостей для Master of TG Ads")
    print("=" * 60)
    
    # Проверка требований
    check_python_version()
    check_git()
    check_docker_compose()
    check_nvidia_gpu()
    
    # Установка зависимостей
    install_python_dependencies()
    setup_stable_diffusion()
    create_env_file()
    
    print("\n" + "=" * 60)
    print("Установка зависимостей завершена!")
    print("=" * 60)
    print("\nДля запуска системы выполните:")
    print("  docker-compose up --build")
    print("\nИли для запуска без Docker:")
    print("  python run.py")


if __name__ == "__main__":
    main()
