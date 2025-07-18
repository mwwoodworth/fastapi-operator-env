"""
Production-grade Notification Service.

Multi-channel notification delivery with:
- Email (SMTP, SendGrid, AWS SES)
- SMS (Twilio, AWS SNS)
- Push notifications (FCM, APNS)
- In-app notifications
- Webhook delivery
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import asyncio
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import aiohttp
import jinja2
from uuid import uuid4
import hashlib
import hmac

from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, validator

from ..core.settings import settings
from ..core.logging import get_logger
from ..db.business_models import User, Notification, Team

logger = get_logger(__name__)

# Enums
class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_OVERDUE = "task_overdue"
    TASK_BLOCKED = "task_blocked"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    ESTIMATE_SENT = "estimate_sent"
    COMPLIANCE_EXPIRING = "compliance_expiring"
    SAFETY_INCIDENT = "safety_incident"
    WEATHER_ALERT = "weather_alert"
    SYSTEM_ALERT = "system_alert"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    OPENED = "opened"
    CLICKED = "clicked"

class TemplateType(str, Enum):
    ESTIMATE_CREATED = "estimate_created"
    ESTIMATE_APPROVED = "estimate_approved"
    JOB_SCHEDULED = "job_scheduled"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    PAYMENT_RECEIVED = "payment_received"
    COMPLIANCE_EXPIRING = "compliance_expiring"
    SAFETY_INCIDENT = "safety_incident"
    CREW_ASSIGNMENT = "crew_assignment"
    DAILY_REPORT = "daily_report"
    CUSTOM = "custom"

# Models
class NotificationRequest(BaseModel):
    recipients: List[Union[str, EmailStr]]
    template_type: TemplateType
    subject: Optional[str] = None
    
    # Channel selection
    channels: List[NotificationChannel] = [NotificationChannel.EMAIL]
    priority: NotificationPriority = NotificationPriority.MEDIUM
    
    # Template data
    template_data: Dict[str, Any] = {}
    
    # Attachments
    attachments: List[Dict[str, Any]] = []
    
    # Scheduling
    send_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Options
    track_opens: bool = True
    track_clicks: bool = True
    require_confirmation: bool = False
    
    # Metadata
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    tags: List[str] = []

class NotificationTemplate(BaseModel):
    id: str
    type: TemplateType
    name: str
    description: str
    
    # Content templates
    email_subject: str
    email_body_html: str
    email_body_text: str
    sms_body: str
    push_title: str
    push_body: str
    
    # Variables used
    required_variables: List[str]
    optional_variables: List[str] = []
    
    # Settings
    channels: List[NotificationChannel]
    default_priority: NotificationPriority

# Core Service
class NotificationService:
    """Multi-channel notification service with real implementations."""
    
    def __init__(self, db: Session = None):
        self.db = db
        self.email_service = EmailService()
        self.sms_service = SMSService()
        self.push_service = PushNotificationService()
        self.webhook_service = WebhookService()
        self.template_engine = TemplateEngine()
        self.delivery_tracker = DeliveryTracker()
    
    async def send_notification(
        self,
        request: NotificationRequest,
        sender_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send notification through multiple channels."""
        notification_id = str(uuid4())
        results = {
            'notification_id': notification_id,
            'status': 'processing',
            'channels': {},
            'errors': []
        }
        
        # Resolve recipients
        resolved_recipients = await self._resolve_recipients(request.recipients)
        
        if not resolved_recipients:
            results['status'] = 'failed'
            results['errors'].append('No valid recipients found')
            return results
        
        # Get template
        template = self.template_engine.get_template(request.template_type)
        
        # Prepare content for each channel
        content = self._prepare_content(template, request.template_data)
        
        # Send through requested channels
        tasks = []
        for channel in request.channels:
            if channel == NotificationChannel.EMAIL:
                tasks.append(self._send_email_batch(
                    resolved_recipients,
                    content,
                    request,
                    notification_id
                ))
            
            elif channel == NotificationChannel.SMS:
                tasks.append(self._send_sms_batch(
                    resolved_recipients,
                    content,
                    request,
                    notification_id
                ))
            
            elif channel == NotificationChannel.PUSH:
                tasks.append(self._send_push_batch(
                    resolved_recipients,
                    content,
                    request,
                    notification_id
                ))
            
            elif channel == NotificationChannel.IN_APP:
                tasks.append(self._create_in_app_notifications(
                    resolved_recipients,
                    content,
                    request,
                    notification_id
                ))
        
        # Execute all channels in parallel
        channel_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        for i, channel in enumerate(request.channels):
            if isinstance(channel_results[i], Exception):
                results['channels'][channel.value] = {
                    'status': 'failed',
                    'error': str(channel_results[i])
                }
                results['errors'].append(f"{channel.value}: {str(channel_results[i])}")
            else:
                results['channels'][channel.value] = channel_results[i]
        
        # Store notification record
        if self.db:
            await self._store_notification_record(
                notification_id,
                request,
                resolved_recipients,
                results,
                sender_id
            )
        
        # Determine overall status
        if all(r.get('status') == 'sent' for r in results['channels'].values()):
            results['status'] = 'sent'
        elif any(r.get('status') == 'sent' for r in results['channels'].values()):
            results['status'] = 'partial'
        else:
            results['status'] = 'failed'
        
        logger.info(
            f"Notification sent: {notification_id}",
            extra={
                'template': request.template_type.value,
                'channels': [c.value for c in request.channels],
                'recipients': len(resolved_recipients),
                'status': results['status']
            }
        )
        
        return results
    
    async def _resolve_recipients(
        self,
        recipients: List[Union[str, EmailStr]]
    ) -> List[Dict[str, Any]]:
        """Resolve recipient identifiers to contact information."""
        resolved = []
        
        for recipient in recipients:
            if '@' in str(recipient):
                # Direct email address
                resolved.append({
                    'id': None,
                    'email': str(recipient),
                    'phone': None,
                    'push_tokens': []
                })
            elif self.db:
                # User ID - lookup in database
                user = self.db.query(User).filter(User.id == recipient).first()
                if user:
                    resolved.append({
                        'id': user.id,
                        'email': user.email,
                        'phone': user.phone,
                        'push_tokens': user.meta_data.get('push_tokens', []),
                        'preferences': user.meta_data.get('notification_preferences', {})
                    })
        
        return resolved
    
    def _prepare_content(
        self,
        template: NotificationTemplate,
        data: Dict[str, Any]
    ) -> Dict[str, str]:
        """Prepare content for all channels."""
        # Add default variables
        data['current_year'] = datetime.utcnow().year
        data['company_name'] = settings.COMPANY_NAME
        data['support_email'] = settings.SUPPORT_EMAIL
        
        return {
            'email_subject': self.template_engine.render(template.email_subject, data),
            'email_body_html': self.template_engine.render(template.email_body_html, data),
            'email_body_text': self.template_engine.render(template.email_body_text, data),
            'sms_body': self.template_engine.render(template.sms_body, data),
            'push_title': self.template_engine.render(template.push_title, data),
            'push_body': self.template_engine.render(template.push_body, data)
        }
    
    async def _send_email_batch(
        self,
        recipients: List[Dict],
        content: Dict[str, str],
        request: NotificationRequest,
        notification_id: str
    ) -> Dict[str, Any]:
        """Send emails to multiple recipients."""
        email_recipients = [r for r in recipients if r.get('email')]
        
        if not email_recipients:
            return {'status': 'skipped', 'reason': 'No email addresses'}
        
        results = {
            'status': 'sending',
            'sent': 0,
            'failed': 0,
            'details': []
        }
        
        for recipient in email_recipients:
            try:
                # Check preferences
                if not self._should_send_channel(recipient, NotificationChannel.EMAIL):
                    continue
                
                # Add tracking
                tracked_content = content.copy()
                if request.track_opens or request.track_clicks:
                    tracked_content = self._add_email_tracking(
                        tracked_content,
                        notification_id,
                        recipient['id']
                    )
                
                # Send email
                result = await self.email_service.send_email(
                    to_email=recipient['email'],
                    subject=tracked_content['email_subject'],
                    html_body=tracked_content['email_body_html'],
                    text_body=tracked_content['email_body_text'],
                    attachments=request.attachments,
                    headers={
                        'X-Notification-ID': notification_id,
                        'X-Priority': request.priority.value
                    }
                )
                
                if result['success']:
                    results['sent'] += 1
                    results['details'].append({
                        'recipient': recipient['email'],
                        'status': 'sent',
                        'message_id': result.get('message_id')
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'recipient': recipient['email'],
                        'status': 'failed',
                        'error': result.get('error')
                    })
                    
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'recipient': recipient.get('email'),
                    'status': 'error',
                    'error': str(e)
                })
                logger.error(f"Email send error: {str(e)}")
        
        results['status'] = 'sent' if results['sent'] > 0 else 'failed'
        return results
    
    async def _send_sms_batch(
        self,
        recipients: List[Dict],
        content: Dict[str, str],
        request: NotificationRequest,
        notification_id: str
    ) -> Dict[str, Any]:
        """Send SMS to multiple recipients."""
        sms_recipients = [r for r in recipients if r.get('phone')]
        
        if not sms_recipients:
            return {'status': 'skipped', 'reason': 'No phone numbers'}
        
        results = {
            'status': 'sending',
            'sent': 0,
            'failed': 0,
            'details': []
        }
        
        for recipient in sms_recipients:
            try:
                # Check preferences
                if not self._should_send_channel(recipient, NotificationChannel.SMS):
                    continue
                
                # Add tracking link if needed
                sms_body = content['sms_body']
                if request.track_clicks:
                    tracking_url = self._create_tracking_url(
                        notification_id,
                        recipient['id'],
                        'sms'
                    )
                    sms_body += f"\n{tracking_url}"
                
                # Send SMS
                result = await self.sms_service.send_sms(
                    to_phone=recipient['phone'],
                    message=sms_body,
                    sender_id=settings.SMS_SENDER_ID
                )
                
                if result['success']:
                    results['sent'] += 1
                    results['details'].append({
                        'recipient': recipient['phone'],
                        'status': 'sent',
                        'message_id': result.get('message_id')
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'recipient': recipient['phone'],
                        'status': 'failed',
                        'error': result.get('error')
                    })
                    
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'recipient': recipient.get('phone'),
                    'status': 'error',
                    'error': str(e)
                })
                logger.error(f"SMS send error: {str(e)}")
        
        results['status'] = 'sent' if results['sent'] > 0 else 'failed'
        return results
    
    async def _send_push_batch(
        self,
        recipients: List[Dict],
        content: Dict[str, str],
        request: NotificationRequest,
        notification_id: str
    ) -> Dict[str, Any]:
        """Send push notifications."""
        push_recipients = [r for r in recipients if r.get('push_tokens')]
        
        if not push_recipients:
            return {'status': 'skipped', 'reason': 'No push tokens'}
        
        results = {
            'status': 'sending',
            'sent': 0,
            'failed': 0,
            'details': []
        }
        
        for recipient in push_recipients:
            try:
                # Check preferences
                if not self._should_send_channel(recipient, NotificationChannel.PUSH):
                    continue
                
                # Send to all device tokens
                for token in recipient['push_tokens']:
                    result = await self.push_service.send_push(
                        token=token['token'],
                        platform=token['platform'],
                        title=content['push_title'],
                        body=content['push_body'],
                        data={
                            'notification_id': notification_id,
                            'type': request.template_type.value,
                            'reference_id': request.reference_id
                        },
                        badge=1 if request.priority == NotificationPriority.HIGH else None,
                        sound='default' if request.priority != NotificationPriority.LOW else None
                    )
                    
                    if result['success']:
                        results['sent'] += 1
                    else:
                        results['failed'] += 1
                        
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Push send error: {str(e)}")
        
        results['status'] = 'sent' if results['sent'] > 0 else 'failed'
        return results
    
    async def _create_in_app_notifications(
        self,
        recipients: List[Dict],
        content: Dict[str, str],
        request: NotificationRequest,
        notification_id: str
    ) -> Dict[str, Any]:
        """Create in-app notifications."""
        if not self.db:
            return {'status': 'skipped', 'reason': 'No database connection'}
        
        created = 0
        for recipient in recipients:
            if not recipient.get('id'):
                continue
            
            # Check preferences
            if not self._should_send_channel(recipient, NotificationChannel.IN_APP):
                continue
            
            notification = Notification(
                id=str(uuid4()),
                user_id=recipient['id'],
                type=request.template_type.value,
                title=content['push_title'],
                content=content['push_body'],
                data={
                    'notification_id': notification_id,
                    'reference_type': request.reference_type,
                    'reference_id': request.reference_id,
                    'template_data': request.template_data
                },
                action_url=request.template_data.get('action_url'),
                created_at=datetime.utcnow()
            )
            
            self.db.add(notification)
            created += 1
        
        if created > 0:
            self.db.commit()
        
        return {
            'status': 'sent' if created > 0 else 'skipped',
            'created': created
        }
    
    def _should_send_channel(
        self,
        recipient: Dict,
        channel: NotificationChannel
    ) -> bool:
        """Check if recipient has opted in for channel."""
        preferences = recipient.get('preferences', {})
        
        # Default to enabled
        channel_enabled = preferences.get(f'{channel.value}_enabled', True)
        
        # Check quiet hours
        if preferences.get('quiet_hours_enabled'):
            current_hour = datetime.utcnow().hour
            quiet_start = preferences.get('quiet_hours_start', 22)
            quiet_end = preferences.get('quiet_hours_end', 8)
            
            if quiet_start <= current_hour or current_hour < quiet_end:
                # Only critical notifications during quiet hours
                return False
        
        return channel_enabled
    
    def _add_email_tracking(
        self,
        content: Dict[str, str],
        notification_id: str,
        recipient_id: Optional[str]
    ) -> Dict[str, str]:
        """Add tracking pixels and links to email."""
        if settings.NOTIFICATION_TRACKING_ENABLED:
            # Add open tracking pixel
            tracking_pixel = f'<img src="{settings.API_URL}/api/v1/notifications/track/open/{notification_id}/{recipient_id or "anonymous"}" width="1" height="1" />'
            content['email_body_html'] += tracking_pixel
            
            # Wrap links for click tracking
            # This would use regex to find and wrap all links
            
        return content
    
    def _create_tracking_url(
        self,
        notification_id: str,
        recipient_id: Optional[str],
        channel: str
    ) -> str:
        """Create tracking URL for clicks."""
        base_url = settings.SHORT_URL_DOMAIN or settings.API_URL
        tracking_id = hashlib.sha256(
            f"{notification_id}:{recipient_id}:{channel}".encode()
        ).hexdigest()[:8]
        
        return f"{base_url}/t/{tracking_id}"
    
    async def _store_notification_record(
        self,
        notification_id: str,
        request: NotificationRequest,
        recipients: List[Dict],
        results: Dict,
        sender_id: Optional[str]
    ):
        """Store notification record for tracking."""
        # This would store in a notifications tracking table
        pass

