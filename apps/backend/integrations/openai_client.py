"""
OpenAI Integration Client
"""
import asyncio
from typing import Optional, List, Dict, Any, Union
from openai import AsyncOpenAI
import openai
from ..core.settings import settings
from ..core.logging import logger


class OpenAIClient:
    """Client for OpenAI API integration"""
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.default_model = getattr(settings, 'OPENAI_DEFAULT_MODEL', 'gpt-4')
        self.max_retries = 3
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Any:
        """Create a chat completion"""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        model = model or self.default_model
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit error: {str(e)}")
            raise
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling OpenAI: {str(e)}")
            raise
    
    async def create_embedding(
        self,
        text: Union[str, List[str]],
        model: str = "text-embedding-ada-002"
    ) -> List[float]:
        """Create embeddings for text"""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        try:
            if isinstance(text, str):
                text = [text]
            
            response = await self.client.embeddings.create(
                model=model,
                input=text
            )
            
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error creating embeddings: {str(e)}")
            raise
    
    async def moderate_content(self, text: str) -> Dict[str, Any]:
        """Check content for policy violations"""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        try:
            response = await self.client.moderations.create(input=text)
            return response.results[0].dict()
        except Exception as e:
            logger.error(f"Error moderating content: {str(e)}")
            raise
    
    async def transcribe_audio(
        self,
        audio_file: bytes,
        model: str = "whisper-1",
        language: Optional[str] = None,
        **kwargs
    ) -> str:
        """Transcribe audio to text"""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        try:
            response = await self.client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                language=language,
                **kwargs
            )
            return response.text
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise
    
    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        n: int = 1,
        model: str = "dall-e-3"
    ) -> List[str]:
        """Generate images from text prompt"""
        if not self.client:
            raise ValueError("OpenAI API key not configured")
        
        try:
            response = await self.client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                n=n
            )
            return [image.url for image in response.data]
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            raise
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        # Rough estimation: ~4 characters per token
        return len(text) // 4
    
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None
    ) -> float:
        """Estimate cost for API usage"""
        model = model or self.default_model
        
        # Pricing as of 2024 (per 1K tokens)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "gpt-4-vision-preview": {"input": 0.01, "output": 0.03}
        }
        
        if model not in pricing:
            return 0.0
        
        input_cost = (input_tokens / 1000) * pricing[model]["input"]
        output_cost = (output_tokens / 1000) * pricing[model]["output"]
        
        return input_cost + output_cost