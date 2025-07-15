"""
OpenAI connector for AI operations
"""

from typing import Dict, Any, List, Optional
import logging
import openai
from .base import BaseConnector


logger = logging.getLogger(__name__)


class OpenAIConnector(BaseConnector):
    """OpenAI API connector"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        openai.api_key = self.api_key
    
    def authenticate(self) -> bool:
        """Test OpenAI API key"""
        try:
            # Test with a simple models request
            openai.Model.list()
            self._is_authenticated = True
            logger.info("OpenAI authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"OpenAI authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check OpenAI API health"""
        try:
            models = openai.Model.list()
            
            return {
                'healthy': True,
                'message': f"Connected, {len(models.data)} models available",
                'details': {
                    'model_count': len(models.data)
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List OpenAI resources"""
        if resource_type == 'models':
            return self.list_models()
        
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List available OpenAI models"""
        try:
            models = openai.Model.list()
            
            return [
                {
                    'id': model.id,
                    'created': model.created,
                    'owned_by': model.owned_by
                }
                for model in models.data
            ]
            
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []