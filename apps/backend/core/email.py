"""
Email utilities for BrainOps backend.
"""

import asyncio
from typing import List, Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
import jinja2

from .settings import settings
from .logging import get_logger

logger = get_logger(__name__)


class EmailService:
    """Service for sending emails."""
    
    def __init__(self):
        self.smtp_host = settings.EMAIL_HOST
        self.smtp_port = settings.EMAIL_PORT
        self.smtp_username = settings.EMAIL_USERNAME
        self.smtp_password = settings.EMAIL_PASSWORD
        self.from_email = settings.EMAIL_FROM
        self.use_tls = settings.EMAIL_USE_TLS
        
        # Initialize template environment
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader('templates/emails')
        )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            attachments: Optional list of attachments
        """
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.from_email
            message['To'] = to_email
            
            # Add text part
            text_part = MIMEText(body, 'plain')
            message.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                message.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    # Implementation for attachments
                    pass
            
            # Send email
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=self.use_tls
            ) as smtp:
                await smtp.login(self.smtp_username, self.smtp_password)
                await smtp.send_message(message)
            
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            raise
    
    async def send_template_email(
        self,
        to_email: str,
        subject: str,
        template_name: str,
        context: Dict[str, Any]
    ):
        """
        Send an email using a template.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            template_name: Name of the template file
            context: Context variables for the template
        """
        try:
            # Render templates
            text_template = self.template_env.get_template(f"{template_name}.txt")
            html_template = self.template_env.get_template(f"{template_name}.html")
            
            text_body = text_template.render(**context)
            html_body = html_template.render(**context)
            
            await self.send_email(
                to_email=to_email,
                subject=subject,
                body=text_body,
                html_body=html_body
            )
            
        except jinja2.TemplateNotFound:
            # Fallback to plain text if template not found
            logger.warning(f"Email template {template_name} not found")
            await self.send_email(
                to_email=to_email,
                subject=subject,
                body=str(context)
            )
    
    async def send_bulk_emails(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ):
        """
        Send bulk emails to multiple recipients.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
        """
        tasks = []
        
        for recipient in recipients:
            task = self.send_email(
                to_email=recipient,
                subject=subject,
                body=body,
                html_body=html_body
            )
            tasks.append(task)
        
        # Send emails concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to send email to {recipients[i]}: {str(result)}")
        
        return results


# Global email service instance
email_service = EmailService()


# Convenience functions
async def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None
):
    """Send a simple email."""
    await email_service.send_email(to_email, subject, body, html_body)


async def send_verification_email(user_email: str, verification_token: str):
    """Send email verification link."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
    
    await email_service.send_template_email(
        to_email=user_email,
        subject="Verify Your Email - BrainOps",
        template_name="verify_email",
        context={
            "verify_url": verify_url,
            "expires_in": "24 hours"
        }
    )


async def send_password_reset_email(user_email: str, reset_token: str):
    """Send password reset link."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    
    await email_service.send_template_email(
        to_email=user_email,
        subject="Reset Your Password - BrainOps",
        template_name="reset_password",
        context={
            "reset_url": reset_url,
            "expires_in": "1 hour"
        }
    )


async def send_welcome_email(user_email: str, user_name: Optional[str] = None):
    """Send welcome email to new user."""
    await email_service.send_template_email(
        to_email=user_email,
        subject="Welcome to BrainOps!",
        template_name="welcome",
        context={
            "user_name": user_name or "there",
            "login_url": f"{settings.FRONTEND_URL}/login",
            "docs_url": f"{settings.FRONTEND_URL}/docs"
        }
    )


async def send_task_notification_email(
    user_email: str,
    task_title: str,
    project_name: str,
    due_date: Optional[str] = None
):
    """Send task assignment notification."""
    await email_service.send_template_email(
        to_email=user_email,
        subject=f"New Task Assigned: {task_title}",
        template_name="task_notification",
        context={
            "task_title": task_title,
            "project_name": project_name,
            "due_date": due_date,
            "task_url": f"{settings.FRONTEND_URL}/tasks"
        }
    )


async def send_workflow_completion_email(
    user_email: str,
    workflow_name: str,
    status: str,
    duration: str
):
    """Send workflow completion notification."""
    await email_service.send_template_email(
        to_email=user_email,
        subject=f"Workflow {status}: {workflow_name}",
        template_name="workflow_completion",
        context={
            "workflow_name": workflow_name,
            "status": status,
            "duration": duration,
            "workflows_url": f"{settings.FRONTEND_URL}/workflows"
        }
    )