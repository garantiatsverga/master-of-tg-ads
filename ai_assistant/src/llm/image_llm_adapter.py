import torch
from diffusers import KandinskyV22Pipeline, KandinskyV22PriorPipeline, StableDiffusionUpscalePipeline
from PIL import Image
from typing import Dict, Any
import asyncio
from ai_assistant.src.config_manager import ConfigManager
from colordebug import info, warning, error

class KandinskyAdapter:
    """Полностью локальный адаптер для Kandinsky 2.2 (float16) с апскейлом"""
    
    def __init__(self, config: Dict[str, Any] = None):
        if not config:
            config = ConfigManager.load_config()
        self.config = config.get('stable_diffusion', {})
        
        # Настройки для Kandinsky 2.2
        self.prior_model = "kandinsky-community/kandinsky-2-2-prior"
        self.decoder_model = "kandinsky-community/kandinsky-2-2-decoder"
        self.upscale_model = "stabilityai/stable-diffusion-x4-upscaler"  # Для апскейла
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        info(f"Используем устройство: {self.device}", exp=True)
        
        # Инициализируем пайплайны асинхронно
        self.prior_pipe = None
        self.decoder_pipe = None
        self.upscale_pipe = None
    
    async def _load_models(self):
        """Асинхронная загрузка моделей Kandinsky 2.2"""
        if self.prior_pipe is None or self.decoder_pipe is None:
            try:
                info(f"Загрузка Prior модели: {self.prior_model}", exp=True)
                self.prior_pipe = KandinskyV22PriorPipeline.from_pretrained(
                    self.prior_model,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    safety_checker=None,
                    requires_safety_checker=False
                )
                self.prior_pipe = self.prior_pipe.to(self.device)
                info(f"Prior модель загружена на {self.device}", exp=True)
                
                info(f"Загрузка Decoder модели: {self.decoder_model}", exp=True)
                self.decoder_pipe = KandinskyV22Pipeline.from_pretrained(
                    self.decoder_model,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    safety_checker=None,
                    requires_safety_checker=False
                )
                self.decoder_pipe = self.decoder_pipe.to(self.device)
                info(f"Decoder модель загружена на {self.device}", exp=True)
                
            except Exception as e:
                error(f"Ошибка загрузки моделей Kandinsky: {e}", exp=True)
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
                           width: int = 640,
                           height: int = 360) -> Image.Image:
        """Генерация изображения с использованием Kandinsky 2.2"""
        
        await self._load_models()
        
        # Параметры для Kandinsky 2.2
        actual_steps = steps or 20
        guidance_scale = 7.0
        
        info(f"Генерация {width}x{height} в {actual_steps} шагов", exp=True)
        
        try:
            # Запускаем генерацию в отдельном потоке
            loop = asyncio.get_event_loop()
            
            # Сначала получаем эмбеддинги от Prior модели
            prior_output = await loop.run_in_executor(
                None,
                lambda: self.prior_pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt or "",
                    num_inference_steps=actual_steps,
                    guidance_scale=guidance_scale
                )
            )
            
            # Затем генерируем изображение с Decoder моделью
            image_embeddings = prior_output.image_embeddings
            negative_image_embeddings = prior_output.negative_image_embeddings
            
            image = await loop.run_in_executor(
                None,
                lambda: self.decoder_pipe(
                    image_embeddings=image_embeddings,
                    negative_image_embeddings=negative_image_embeddings,
                    num_inference_steps=actual_steps,
                    guidance_scale=guidance_scale,
                    height=height,
                    width=width
                ).images[0]
            )
            
            # Сохраняем метаданные
            image.info['sd_params'] = {
                'prompt': prompt,
                'negative_prompt': negative_prompt,
                'steps': actual_steps,
                'model': "Kandinsky 2.2",
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
                lambda: self.decoder_pipe(
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