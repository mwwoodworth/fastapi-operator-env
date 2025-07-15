"""
Connector module for service integrations
"""

from typing import Dict, Type, Any, List
from .base import BaseConnector
from .clickup import ClickUpConnector
from .notion import NotionConnector
from .github import GitHubConnector
from .slack import SlackConnector
from .airtable import AirtableConnector
from .supabase import SupabaseConnector
from .stripe import StripeConnector
from .render import RenderConnector
from .vercel import VercelConnector
from .openai import OpenAIConnector
from .claude import ClaudeConnector


# Registry of available connectors
CONNECTORS: Dict[str, Type[BaseConnector]] = {
    'clickup': ClickUpConnector,
    'notion': NotionConnector,
    'github': GitHubConnector,
    'slack': SlackConnector,
    'airtable': AirtableConnector,
    'supabase': SupabaseConnector,
    'stripe': StripeConnector,
    'render': RenderConnector,
    'vercel': VercelConnector,
    'openai': OpenAIConnector,
    'claude': ClaudeConnector,
}


def get_connector(service_name: str, settings: Any) -> BaseConnector:
    """
    Get a connector instance for a service
    
    Args:
        service_name: Name of the service
        settings: Application settings object
        
    Returns:
        Initialized connector instance
        
    Raises:
        ValueError: If service not found or not configured
    """
    service_name = service_name.lower()
    
    if service_name not in CONNECTORS:
        raise ValueError(f"Unknown service: {service_name}")
    
    # Get service configuration
    config = settings.get_service_config(service_name)
    
    if not config or not any(config.values()):
        raise ValueError(f"Service {service_name} is not configured")
    
    # Create and return connector instance
    connector_class = CONNECTORS[service_name]
    return connector_class(config)


def list_available_connectors() -> List[str]:
    """Get list of available connector names"""
    return list(CONNECTORS.keys())


__all__ = [
    'BaseConnector',
    'get_connector',
    'list_available_connectors',
    'CONNECTORS',
]