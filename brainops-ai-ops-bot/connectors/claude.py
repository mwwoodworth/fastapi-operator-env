"""
Claude connector for AI operations
"""

from typing import Dict, Any, List, Optional
import logging
import requests
from .base import BaseConnector


logger = logging.getLogger(__name__)


class ClaudeConnector(BaseConnector):
    """Claude API connector"""
    
    BASE_URL = "https://api.anthropic.com"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
    
    def authenticate(self) -> bool:
        """Test Claude API key"""
        try:
            # Test with a simple message request
            response = requests.post(
                f"{self.BASE_URL}/v1/messages",
                headers=self.headers,
                json={
                    "model": "claude-3-sonnet-20240229",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "Hi"}]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                self._is_authenticated = True
                logger.info("Claude authentication successful")
                return True
            else:
                logger.error(f"Claude authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Claude authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Claude API health"""
        try:
            # Simple health check
            response = requests.post(
                f"{self.BASE_URL}/v1/messages",
                headers=self.headers,
                json={
                    "model": "claude-3-sonnet-20240229",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "Test"}]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'healthy': True,
                    'message': "Connected successfully",
                    'details': {
                        'model': 'claude-3-sonnet-20240229'
                    }
                }
            else:
                return {
                    'healthy': False,
                    'message': f"API returned status {response.status_code}"
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List Claude resources"""
        if resource_type == 'models':
            return self.list_models()
        
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List available Claude models"""
        # Claude doesn't have a models endpoint, so return known models
        return [
            {
                'id': 'claude-3-sonnet-20240229',
                'name': 'Claude 3 Sonnet',
                'type': 'text'
            },
            {
                'id': 'claude-3-haiku-20240307',
                'name': 'Claude 3 Haiku',
                'type': 'text'
            }
        ]