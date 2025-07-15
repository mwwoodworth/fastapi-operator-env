"""
Slack connector for messaging and notifications
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
from .base import BaseConnector


logger = logging.getLogger(__name__)


class SlackConnector(BaseConnector):
    """Slack API connector"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get('bot_token')
        self.webhook_url = config.get('webhook_url')
        self.alert_channel = config.get('alert_channel', '#alerts')
        self.client = None
        self._workspace_info = None
    
    def authenticate(self) -> bool:
        """Initialize Slack client and verify authentication"""
        try:
            self.client = WebClient(token=self.bot_token)
            
            # Test authentication
            response = self.client.auth_test()
            
            if response['ok']:
                self._is_authenticated = True
                self._workspace_info = {
                    'team': response['team'],
                    'user': response['user'],
                    'team_id': response['team_id'],
                    'user_id': response['user_id']
                }
                logger.info(f"Slack authentication successful for {response['team']}")
                return True
            else:
                logger.error("Slack authentication failed")
                return False
                
        except SlackApiError as e:
            logger.error(f"Slack authentication error: {e}")
            return False
        except Exception as e:
            logger.error(f"Slack authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Slack API health"""
        try:
            # Test API connection
            response = self.client.api_test()
            
            if response['ok']:
                # Get channel list to verify permissions
                channels_response = self.client.conversations_list(limit=1)
                
                return {
                    'healthy': True,
                    'message': f"Connected to {self._workspace_info['team']}",
                    'details': {
                        'workspace': self._workspace_info['team'],
                        'bot_user': self._workspace_info['user'],
                        'can_access_channels': channels_response['ok']
                    }
                }
            else:
                return {
                    'healthy': False,
                    'message': "API test failed"
                }
                
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List Slack resources"""
        if resource_type == 'channels':
            return self.list_channels()
        elif resource_type == 'users':
            return self.list_users()
        else:
            raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_channels(self, include_private: bool = False) -> List[Dict[str, Any]]:
        """List Slack channels"""
        try:
            channels = []
            
            # Get public channels
            response = self.client.conversations_list(
                types="public_channel,private_channel" if include_private else "public_channel"
            )
            
            for channel in response.get('channels', []):
                channels.append({
                    'id': channel['id'],
                    'name': channel['name'],
                    'is_private': channel.get('is_private', False),
                    'is_archived': channel.get('is_archived', False),
                    'member_count': channel.get('num_members', 0),
                    'topic': channel.get('topic', {}).get('value', ''),
                    'purpose': channel.get('purpose', {}).get('value', '')
                })
            
            return channels
            
        except Exception as e:
            logger.error(f"Error listing channels: {e}")
            return []
    
    def list_users(self) -> List[Dict[str, Any]]:
        """List Slack users"""
        try:
            users = []
            
            response = self.client.users_list()
            
            for user in response.get('members', []):
                if not user.get('is_bot', False) and not user.get('deleted', False):
                    users.append({
                        'id': user['id'],
                        'name': user.get('name', ''),
                        'real_name': user.get('real_name', ''),
                        'email': user.get('profile', {}).get('email', ''),
                        'is_admin': user.get('is_admin', False),
                        'is_owner': user.get('is_owner', False),
                        'status': user.get('profile', {}).get('status_text', '')
                    })
            
            return users
            
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []
    
    def send_message(self, channel: str, text: str, 
                    blocks: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Send a message to a Slack channel"""
        try:
            kwargs = {
                'channel': channel,
                'text': text
            }
            
            if blocks:
                kwargs['blocks'] = blocks
            
            response = self.client.chat_postMessage(**kwargs)
            
            return {
                'success': response['ok'],
                'timestamp': response.get('ts'),
                'channel': response.get('channel')
            }
            
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_webhook_message(self, text: str, attachments: Optional[List[Dict]] = None) -> bool:
        """Send a message via webhook URL"""
        if not self.webhook_url:
            logger.error("No webhook URL configured")
            return False
        
        try:
            payload = {'text': text}
            
            if attachments:
                payload['attachments'] = attachments
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Error sending webhook message: {e}")
            return False
    
    def send_alert(self, title: str, message: str, 
                  severity: str = 'warning', fields: Optional[Dict] = None) -> bool:
        """Send an alert message with formatting"""
        try:
            # Determine color based on severity
            color_map = {
                'info': '#36a64f',
                'warning': '#ff9900',
                'error': '#ff0000',
                'critical': '#ff0000'
            }
            color = color_map.get(severity, '#808080')
            
            # Build attachment
            attachment = {
                'color': color,
                'title': title,
                'text': message,
                'footer': 'BrainOps AI Ops Bot',
                'ts': int(datetime.utcnow().timestamp())
            }
            
            # Add fields if provided
            if fields:
                attachment['fields'] = [
                    {'title': k, 'value': str(v), 'short': True}
                    for k, v in fields.items()
                ]
            
            # Try webhook first for alerts
            if self.webhook_url:
                return self.send_webhook_message(
                    text=f"🚨 *{severity.upper()}*: {title}",
                    attachments=[attachment]
                )
            else:
                # Fall back to regular message
                blocks = [
                    {
                        'type': 'header',
                        'text': {
                            'type': 'plain_text',
                            'text': f"🚨 {severity.upper()}: {title}"
                        }
                    },
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': message
                        }
                    }
                ]
                
                if fields:
                    field_text = '\n'.join([f"*{k}:* {v}" for k, v in fields.items()])
                    blocks.append({
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': field_text
                        }
                    })
                
                result = self.send_message(
                    channel=self.alert_channel,
                    text=f"{severity.upper()}: {title}",
                    blocks=blocks
                )
                
                return result['success']
                
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False
    
    def get_channel_history(self, channel: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get channel message history"""
        try:
            response = self.client.conversations_history(
                channel=channel,
                limit=limit
            )
            
            messages = []
            for msg in response.get('messages', []):
                messages.append({
                    'timestamp': msg['ts'],
                    'user': msg.get('user', 'bot'),
                    'text': msg.get('text', ''),
                    'type': msg['type']
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting channel history: {e}")
            return []
    
    def create_resource(self, resource_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Slack resource"""
        if resource_type == 'channel':
            return self.create_channel(data)
        else:
            raise ValueError(f"Cannot create resource type: {resource_type}")
    
    def create_channel(self, channel_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Slack channel"""
        try:
            response = self.client.conversations_create(
                name=channel_data.get('name'),
                is_private=channel_data.get('is_private', False)
            )
            
            if response['ok']:
                return {
                    'success': True,
                    'channel_id': response['channel']['id'],
                    'channel_name': response['channel']['name']
                }
            else:
                return {
                    'success': False,
                    'error': response.get('error', 'Unknown error')
                }
                
        except Exception as e:
            logger.error(f"Error creating channel: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def upload_file(self, channel: str, file_path: str, 
                   title: Optional[str] = None) -> Dict[str, Any]:
        """Upload a file to Slack"""
        try:
            with open(file_path, 'rb') as file_content:
                response = self.client.files_upload_v2(
                    channel=channel,
                    file=file_content,
                    title=title or file_path.split('/')[-1]
                )
            
            if response['ok']:
                return {
                    'success': True,
                    'file_id': response['file']['id']
                }
            else:
                return {
                    'success': False,
                    'error': response.get('error', 'Unknown error')
                }
                
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return {
                'success': False,
                'error': str(e)
            }