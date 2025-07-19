"""
Speech-to-Text and Text-to-Speech Service
"""
import base64
import io
from typing import Optional, Dict, Any, Union
from ..core.logging import logger
from ..integrations.openai_client import OpenAIClient
from ..core.settings import settings


class SpeechToTextService:
    """Service for speech recognition and synthesis"""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.supported_audio_formats = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']
    
    async def transcribe(
        self,
        audio_data: Union[bytes, str],
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        response_format: str = "json",
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio bytes or base64 string
            language: Language code (e.g., 'en', 'es')
            prompt: Optional prompt to guide transcription
            response_format: 'json', 'text', 'srt', 'verbose_json', 'vtt'
            temperature: Sampling temperature (0-1)
        
        Returns:
            Transcription result
        """
        try:
            # Convert base64 to bytes if needed
            if isinstance(audio_data, str):
                audio_data = base64.b64decode(audio_data)
            
            # Use OpenAI Whisper
            result = await self.openai_client.transcribe_audio(
                audio_file=audio_data,
                language=language,
                prompt=prompt,
                response_format=response_format,
                temperature=temperature
            )
            
            return {
                'success': True,
                'text': result if response_format == 'text' else result.get('text', ''),
                'language': language,
                'format': response_format,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Speech transcription failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def translate(
        self,
        audio_data: Union[bytes, str],
        prompt: Optional[str] = None,
        response_format: str = "json",
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Translate audio to English text
        
        Args:
            audio_data: Audio bytes or base64 string
            prompt: Optional prompt to guide translation
            response_format: 'json', 'text', 'srt', 'verbose_json', 'vtt'
            temperature: Sampling temperature (0-1)
        
        Returns:
            Translation result
        """
        try:
            # Convert base64 to bytes if needed
            if isinstance(audio_data, str):
                audio_data = base64.b64decode(audio_data)
            
            # Use OpenAI Whisper translation
            result = await self.openai_client.translate_audio(
                audio_file=audio_data,
                prompt=prompt,
                response_format=response_format,
                temperature=temperature
            )
            
            return {
                'success': True,
                'text': result if response_format == 'text' else result.get('text', ''),
                'format': response_format,
                'result': result
            }
            
        except Exception as e:
            logger.error(f"Speech translation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def text_to_speech(
        self,
        text: str,
        voice: str = "nova",
        model: str = "tts-1",
        speed: float = 1.0,
        response_format: str = "mp3"
    ) -> Dict[str, Any]:
        """
        Convert text to speech
        
        Args:
            text: Text to convert
            voice: Voice ID ('alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer')
            model: TTS model ('tts-1' or 'tts-1-hd')
            speed: Speed (0.25 to 4.0)
            response_format: Audio format ('mp3', 'opus', 'aac', 'flac', 'wav', 'pcm')
        
        Returns:
            Audio data and metadata
        """
        try:
            # Use OpenAI TTS
            audio_data = await self.openai_client.text_to_speech(
                text=text,
                voice=voice,
                model=model,
                speed=speed,
                response_format=response_format
            )
            
            # Convert to base64 for easy transmission
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            return {
                'success': True,
                'audio_data': audio_data,
                'audio_base64': audio_base64,
                'format': response_format,
                'voice': voice,
                'model': model,
                'text_length': len(text)
            }
            
        except Exception as e:
            logger.error(f"Text-to-speech failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def analyze_audio(
        self,
        audio_data: Union[bytes, str]
    ) -> Dict[str, Any]:
        """
        Analyze audio properties and quality
        
        Args:
            audio_data: Audio bytes or base64 string
        
        Returns:
            Audio analysis results
        """
        try:
            # Convert base64 to bytes if needed
            if isinstance(audio_data, str):
                audio_data = base64.b64decode(audio_data)
            
            # Basic analysis
            audio_size = len(audio_data)
            
            # Try to get more detailed info using transcription with verbose output
            result = await self.transcribe(
                audio_data=audio_data,
                response_format="verbose_json"
            )
            
            analysis = {
                'success': True,
                'size_bytes': audio_size,
                'size_mb': round(audio_size / (1024 * 1024), 2)
            }
            
            if result['success'] and 'result' in result:
                verbose_data = result['result']
                analysis.update({
                    'duration': verbose_data.get('duration'),
                    'language': verbose_data.get('language'),
                    'segments_count': len(verbose_data.get('segments', [])) if verbose_data.get('segments') else 0
                })
            
            return analysis
            
        except Exception as e:
            logger.error(f"Audio analysis failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Create singleton instance
speech_service = SpeechToTextService()


# Convenience functions
async def transcribe_audio(*args, **kwargs):
    return await speech_service.transcribe(*args, **kwargs)

async def translate_audio(*args, **kwargs):
    return await speech_service.translate(*args, **kwargs)

async def text_to_speech(*args, **kwargs):
    return await speech_service.text_to_speech(*args, **kwargs)