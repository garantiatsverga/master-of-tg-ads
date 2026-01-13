from typing import Dict, Any
from agents.base_agent import BaseAgent
from colordebug import *
from PIL import Image
import torch
from diffusers import KandinskyV22Pipeline, KandinskyV22PriorPipeline, StableDiffusionUpscalePipeline
import asyncio
import tempfile
import uuid
import os
from pathlib import Path

class BannerDesignerAgent(BaseAgent):
    """
    Агент для генерации баннеров с локальным Kandinsky 2.2.
    Сохраняет изображения в директорию проекта.
    """
    
    def __init__(
        self,
        mcp_server=None,
        security_checker=None,
        metrics_collector=None,
        config: Dict[str, Any] = None
    ):
        super().__init__(
            name="BannerDesignerAgent",
            mcp_server=mcp_server,
            security_checker=security_checker,
            metrics_collector=metrics_collector
        )
        
        # Конфигурация генерации
        self.config = config or {
            'prior_model': "kandinsky-community/kandinsky-2-2-prior",
            'decoder_model': "kandinsky-community/kandinsky-2-2-decoder",
            'upscale_model': "stabilityai/stable-diffusion-x4-upscaler",
            'lowres_width': 640,
            'lowres_height': 360,
            'hires_width': 1920,
            'hires_height': 1080,
            'steps': 20,
            'upscale_steps': 20,
            'guidance_scale': 7.5
        }
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.prior_pipe = None
        self.decoder_pipe = None
        self.upscale_pipe = None
        
        # Определяем директорию для сохранения
        self.output_dir = Path.cwd() / "generated_banners"
        self.output_dir.mkdir(exist_ok=True)
        
        info(f"[{self.name}] Инициализирован на устройстве: {self.device}", exp=True)
        info(f"[{self.name}] Баннеры будут сохраняться в: {self.output_dir}", exp=True)
    
    def _register_agent_permissions(self):
        """Разрешения больше не нужны"""
        pass
    
    async def _load_models(self):
        """Загрузка моделей Kandinsky 2.2"""
        if self.prior_pipe is None or self.decoder_pipe is None:
            try:
                info(f"[{self.name}] Загрузка Prior модели: {self.config['prior_model']}", exp=True)
                self.prior_pipe = KandinskyV22PriorPipeline.from_pretrained(
                    self.config['prior_model'],
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    safety_checker=None,
                    requires_safety_checker=False
                )
                self.prior_pipe = self.prior_pipe.to(self.device)
                success(f"[{self.name}] Prior модель загружена", exp=True)
                
                info(f"[{self.name}] Загрузка Decoder модели: {self.config['decoder_model']}", exp=True)
                self.decoder_pipe = KandinskyV22Pipeline.from_pretrained(
                    self.config['decoder_model'],
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    safety_checker=None,
                    requires_safety_checker=False
                )
                self.decoder_pipe = self.decoder_pipe.to(self.device)
                success(f"[{self.name}] Decoder модель загружена", exp=True)
                
            except Exception as e:
                error(f"[{self.name}] Ошибка загрузки моделей Kandinsky: {e}", exp=True)
                raise
        
        if self.upscale_pipe is None and self.device == "cuda":
            try:
                info(f"[{self.name}] Загрузка апскейлера: {self.config['upscale_model']}", exp=True)
                self.upscale_pipe = StableDiffusionUpscalePipeline.from_pretrained(
                    self.config['upscale_model'],
                    torch_dtype=torch.float16,
                )
                self.upscale_pipe = self.upscale_pipe.to(self.device)
                success(f"[{self.name}] Апскейлер загружен", exp=True)
            except Exception as e:
                warning(f"[{self.name}] Не удалось загрузить апскейлер: {e}", exp=True)
                self.upscale_pipe = None
    
    async def _generate_image(self, prompt: str, negative_prompt: str = "") -> Image.Image:
        """Внутренний метод генерации изображения с использованием Kandinsky 2.2"""
        await self._load_models()
        
        # Отрицательный промпт для улучшения качества
        negative = negative_prompt or "blurry, low quality, watermark, text, ugly, deformed, noisy"
        
        loop = asyncio.get_event_loop()
        
        # Сначала получаем эмбеддинги от Prior модели
        prior_output = await loop.run_in_executor(
            None,
            lambda: self.prior_pipe(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=self.config['steps'],
                guidance_scale=self.config['guidance_scale']
            )
        )
        
        # Затем генерируем изображение с Decoder моделью
        image_embeddings = prior_output.image_embeddings
        negative_image_embeddings = prior_output.negative_image_embeddings
        
        low_res = await loop.run_in_executor(
            None,
            lambda: self.decoder_pipe(
                image_embeddings=image_embeddings,
                negative_image_embeddings=negative_image_embeddings,
                num_inference_steps=self.config['steps'],
                guidance_scale=self.config['guidance_scale'],
                height=self.config['lowres_height'],
                width=self.config['lowres_width']
            ).images[0]
        )
        
        return low_res
    
    async def _upscale_image(self, image: Image.Image) -> Image.Image:
        """Апскейл изображения до HD с обработкой ошибок памяти"""
        if self.upscale_pipe is None:
            # Простой ресайз если апскейлер не доступен
            return image.resize(
                (self.config['hires_width'], self.config['hires_height']),
                Image.Resampling.LANCZOS
            )
        
        try:
            loop = asyncio.get_event_loop()
            upscaled = await loop.run_in_executor(
                None,
                lambda: self.upscale_pipe(
                    prompt="high quality, detailed, sharp, professional",
                    image=image,
                    num_inference_steps=min(self.config['upscale_steps'], 15),  # Меньше шагов для экономии памяти
                    guidance_scale=7.5
                ).images[0]
            )
            
            # Обрезаем до нужного размера
            if upscaled.size != (self.config['hires_width'], self.config['hires_height']):
                upscaled = upscaled.resize(
                    (self.config['hires_width'], self.config['hires_height']),
                    Image.Resampling.LANCZOS
            )
            
            return upscaled
            
        except torch.OutOfMemoryError:
            warning(f"[{self.name}] Не хватает GPU памяти для апскейла, использую простой ресайз", exp=True)
            return image.resize(
                (self.config['hires_width'], self.config['hires_height']),
                Image.Resampling.LANCZOS
            )
        
        except Exception as e:
            error(f"[{self.name}] Ошибка апскейла: {e}", exp=True)
            return image.resize(
                (self.config['hires_width'], self.config['hires_height']),
                Image.Resampling.LANCZOS
            )
    
    def validate(self, payload: Dict[str, Any]) -> None:
        """Проверяем наличие графического промпта"""
        super().validate(payload)
        
        if "target_image_prompt" not in payload:
            raise ValueError(
                f"[{self.name}] Ошибка: В контексте отсутствует 'target_image_prompt'"
            )
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Основной процесс генерации баннера для смартфона
        Сохраняет в директорию проекта, использует английский промпт
        """
        # Берем английский промпт если есть, иначе русский
        image_prompt = context.get("full_image_prompt_en", 
                                  context.get("target_image_prompt", ""))
        
        product_name = context.get("meta", {}).get("product", "product")
        product_type = context.get("meta", {}).get("product_type", "").lower()
        
        # Определяем тип продукта для специализированного промпта
        is_smartphone = any(word in (product_name + " " + product_type).lower() 
                           for word in ["смартфон", "smartphone", "телефон", "phone"])
        
        if is_smartphone:
            # Улучшенный промпт для смартфона на английском
            enhanced_prompt = f"""Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."""
            
            # Отрицательный промпт чтобы избежать нежелательных элементов
            negative_prompt = """Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."""
            
            info(f"[{self.name}] Генерация баннера для СМАРТФОНА: {product_name}", exp=True)
            
        else:
            # Общий промпт для других продуктов
            enhanced_prompt = f"""
            professional product photography of {product_name},
            clean white background, studio lighting,
            sharp focus, highly detailed, commercial advertisement,
            minimalist design, professional photo
            """
            
            negative_prompt = "blurry, low quality, deformed, ugly, text, watermark"
            info(f"[{self.name}] Генерация баннера для: {product_name}", exp=True)
        
        # Укорачиваем промпт для безопасности
        short_prompt = " ".join(enhanced_prompt.strip().split()[:30])
        
        try:
            # 1. Генерация изображения с улучшенным промптом
            info(f"[{self.name}] Промпт: {short_prompt[:80]}...", exp=True)
            low_res_image = await self._generate_image(
                prompt=enhanced_prompt.strip(),
                negative_prompt=negative_prompt.strip()
            )
            success(f"[{self.name}] Изображение сгенерировано (640x360)", exp=True)
            
            # 2. Апскейл до HD
            info(f"[{self.name}] Апскейл до 1920x1080...", exp=True)
            high_res_image = await self._upscale_image(low_res_image)
            success(f"[{self.name}] Апскейл завершен", exp=True)
            
            # 3. Подготовка к сохранению в проект
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # Безопасное имя файла
            safe_name = "".join(c for c in product_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')[:40]
            
            # Создаем директорию для баннеров
            project_root = Path(__file__).parent.parent.parent
            banners_dir = project_root / "generated_banners"
            banners_dir.mkdir(exist_ok=True)
            
            # 4. Сохраняем основной баннер
            banner_filename = f"banner_{safe_name}_{timestamp}.png"
            banner_path = banners_dir / banner_filename
            
            # Сохраняем с максимальным качеством
            high_res_image.save(banner_path, "PNG", optimize=True, quality=95)
            
            # 5. Сохраняем миниатюру для превью
            thumb_filename = f"thumb_{safe_name}_{timestamp}.jpg"
            thumb_path = banners_dir / thumb_filename
            thumbnail = high_res_image.resize((400, 225), Image.Resampling.LANCZOS)
            thumbnail.save(thumb_path, "JPEG", quality=85, optimize=True)
            
            # 6. Также сохраняем low-res версию для быстрого просмотра
            lowres_filename = f"lowres_{safe_name}_{timestamp}.jpg"
            lowres_path = banners_dir / lowres_filename
            low_res_image.save(lowres_path, "JPEG", quality=80, optimize=True)
            
            # 7. Сохраняем промпт в текстовый файл
            prompt_filename = f"prompt_{safe_name}_{timestamp}.txt"
            prompt_path = banners_dir / prompt_filename
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(f"Product: {product_name}\n")
                f.write(f"Type: {product_type}\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Prompt:\n{enhanced_prompt}\n")
                f.write(f"\nNegative Prompt:\n{negative_prompt}\n")
            
            # 8. Возвращаем результат в контекст
            context["banner_url"] = f"file://{banner_path}"
            context["banner_local_path"] = str(banner_path)
            context["banner_thumbnail"] = str(thumb_path)
            context["banner_lowres"] = str(lowres_path)
            context["banner_size"] = "1920x1080"
            context["banner_generated"] = True
            context["banner_filename"] = banner_filename
            context["banner_prompt"] = short_prompt
            context["banner_prompt_file"] = str(prompt_path)
            context["banner_timestamp"] = timestamp
            context["banner_directory"] = str(banners_dir)
            
            # 9. Логируем успех
            success(f"[{self.name}] Баннер сохранен успешно!", exp=True)
            info(f"[{self.name}] Основной файл: {banner_path}", exp=True)
            info(f"[{self.name}] Миниатюра: {thumb_path}", exp=True)
            info(f"[{self.name}] Low-res: {lowres_path}", exp=True)
            info(f"[{self.name}] Промпт: {prompt_path}", exp=True)
            
            # 10. Показываем превью если в Colab
            try:
                from IPython.display import display, Image as IPImage, Markdown
                
                # Показываем миниатюру
                display(thumbnail)
                
                # Показываем информацию
                print(f"\n{'_'*30}")
                info(f"БАаннер успешно создан")
                info(f"{'_'*30}")
                info(f"Продукт: {product_name}")
                info(f"Папка: {banners_dir}")
                info(f"Основной: {banner_filename}")
                info(f"Миниатюра: {thumb_filename}")
                info(f"Low-res: {lowres_filename}")
                info(f"Промпт: {prompt_filename}")
                print(f"{'_'*30}")
                
            except ImportError:
                # Просто выводим пути
                info(f"\nФайлы сохранены в: {banners_dir}")
                info(f"Баннер: {banner_path}")
                info(f"Миниатюра: {thumb_path}")
            
        except Exception as e:
            error(f"[{self.name}] Ошибка генерации баннера: {e}", exp=True)
            import traceback
            traceback.print_exc()
            
            # Создаем заглушку с информацией об ошибке
            import time
            timestamp = int(time.time())
            project_root = Path(__file__).parent.parent.parent
            banners_dir = project_root / "generated_banners"
            banners_dir.mkdir(exist_ok=True)
            
            placeholder_path = banners_dir / f"error_{timestamp}.png"
            
            # Создаем placeholder
            placeholder = Image.new('RGB', (1920, 1080), color='#1a1a2e')
            from PIL import ImageDraw, ImageFont
            
            draw = ImageDraw.Draw(placeholder)
            
            # Пытаемся использовать шрифт
            try:
                font_large = ImageFont.truetype("arial.ttf", 60)
                font_small = ImageFont.truetype("arial.ttf", 30)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Текст ошибки
            error_text = f"Ошибка генерации: {product_name}"
            draw.text((960, 400), error_text, fill="white", font=font_large, anchor="mm")
            draw.text((960, 500), str(e)[:100], fill="#ff6b6b", font=font_small, anchor="mm")
            draw.text((960, 600), "Проверьте промпт и параметры", fill="#4ecdc4", font=font_small, anchor="mm")
            
            placeholder.save(placeholder_path, "PNG")
            
            # Возвращаем информацию об ошибке
            context["banner_url"] = f"file://{placeholder_path}"
            context["banner_local_path"] = str(placeholder_path)
            context["banner_generated"] = False
            context["banner_error"] = str(e)
            context["banner_error_trace"] = traceback.format_exc()
        
        return context