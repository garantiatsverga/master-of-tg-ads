import torch
from diffusers import StableDiffusionPipeline, StableDiffusionUpscalePipeline
from PIL import Image
from typing import Dict, Any
import asyncio
from ai_assistant.src.config_manager import ConfigManager
from colordebug import info, warning, error

class StableDiffusionAdapter:
    """Полностью локальный адаптер для segmind/tiny-sd с апскейлом"""
    
    def __init__(self, config: Dict[str, Any] = None):
        if not config:
            config = ConfigManager.load_config()
        self.config = config['stable_diffusion']
        
        # Настройки для segmind/tiny-sd (маленькая быстрая модель)
        self.base_model = "segmind/tiny-sd"  # Легкая модель для быстрой генерации
        self.upscale_model = "stabilityai/stable-diffusion-x4-upscaler"  # Для апскейла
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        info(f"Используем устройство: {self.device}", exp=True)
        
        # Инициализируем пайплайны асинхронно
        self.pipe = None
        self.upscale_pipe = None
    
    async def _load_models(self):
        """Асинхронная загрузка моделей"""
        if self.pipe is None:
            try:
                info(f"Загрузка базовой модели: {self.base_model}", exp=True)
                
                # Загружаем маленькую быструю модель
                self.pipe = StableDiffusionPipeline.from_pretrained(
                    self.base_model,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    safety_checker=None,  # Отключаем для скорости
                    requires_safety_checker=False
                )
                
                # Оптимизации
                if self.device == "cuda":
                    self.pipe.enable_attention_slicing()
                    # Не используем xformers если не установлен
                    try:
                        self.pipe.enable_xformers_memory_efficient_attention()
                    except:
                        pass
                
                self.pipe = self.pipe.to(self.device)
                info(f"Базовая модель загружена на {self.device}", exp=True)
                
            except Exception as e:
                error(f"Ошибка загрузки базовой модели: {e}", exp=True)
                raise
        
        if self.upscale_pipe is None and self.device == "cuda":
            try:
                info(f"Загрузка модели апскейла: {self.upscale_model}", exp=True)
                self.upscale_pipe = StableDiffusionUpscalePipeline.from_pretrained(
                    self.upscale_model,
                    torch_dtype=torch.float16,
                )
                self.upscale_pipe = self.upscale_pipe.to(self.device)
                info("Модель апскейла загружена", exp=True)
            except Exception as e:
                warning(f"Не удалось загрузить модель апскейла: {e}", exp=True)
                self.upscale_pipe = None
    
    async def generate_image(self, prompt: str,
                           negative_prompt: str = None,
                           steps: int = None,
                           width: int = 640,    # Уменьшаем для скорости
                           height: int = 360) -> Image.Image:
        """Генерация изображения в низком разрешении"""
        
        await self._load_models()
        
        # Параметры для tiny-sd
        actual_steps = steps or 20  # Меньше шагов для скорости
        guidance_scale = 7.0
        
        info(f"Генерация {width}x{height} в {actual_steps} шагов", exp=True)
        
        try:
            # Запускаем генерацию в отдельном потоке
            loop = asyncio.get_event_loop()
            image = await loop.run_in_executor(
                None,
                lambda: self.pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt or "",
                    num_inference_steps=actual_steps,
                    guidance_scale=guidance_scale,
                    width=width,
                    height=height,
                    num_images_per_prompt=1
                ).images[0]
            )
            
            # Сохраняем метаданные
            image.info['sd_params'] = {
                'prompt': prompt,
                'negative_prompt': negative_prompt,
                'steps': actual_steps,
                'model': self.base_model,
                'size': f"{width}x{height}"
            }
            
            info(f"Изображение сгенерировано: {width}x{height}", exp=True)
            return image
            
        except Exception as e:
            error(f"Ошибка генерации: {e}", exp=True)
            # Возвращаем черное изображение как заглушку
            return Image.new('RGB', (width, height), color='black')
    
    async def upscale_image(self, image: Image.Image, 
                          target_width: int = 1920, 
                          target_height: int = 1080) -> Image.Image:
        """Апскейл изображения"""
        
        await self._load_models()
        
        if self.upscale_pipe is None:
            warning("Модель апскейла недоступна, используем простой ресайз", exp=True)
            return image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Для апскейла нужен промпт, используем общий
        upscale_prompt = "high quality, detailed, sharp"
        
        try:
            info(f"Апскейл до {target_width}x{target_height}", exp=True)
            
            loop = asyncio.get_event_loop()
            upscaled = await loop.run_in_executor(
                None,
                lambda: self.upscale_pipe(
                    prompt=upscale_prompt,
                    image=image,
                    num_inference_steps=20,
                    guidance_scale=7.5
                ).images[0]
            )
            
            # Обрезаем до нужного соотношения сторон если нужно
            if upscaled.size != (target_width, target_height):
                upscaled = upscaled.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            info("Апскейл завершен", exp=True)
            return upscaled
            
        except Exception as e:
            error(f"Ошибка апскейла: {e}", exp=True)
            return image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    async def img2img(self, init_image: Image.Image, 
                     prompt: str, 
                     strength: float = 0.75) -> Image.Image:
        """Img2Img преобразование"""
        await self._load_models()
        
        try:
            # Ресайзим для совместимости с моделью
            init_image = init_image.resize((512, 512), Image.Resampling.LANCZOS)
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.pipe(
                    prompt=prompt,
                    image=init_image,
                    strength=strength,
                    num_inference_steps=25,
                    guidance_scale=7.5
                ).images[0]
            )
            
            return result
            
        except Exception as e:
            error(f"Ошибка img2img: {e}", exp=True)
            return init_image