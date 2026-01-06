import aiohttp
import base64
import simdjson as sd
from io import BytesIO
from PIL import Image
from typing import Dict, Any
from config_manager import ConfigManager

class StableDiffusionAdapter:
    """Адаптер для локального Stable Diffusion 1.5 через AUTOMATIC1111 API"""
    
    def __init__(self, config: Dict[str, Any] = None):
        if not config:
            config = ConfigManager.load_config()
        self.config = config['stable_diffusion']
        
    async def generate_image(self, prompt: str, 
                           negative_prompt: str = None,
                           steps: int = None) -> Image.Image:
        """Генерация изображения через SD"""
        
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt or self.config.get('negative_prompt', ''),
            "steps": steps or self.config.get('steps', 25),
            "width": self.config['width'],   # 1920
            "height": self.config['height'], # 1080
            "cfg_scale": self.config.get('cfg_scale', 7.5),
            "sampler_name": self.config.get('sampler', 'Euler a'),
            "batch_size": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config['base_url']}/sdapi/v1/txt2img",
                    json=payload,
                    timeout=self.config.get('timeout', 600)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"SD-ошибка: {response.status} - {error_text}")
                    
                    result = await response.json()
                    
                    # Извлекаем base64 изображение
                    image_data = base64.b64decode(result['images'][0])
                    
                    # Создаем PIL Image
                    image = Image.open(BytesIO(image_data))
                    
                    # Сохраняем параметры генерации в метаданные
                    image.info['sd_params'] = {
                        'prompt': prompt,
                        'negative_prompt': negative_prompt,
                        'steps': payload['steps'],
                        'seed': result['parameters'].get('seed', -1)
                    }
                    
                    return image
                    
        except Exception as e:
            # Логируем ошибку
            from colordebug import error
            error(f"Ошибка генерации: {e}")
            raise

    async def upscale_image(self, image: Image.Image, scale_factor: float = 2.0) -> Image.Image:
        """Апскейл изображения через SD"""
        # Конвертируем PIL Image в base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        payload = {
            "image": img_str,
            "upscaling_resize": scale_factor,
            "upscaler_1": self.config.get('upscaler', 'ESRGAN_4x')
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.config['base_url']}/sdapi/v1/extra-single-image",
                json=payload,
                timeout=self.config.get('timeout', 120)
            ) as response:
                result = await response.json()
                image_data = base64.b64decode(result['image'])
                return Image.open(BytesIO(image_data))

    async def img2img(self, init_image: Image.Image, 
                     prompt: str, 
                     denoising_strength: float = 0.75) -> Image.Image:
        """Img2Img преобразование"""
        buffered = BytesIO()
        init_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        payload = {
            "init_images": [img_str],
            "prompt": prompt,
            "denoising_strength": denoising_strength,
            "steps": self.config.get('steps', 25),
            "width": self.config['width'],
            "height": self.config['height']
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.config['base_url']}/sdapi/v1/img2img",
                json=payload,
                timeout=self.config.get('timeout', 300)
            ) as response:
                result = await response.json()
                image_data = base64.b64decode(result['images'][0])
                return Image.open(BytesIO(image_data))