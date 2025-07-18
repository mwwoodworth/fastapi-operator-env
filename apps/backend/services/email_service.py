"""
Email service for sending transactional and marketing emails.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os


class EmailService:
    """Service for email operations."""
    
    def __init__(self):
        # In production, would initialize with email provider (SendGrid, SES, etc.)
        self.from_email = os.getenv("FROM_EMAIL", "noreply@brainops.com")
        self.from_name = os.getenv("FROM_NAME", "BrainOps")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        reply_to: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send single email."""
        # Mock implementation - in production would use email provider
        print(f"Sending email to {to_email}: {subject}")
        
        # Simulate async send
        await asyncio.sleep(0.1)
        
        return {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "status": "sent",
            "to": to_email,
            "subject": subject
        }
    
    async def send_bulk_email(
        self,
        recipients: List[Dict[str, Any]],
        subject: str,
        template_id: str,
        template_data: Dict[str, Any],
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send bulk emails using template."""
        # Mock implementation
        sent = 0
        failed = 0
        
        for recipient in recipients:
            try:
                await self.send_email(
                    recipient["email"],
                    subject,
                    self._render_template(template_id, {**template_data, **recipient})
                )
                sent += 1
            except:
                failed += 1
        
        return {
            "sent": sent,
            "failed": failed,
            "total": len(recipients)
        }
    
    async def send_invoice_email(
        self,
        invoice_data: Dict[str, Any],
        pdf_attachment: bytes
    ) -> Dict[str, Any]:
        """Send invoice email with PDF attachment."""
        subject = f"Invoice {invoice_data['invoice_number']} from {self.from_name}"
        
        body = f"""
Dear {invoice_data['customer_name']},

Please find attached invoice {invoice_data['invoice_number']} for ${invoice_data['total_amount']:,.2f}.

Due Date: {invoice_data['due_date']}

You can pay this invoice online at: {invoice_data['payment_link']}

Thank you for your business!

Best regards,
{self.from_name}
        """
        
        return await self.send_email(
            invoice_data['customer_email'],
            subject,
            body,
            attachments=[{
                "filename": f"invoice_{invoice_data['invoice_number']}.pdf",
                "content": pdf_attachment,
                "content_type": "application/pdf"
            }]
        )
    
    async def send_receipt_email(
        self,
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send payment receipt email."""
        subject = f"Payment Receipt - ${payment_data['amount']:,.2f}"
        
        body = f"""
Dear {payment_data['customer_name']},

Thank you for your payment of ${payment_data['amount']:,.2f}.

Payment Details:
- Invoice: {payment_data['invoice_number']}
- Payment Method: {payment_data['payment_method']}
- Transaction ID: {payment_data['transaction_id']}
- Date: {payment_data['payment_date']}

Your account balance is now: ${payment_data['balance']:,.2f}

Best regards,
{self.from_name}
        """
        
        return await self.send_email(
            payment_data['customer_email'],
            subject,
            body
        )
    
    async def send_welcome_email(
        self,
        user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send welcome email to new users."""
        subject = f"Welcome to {self.from_name}!"
        
        body = f"""
Hi {user_data['name']},

Welcome to {self.from_name}! We're excited to have you on board.

Here are your next steps:
1. Complete your profile
2. Connect your integrations
3. Invite your team members

If you have any questions, feel free to reach out to our support team.

Best regards,
The {self.from_name} Team
        """
        
        return await self.send_email(
            user_data['email'],
            subject,
            body
        )
    
    async def send_notification_email(
        self,
        to_email: str,
        notification_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send notification emails based on type."""
        templates = {
            "task_assigned": {
                "subject": "New Task Assigned: {task_title}",
                "body": "You have been assigned a new task: {task_title}\n\nDue: {due_date}\nPriority: {priority}"
            },
            "lead_assigned": {
                "subject": "New Lead Assigned: {lead_name}",
                "body": "You have been assigned a new lead:\n\nName: {lead_name}\nCompany: {company}\nScore: {score}"
            },
            "deal_won": {
                "subject": "Deal Won: {deal_title}",
                "body": "Congratulations! The deal '{deal_title}' has been won.\n\nValue: ${value:,.2f}"
            }
        }
        
        template = templates.get(notification_type, {
            "subject": "Notification",
            "body": "You have a new notification."
        })
        
        subject = template["subject"].format(**data)
        body = template["body"].format(**data)
        
        return await self.send_email(to_email, subject, body)
    
    async def send_campaign_email(
        self,
        campaign_id: str,
        recipient: Dict[str, Any],
        template_id: str,
        personalization: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send campaign email with tracking."""
        # Add tracking pixels and links
        tracking_data = {
            "campaign_id": campaign_id,
            "recipient_id": recipient.get("id"),
            "sent_at": datetime.utcnow().isoformat()
        }
        
        # Mock implementation
        return await self.send_email(
            recipient["email"],
            personalization.get("subject", "Campaign Email"),
            self._render_template(template_id, personalization),
            tags=["campaign", f"campaign_{campaign_id}"]
        )
    
    def _render_template(
        self,
        template_id: str,
        data: Dict[str, Any]
    ) -> str:
        """Render email template with data."""
        # Mock template rendering
        templates = {
            "lead_nurture": """
Hi {first_name},

Thanks for your interest in {product_name}. We noticed you {trigger_action}.

Here are some resources that might help:
- {resource_1}
- {resource_2}

Ready to take the next step? {cta_text}

Best,
{sender_name}
            """,
            "follow_up": """
Hi {first_name},

Following up on our conversation about {topic}.

{custom_message}

Let me know if you'd like to schedule a call to discuss further.

Best,
{sender_name}
            """
        }
        
        template = templates.get(template_id, "Hi {first_name},\n\n{message}\n\nBest,\n{sender_name}")
        
        # Simple template rendering
        for key, value in data.items():
            template = template.replace(f"{{{key}}}", str(value))
        
        return template
    
    async def verify_email_address(
        self,
        email: str
    ) -> Dict[str, Any]:
        """Verify email address validity."""
        # Mock implementation - would use email verification service
        import re
        
        # Basic email regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid = bool(re.match(pattern, email))
        
        return {
            "email": email,
            "valid": is_valid,
            "disposable": False,  # Would check against disposable email list
            "role_based": email.startswith(("admin@", "info@", "support@")),
            "free_email": any(domain in email for domain in ["gmail.com", "yahoo.com", "hotmail.com"])
        }
    
    async def get_email_stats(
        self,
        message_ids: List[str]
    ) -> Dict[str, Any]:
        """Get email delivery and engagement stats."""
        # Mock implementation - would query email provider
        return {
            "sent": len(message_ids),
            "delivered": int(len(message_ids) * 0.95),
            "opened": int(len(message_ids) * 0.25),
            "clicked": int(len(message_ids) * 0.05),
            "bounced": int(len(message_ids) * 0.02),
            "complained": 0
        }


# Create singleton instance
email_service = EmailService()

# Convenience function exports
send_email = email_service.send_email
send_invoice_email = email_service.send_invoice_email
send_receipt_email = email_service.send_receipt_email
send_notification_email = email_service.send_notification_email