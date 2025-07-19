"""
AI Vision Service for image analysis and processing
"""
import base64
import io
from typing import Optional, List, Dict, Any, Union
from PIL import Image
import numpy as np
from ..core.logging import logger
from ..integrations.openai_client import OpenAIClient
from ..integrations.anthropic_client import AnthropicClient
from ..core.settings import settings


class AIVisionService:
    """Service for AI-powered image analysis and vision tasks"""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.anthropic_client = AnthropicClient()
        self.default_provider = getattr(settings, 'DEFAULT_VISION_PROVIDER', 'openai')
    
    async def analyze_image(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        provider: Optional[str] = None,
        max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """
        Analyze an image using AI vision models
        
        Args:
            image_data: Image bytes or base64 string
            prompt: Analysis prompt
            provider: AI provider ('openai' or 'anthropic')
            max_tokens: Maximum response tokens
        
        Returns:
            Analysis results
        """
        try:
            provider = provider or self.default_provider
            
            # Convert image data to base64 if needed
            if isinstance(image_data, bytes):
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            else:
                image_base64 = image_data
            
            if provider == 'openai':
                return await self._analyze_with_openai(image_base64, prompt, max_tokens)
            elif provider == 'anthropic':
                return await self._analyze_with_anthropic(image_base64, prompt, max_tokens)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        except Exception as e:
            logger.error(f"Image analysis failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _analyze_with_openai(
        self,
        image_base64: str,
        prompt: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Analyze image using OpenAI Vision"""
        try:
            response = await self.openai_client.chat_completion(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                model="gpt-4-vision-preview",
                max_tokens=max_tokens
            )
            
            return {
                "success": True,
                "provider": "openai",
                "analysis": response.choices[0].message.content,
                "usage": response.usage.dict() if hasattr(response, 'usage') else None
            }
        except Exception as e:
            logger.error(f"OpenAI vision analysis failed: {str(e)}")
            raise
    
    async def _analyze_with_anthropic(
        self,
        image_base64: str,
        prompt: str,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Analyze image using Claude Vision"""
        try:
            response = await self.anthropic_client.create_message(
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }],
                model="claude-3-opus-20240229",
                max_tokens=max_tokens
            )
            
            return {
                "success": True,
                "provider": "anthropic",
                "analysis": response.content[0].text,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }
        except Exception as e:
            logger.error(f"Claude vision analysis failed: {str(e)}")
            raise
    
    async def extract_text_from_image(
        self,
        image_data: Union[bytes, str],
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract text (OCR) from an image"""
        prompt = "Extract all text from this image. Format the text to maintain the original layout as much as possible."
        return await self.analyze_image(image_data, prompt, provider)
    
    async def describe_image(
        self,
        image_data: Union[bytes, str],
        detail_level: str = "medium",
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a description of an image"""
        detail_prompts = {
            "brief": "Provide a brief one-sentence description of this image.",
            "medium": "Describe this image in 2-3 sentences, covering the main subjects and context.",
            "detailed": "Provide a detailed description of this image, including subjects, colors, composition, and any text or notable details."
        }
        
        prompt = detail_prompts.get(detail_level, detail_prompts["medium"])
        return await self.analyze_image(image_data, prompt, provider)
    
    async def analyze_roofing_image(
        self,
        image_data: Union[bytes, str],
        analysis_type: str = "damage",
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Specialized analysis for roofing images"""
        prompts = {
            "damage": """Analyze this roof image and identify:
1. Any visible damage (missing shingles, cracks, holes, water damage)
2. The severity of each issue (minor, moderate, severe)
3. Recommended repairs
4. Estimated urgency of repairs""",
            
            "material": """Analyze this roof image and identify:
1. The roofing material type
2. Approximate age/condition
3. Color and style
4. Any special features or characteristics""",
            
            "measurement": """Analyze this roof image and estimate:
1. Visible roof sections and their approximate dimensions
2. Number of roof facets/planes
3. Any special features (dormers, valleys, ridges)
4. Notes about areas that would need field verification"""
        }
        
        prompt = prompts.get(analysis_type, prompts["damage"])
        return await self.analyze_image(image_data, prompt, provider)
    
    async def compare_images(
        self,
        image1_data: Union[bytes, str],
        image2_data: Union[bytes, str],
        comparison_prompt: str = "Compare these two images and describe the differences.",
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare two images"""
        try:
            provider = provider or self.default_provider
            
            # Convert to base64
            if isinstance(image1_data, bytes):
                image1_base64 = base64.b64encode(image1_data).decode('utf-8')
            else:
                image1_base64 = image1_data
                
            if isinstance(image2_data, bytes):
                image2_base64 = base64.b64encode(image2_data).decode('utf-8')
            else:
                image2_base64 = image2_data
            
            if provider == 'openai':
                response = await self.openai_client.chat_completion(
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": comparison_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image1_base64}"}
                            },
                            {
                                "type": "image_url", 
                                "image_url": {"url": f"data:image/jpeg;base64,{image2_base64}"}
                            }
                        ]
                    }],
                    model="gpt-4-vision-preview"
                )
                
                return {
                    "success": True,
                    "provider": "openai",
                    "comparison": response.choices[0].message.content
                }
            else:
                # Anthropic format
                response = await self.anthropic_client.create_message(
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image1_base64
                                }
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image2_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": comparison_prompt
                            }
                        ]
                    }],
                    model="claude-3-opus-20240229"
                )
                
                return {
                    "success": True,
                    "provider": "anthropic",
                    "comparison": response.content[0].text
                }
                
        except Exception as e:
            logger.error(f"Image comparison failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def preprocess_image(
        self,
        image_data: bytes,
        max_size: tuple = (1920, 1080),
        quality: int = 85
    ) -> bytes:
        """Preprocess image for optimal API usage"""
        try:
            # Open image
            image = Image.open(io.BytesIO(image_data))
            
            # Convert RGBA to RGB if needed
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            
            # Resize if larger than max_size
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}")
            raise


# Create singleton instance
ai_vision_service = AIVisionService()


# Convenience functions
async def analyze_image(*args, **kwargs):
    return await ai_vision_service.analyze_image(*args, **kwargs)

async def extract_text_from_image(*args, **kwargs):
    return await ai_vision_service.extract_text_from_image(*args, **kwargs)

async def describe_image(*args, **kwargs):
    return await ai_vision_service.describe_image(*args, **kwargs)

async def analyze_roofing_image(*args, **kwargs):
    return await ai_vision_service.analyze_roofing_image(*args, **kwargs)