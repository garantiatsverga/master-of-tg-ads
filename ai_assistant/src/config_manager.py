import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
import simdjson as sd

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from colordebug import info, warning, error
from ai_assistant.src.observability.logging_setup import log_configuration

class ConfigManager:
    """Менеджер конфигурации"""
    
    BANNER_WIDTH = 1920
    BANNER_HEIGHT = 1080
    BANNER_RATIO = "16:9"
    
    @staticmethod
    def load_config(path: str = None, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Загрузка конфигурации из YAML-файла"""
        if path is None:
            path = "config.yaml"
            
        config_paths = [
            path,
            os.path.join(project_root, "config", path),
            os.path.join(project_root, path),
        ]
        
        if default is None:
            default = ConfigManager.get_default_config()
        
        loaded_config = None
        loaded_from = None
        
        for config_path in config_paths:
            try:
                if os.path.exists(config_path):
                    info(f"Попытка загрузки конфигурации из {config_path}", exp=True)
                    
                    with open(config_path, 'rb') as f:
                        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                            loaded_config = yaml.safe_load(f)
                        else:
                            loaded_config = sd.load(f)
                    
                    info(f"Успешно загружена конфигурация из {config_path}", exp=True)
                    loaded_from = config_path
                    break
                    
            except Exception as e:
                warning(f"Ошибка загрузки конфигурации {config_path}: {e}", exp=True)
                continue
        
        if loaded_config:
            ConfigManager._deep_update(default, loaded_config)
            info(f"Конфигурация загружена из {loaded_from}", exp=True)
        else:
            warning(f"Конфигурация {path} не найдена, используются значения по умолчанию", exp=True)
        
        ConfigManager._apply_banner_constants(default)
        log_configuration(default)
        ConfigManager._validate_config(default)
        
        return default
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Конфигурация по умолчанию"""
        return {
            'system': {
                'debug': os.getenv('DEBUG', 'false').lower() == 'true',
                'log_level': os.getenv('LOG_LEVEL', 'info'),
                'temp_dir': os.getenv('TEMP_DIR', './tmp'),
                'max_workers': int(os.getenv('MAX_WORKERS', '1')),
            },
            
            'agents': {
                'workflow': ['prompt_agent', 'banner_designer', 'copywriter', 'qa_compliance'],
                'timeout_seconds': {
                    'prompt_agent': 45,
                    'banner_designer': 300,
                    'copywriter': 90,
                    'qa_compliance': 30,
                    'total': 600
                },
                'retry_attempts': 3,
            },
            
            'llm': {
                'gigachat': {
                    'provider': 'gigachat',
                    'api_key': os.getenv('GIGACHAT_API_KEY', ''),
                    'base_url': os.getenv('GIGACHAT_BASE_URL', 'https://gigachat.devices.sberbank.ru/api/v1'),
                    'temperature': float(os.getenv('GIGACHAT_TEMPERATURE', '0.7')),
                    'max_tokens': int(os.getenv('GIGACHAT_MAX_TOKENS', '1000')),
                    'timeout': int(os.getenv('GIGACHAT_TIMEOUT', '120')),
                }
            },
            
            'stable_diffusion': {
                'provider': 'local',
                'model': os.getenv('SD_MODEL', 'runwayml/stable-diffusion-v1-5'),
                'device': os.getenv('SD_DEVICE', 'cuda'),
                'base_url': os.getenv('SD_BASE_URL', 'http://localhost:7860'),
                'width': ConfigManager.BANNER_WIDTH,
                'height': ConfigManager.BANNER_HEIGHT,
                'steps': int(os.getenv('SD_STEPS', '25')),
                'timeout': int(os.getenv('SD_TIMEOUT', '300')),
            },
            
            'telegram_ads': {
                'specifications': {
                    'max_text_length': 160,
                    'max_file_size_mb': 5,
                    'aspect_ratios': [ConfigManager.BANNER_RATIO],
                },
                
                'rule_files': {
                    'telegram_rules': './prompt_engine/telegram_rules.json',
                    'banned_patterns': './prompt_engine/banned_patterns.json'
                },
                
                'validation': {
                    'enable_automated_check': True,
                    'manual_review_threshold': 0.7
                }
            },
            
            'image_processing': {
                'text_overlay': {
                    'font_path': os.getenv('FONT_PATH', './assets/fonts/Roboto-Bold.ttf'),
                    'font_size': int(os.getenv('FONT_SIZE', '56')),
                },
                'resize': {
                    'target_width': ConfigManager.BANNER_WIDTH,
                    'target_height': ConfigManager.BANNER_HEIGHT,
                }
            }
        }
    
    @staticmethod
    def _apply_banner_constants(config: Dict[str, Any]) -> None:
        """Применяет константы размеров баннеров"""
        if 'stable_diffusion' in config:
            config['stable_diffusion']['width'] = ConfigManager.BANNER_WIDTH
            config['stable_diffusion']['height'] = ConfigManager.BANNER_HEIGHT
        
        if 'image_processing' in config and 'resize' in config['image_processing']:
            config['image_processing']['resize']['target_width'] = ConfigManager.BANNER_WIDTH
            config['image_processing']['resize']['target_height'] = ConfigManager.BANNER_HEIGHT
    
    @staticmethod
    def _deep_update(original: Dict, update: Dict) -> None:
        """Рекурсивное обновление словаря"""
        for key, value in update.items():
            if key in original and isinstance(original[key], dict) and isinstance(value, dict):
                ConfigManager._deep_update(original[key], value)
            else:
                original[key] = value
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]) -> bool:
        """Базовая валидация конфигурации"""
        try:
            # Проверка обязательных полей
            if not config['llm']['gigachat']['api_key']:
                warning("API-ключ GigaChat не установлен", exp=True)
            
            # Проверка существования файла правил
            rules_path = config['telegram_ads']['rule_files']['telegram_rules']
            if not os.path.exists(rules_path):
                warning(f"Файл правил Telegram не найден: {rules_path}", exp=True)
            
            return True
        except Exception as e:
            error(f"Ошибка валидации конфигурации: {e}", exp=True)
            return False
    
    @staticmethod
    def get_security_rules_path(config: Dict[str, Any]) -> str:
        """Получение пути к файлу правил Telegram"""
        return config['telegram_ads']['rule_files']['telegram_rules']