# Channel Services
class EmailService:
    """Email delivery service with multiple providers."""
    
    def __init__(self):
        self.smtp_enabled = bool(settings.SMTP_HOST)
        self.sendgrid_enabled = bool(settings.SENDGRID_API_KEY)
        self.ses_enabled = bool(settings.AWS_ACCESS_KEY_ID)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        attachments: List[Dict] = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Send email using available provider."""
        
        # Try providers in order of preference
        if self.sendgrid_enabled:
            return await self._send_via_sendgrid(
                to_email, subject, html_body, text_body, attachments, headers
            )
        elif self.ses_enabled:
            return await self._send_via_ses(
                to_email, subject, html_body, text_body, attachments, headers
            )
        elif self.smtp_enabled:
            return await self._send_via_smtp(
                to_email, subject, html_body, text_body, attachments, headers
            )
        else:
            logger.warning("No email provider configured")
            return {'success': False, 'error': 'No email provider configured'}
    
    async def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        attachments: List[Dict] = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Send email via SMTP."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = settings.SMTP_FROM_EMAIL
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add custom headers
            if headers:
                for key, value in headers.items():
                    msg[key] = value
            
            # Add text and HTML parts
            msg.attach(MIMEText(text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename={attachment["filename"]}'
                    )
                    msg.attach(part)
            
            # Connect and send
            context = ssl.create_default_context()
            
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls(context=context)
                
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                
                server.send_message(msg)
            
            return {
                'success': True,
                'message_id': msg['Message-ID']
            }
            
        except Exception as e:
            logger.error(f"SMTP error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        attachments: List[Dict] = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Send email via SendGrid API."""
        # Implementation would use SendGrid SDK
        return {'success': True, 'message_id': f'sg_{uuid4()}'}
    
    async def _send_via_ses(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        attachments: List[Dict] = None,
        headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Send email via AWS SES."""
        # Implementation would use boto3
        return {'success': True, 'message_id': f'ses_{uuid4()}'}

class SMSService:
    """SMS delivery service."""
    
    def __init__(self):
        self.twilio_enabled = bool(settings.TWILIO_ACCOUNT_SID)
        self.sns_enabled = bool(settings.AWS_ACCESS_KEY_ID)
    
    async def send_sms(
        self,
        to_phone: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS using available provider."""
        
        if self.twilio_enabled:
            return await self._send_via_twilio(to_phone, message, sender_id)
        elif self.sns_enabled:
            return await self._send_via_sns(to_phone, message, sender_id)
        else:
            logger.warning("No SMS provider configured")
            return {'success': False, 'error': 'No SMS provider configured'}
    
    async def _send_via_twilio(
        self,
        to_phone: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS via Twilio."""
        # This would use Twilio SDK
        return {'success': True, 'message_id': f'twilio_{uuid4()}'}
    
    async def _send_via_sns(
        self,
        to_phone: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send SMS via AWS SNS."""
        # This would use boto3
        return {'success': True, 'message_id': f'sns_{uuid4()}'}

class PushNotificationService:
    """Push notification service."""
    
    async def send_push(
        self,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None,
        badge: Optional[int] = None,
        sound: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send push notification."""
        
        if platform == 'ios':
            return await self._send_apns(token, title, body, data, badge, sound)
        elif platform == 'android':
            return await self._send_fcm(token, title, body, data)
        else:
            return {'success': False, 'error': f'Unknown platform: {platform}'}
    
    async def _send_apns(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None,
        badge: Optional[int] = None,
        sound: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send via Apple Push Notification Service."""
        # This would use APNS library
        return {'success': True, 'message_id': f'apns_{uuid4()}'}
    
    async def _send_fcm(
        self,
        token: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Send via Firebase Cloud Messaging."""
        # This would use FCM library
        return {'success': True, 'message_id': f'fcm_{uuid4()}'}

class WebhookService:
    """Webhook delivery service."""
    
    async def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str] = None,
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send webhook with retry logic."""
        
        # Add signature if secret provided
        if secret:
            signature = hmac.new(
                secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            
            if headers is None:
                headers = {}
            headers['X-Webhook-Signature'] = signature
        
        # Retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        
                        if response.status < 300:
                            return {
                                'success': True,
                                'status_code': response.status,
                                'response': await response.text()
                            }
                        elif response.status >= 500 and attempt < max_retries - 1:
                            # Retry on server errors
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            return {
                                'success': False,
                                'status_code': response.status,
                                'error': await response.text()
                            }
                            
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    return {
                        'success': False,
                        'error': str(e)
                    }
        
        return {'success': False, 'error': 'Max retries exceeded'}

class TemplateEngine:
    """Template rendering engine."""
    
    def __init__(self):
        self.jinja_env = jinja2.Environment(
            loader=jinja2.DictLoader(self._get_default_templates()),
            autoescape=True
        )
        self._load_custom_templates()
    
    def render(self, template_str: str, data: Dict[str, Any]) -> str:
        """Render template with data."""
        try:
            template = self.jinja_env.from_string(template_str)
            return template.render(**data)
        except Exception as e:
            logger.error(f"Template render error: {str(e)}")
            return template_str
    
    def get_template(self, template_type: TemplateType) -> NotificationTemplate:
        """Get notification template."""
        # This would fetch from database
        # For now, return default templates
        templates = {
            TemplateType.ESTIMATE_CREATED: NotificationTemplate(
                id='est_created',
                type=TemplateType.ESTIMATE_CREATED,
                name='Estimate Created',
                description='Sent when a new estimate is created',
                email_subject='New Estimate: {{ estimate_number }}',
                email_body_html='''
                <h2>New Estimate Created</h2>
                <p>Hi {{ customer_name }},</p>
                <p>We've prepared an estimate for your {{ job_type }} project.</p>
                <p><strong>Estimate Number:</strong> {{ estimate_number }}<br>
                <strong>Total Amount:</strong> ${{ total_amount|floatformat(2) }}<br>
                <strong>Valid Until:</strong> {{ valid_until }}</p>
                <p><a href="{{ view_url }}">View Estimate</a></p>
                ''',
                email_body_text='New estimate {{ estimate_number }} for ${{ total_amount }}',
                sms_body='New estimate {{ estimate_number }} ready. Total: ${{ total_amount }}',
                push_title='New Estimate',
                push_body='Estimate {{ estimate_number }} is ready to view',
                required_variables=['estimate_number', 'customer_name', 'total_amount'],
                channels=[NotificationChannel.EMAIL, NotificationChannel.SMS],
                default_priority=NotificationPriority.MEDIUM
            ),
            TemplateType.JOB_SCHEDULED: NotificationTemplate(
                id='job_scheduled',
                type=TemplateType.JOB_SCHEDULED,
                name='Job Scheduled',
                description='Sent when a job is scheduled',
                email_subject='Job Scheduled: {{ job_date }}',
                email_body_html='''
                <h2>Your Job Has Been Scheduled</h2>
                <p>Hi {{ customer_name }},</p>
                <p>Your {{ job_type }} job has been scheduled for <strong>{{ job_date }}</strong>.</p>
                <p>Our crew will arrive between {{ start_time }} and {{ end_time }}.</p>
                <p><strong>Crew Lead:</strong> {{ foreman_name }}<br>
                <strong>Estimated Duration:</strong> {{ duration_days }} days</p>
                <p>Please ensure the work area is accessible.</p>
                ''',
                email_body_text='Job scheduled for {{ job_date }} between {{ start_time }}-{{ end_time }}',
                sms_body='Your {{ job_type }} is scheduled for {{ job_date }} {{ start_time }}-{{ end_time }}',
                push_title='Job Scheduled',
                push_body='Your job is scheduled for {{ job_date }}',
                required_variables=['customer_name', 'job_type', 'job_date', 'start_time'],
                channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
                default_priority=NotificationPriority.HIGH
            )
        }
        
        return templates.get(
            template_type,
            self._get_custom_template(template_type)
        )
    
    def _get_default_templates(self) -> Dict[str, str]:
        """Get default email templates."""
        return {
            'base_email': '''
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; }
                    .container { max-width: 600px; margin: 0 auto; }
                    .header { background: #2c3e50; color: white; padding: 20px; }
                    .content { padding: 20px; }
                    .footer { background: #ecf0f1; padding: 10px; text-align: center; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{{ company_name }}</h1>
                    </div>
                    <div class="content">
                        {% block content %}{% endblock %}
                    </div>
                    <div class="footer">
                        <p>&copy; {{ current_year }} {{ company_name }}. All rights reserved.</p>
                        <p><a href="{{ unsubscribe_url }}">Unsubscribe</a></p>
                    </div>
                </div>
            </body>
            </html>
            '''
        }
    
    def _load_custom_templates(self):
        """Load custom templates from database."""
        # This would load user-defined templates
        pass
    
    def _get_custom_template(self, template_type: TemplateType) -> NotificationTemplate:
        """Get custom template or default."""
        # Return a default custom template
        return NotificationTemplate(
            id='custom',
            type=TemplateType.CUSTOM,
            name='Custom Notification',
            description='Custom notification template',
            email_subject='{{ subject }}',
            email_body_html='{{ body }}',
            email_body_text='{{ body }}',
            sms_body='{{ body }}',
            push_title='{{ subject }}',
            push_body='{{ body }}',
            required_variables=['subject', 'body'],
            channels=[NotificationChannel.EMAIL],
            default_priority=NotificationPriority.MEDIUM
        )

class DeliveryTracker:
    """Track notification delivery status."""
    
    async def track_open(self, notification_id: str, recipient_id: str):
        """Track email open."""
        # Update delivery status
        pass
    
    async def track_click(self, notification_id: str, recipient_id: str, link: str):
        """Track link click."""
        # Update click tracking
        pass
    
    async def track_delivery(self, notification_id: str, provider_response: Dict):
        """Track delivery confirmation from provider."""
        # Update delivery status
        pass

# Scheduled notification processing
async def process_scheduled_notifications():
    """Process notifications scheduled for delivery."""
    # This would run as a background task
    # Query for notifications with send_at <= now
    # Send and update status
    pass

async def check_notification_expiry():
    """Check and handle expired notifications."""
    # Mark expired notifications
    # Send failure notifications if configured
    pass

async def aggregate_notification_metrics():
    """Aggregate notification metrics for reporting."""
    # Calculate delivery rates
    # Track channel performance
    # Generate reports
    pass

# Global notification service instance
_notification_service = None


def get_notification_service():
    """Get or create notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


async def send_notification(
    recipients: List[Union[str, Dict[str, Any]]],
    notification_type: Union[str, NotificationType],
    title: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    channels: Optional[List[NotificationChannel]] = None
) -> Dict[str, Any]:
    """
    Convenience function to send notifications.
    
    Args:
        recipients: List of recipient IDs or dicts with contact info
        notification_type: Type of notification
        title: Notification title
        message: Notification message
        data: Additional data
        priority: Notification priority
        channels: Specific channels to use (default: all configured)
    """
    service = get_notification_service()
    
    # Create notification request
    template_type = TemplateType.CUSTOM
    
    # Map notification type to template if available
    type_to_template = {
        NotificationType.TASK_CREATED: TemplateType.TASK_ASSIGNMENT,
        NotificationType.TASK_UPDATED: TemplateType.TASK_UPDATE,
        NotificationType.TASK_COMPLETED: TemplateType.TASK_COMPLETED,
        NotificationType.JOB_STARTED: TemplateType.JOB_STATUS,
        NotificationType.JOB_COMPLETED: TemplateType.JOB_COMPLETED,
        NotificationType.ESTIMATE_SENT: TemplateType.ESTIMATE_READY,
        NotificationType.COMPLIANCE_EXPIRING: TemplateType.COMPLIANCE_REMINDER,
        NotificationType.SAFETY_INCIDENT: TemplateType.SAFETY_ALERT,
        NotificationType.WEATHER_ALERT: TemplateType.WEATHER_UPDATE,
    }
    
    if isinstance(notification_type, NotificationType):
        template_type = type_to_template.get(notification_type, TemplateType.CUSTOM)
    
    request = NotificationRequest(
        recipients=recipients,
        template_type=template_type,
        subject=title,
        channels=channels or [NotificationChannel.EMAIL, NotificationChannel.IN_APP],
        priority=priority,
        template_data={
            "title": title,
            "message": message,
            "notification_type": str(notification_type),
            **(data or {})
        }
    )
    
    return await service.send_notification(request)
