"""
Stripe webhook handler and payment integration module.

This module protects your revenue stream by ensuring reliable payment
processing, subscription management, and automated customer onboarding.
Every webhook is verified, every payment tracked, and every customer
action triggers the right business response.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
import stripe
from fastapi import HTTPException, Header, Request

from ..core.settings import settings
from ..core.logging import logger
from ..memory.memory_store import MemoryStore
from ..tasks import task_registry


class StripeIntegration:
    """
    Stripe integration for BrainOps revenue operations.
    
    Handles payment processing, subscription lifecycle, and customer
    value tracking with the reliability your business depends on.
    """
    
    def __init__(self):
        # Initialize Stripe with your secret key
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        self.memory_store = MemoryStore()
        
    async def handle_webhook(
        self, 
        payload: str,
        signature: str
    ) -> Dict[str, Any]:
        """
        Process incoming Stripe webhooks with bulletproof verification.
        
        This is where money meets automation - handle with appropriate
        care and logging to protect against revenue loss.
        """
        try:
            # Verify webhook signature to prevent fraud
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
        except ValueError:
            logger.error("Invalid Stripe webhook payload")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid Stripe webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Log the event for audit trail
        logger.info(f"Processing Stripe event: {event['type']} - {event['id']}")
        
        # Route to appropriate handler based on event type
        handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_cancelled,
            "payment_intent.succeeded": self._handle_payment_succeeded,
            "payment_intent.payment_failed": self._handle_payment_failed,
            "invoice.payment_succeeded": self._handle_invoice_paid,
            "customer.created": self._handle_customer_created,
            "checkout.session.completed": self._handle_checkout_completed,
        }
        
        handler = handlers.get(event['type'])
        if handler:
            await handler(event)
            result = {"status": "processed", "event_type": event['type']}
        else:
            logger.warning(f"Unhandled Stripe event type: {event['type']}")
            result = {"status": "unhandled", "event_type": event['type']}
        
        # Store webhook event for debugging and replay capability
        await self.memory_store.add_system_knowledge(
            content=f"Stripe webhook processed: {event['type']}",
            metadata={
                "event_id": event['id'],
                "event_type": event['type'],
                "livemode": event.get('livemode', False),
                "processing_result": result
            }
        )
        
        return result
    
    async def _handle_subscription_created(self, event: Dict[str, Any]):
        """
        Handle new subscription creation - the moment of truth.
        
        This triggers onboarding sequences and sets up the customer
        for success from day one.
        """
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # Get or create customer record
        customer = await self._ensure_customer_record(customer_id)
        
        # Store subscription details in memory for quick access
        await self.memory_store.add_knowledge(
            content=f"Customer {customer.get('email', customer_id)} started subscription",
            metadata={
                "customer_id": customer_id,
                "subscription_id": subscription['id'],
                "plan_id": subscription['items']['data'][0]['price']['id'],
                "status": subscription['status'],
                "current_period_end": subscription['current_period_end']
            },
            memory_type="customer_data"
        )
        
        # Trigger onboarding task for new subscribers
        if subscription['status'] == 'active':
            await self._trigger_onboarding_sequence(customer_id, subscription['id'])
        
        logger.info(f"Subscription created for customer {customer_id}")
    
    async def _handle_subscription_updated(self, event: Dict[str, Any]):
        """
        Handle subscription changes - upgrades, downgrades, and modifications.
        
        These changes often signal shifting customer needs that require
        attention and appropriate response.
        """
        subscription = event['data']['object']
        previous_attributes = event['data'].get('previous_attributes', {})
        
        # Detect meaningful changes
        if 'items' in previous_attributes:
            # Plan change detected
            old_plan = previous_attributes['items']['data'][0]['price']['id']
            new_plan = subscription['items']['data'][0]['price']['id']
            
            await self.memory_store.add_knowledge(
                content=f"Customer changed subscription from {old_plan} to {new_plan}",
                metadata={
                    "customer_id": subscription['customer'],
                    "subscription_id": subscription['id'],
                    "old_plan": old_plan,
                    "new_plan": new_plan,
                    "change_type": "plan_change"
                },
                memory_type="customer_event"
            )
            
            # Trigger appropriate workflow based on change type
            if self._is_upgrade(old_plan, new_plan):
                await self._handle_plan_upgrade(subscription['customer'], new_plan)
            else:
                await self._handle_plan_downgrade(subscription['customer'], new_plan)
    
    async def _handle_subscription_cancelled(self, event: Dict[str, Any]):
        """
        Handle subscription cancellation - a critical retention moment.
        
        This is your last chance to understand why and potentially
        save the relationship. Handle with care and gather intelligence.
        """
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # Log cancellation with full context
        await self.memory_store.add_knowledge(
            content=f"Customer cancelled subscription - requires attention",
            metadata={
                "customer_id": customer_id,
                "subscription_id": subscription['id'],
                "cancelled_at": subscription['canceled_at'],
                "current_period_end": subscription['current_period_end'],
                "cancellation_details": subscription.get('cancellation_details', {})
            },
            memory_type="customer_event",
            importance_score=9  # High importance for retention
        )
        
        # Trigger retention workflow
        await self._trigger_retention_sequence(customer_id, subscription['id'])
        
        logger.warning(f"Subscription cancelled for customer {customer_id}")
    
    async def _handle_payment_succeeded(self, event: Dict[str, Any]):
        """
        Handle successful payment - the fuel for your business engine.
        
        Track revenue, update customer lifetime value, and ensure
        proper service delivery.
        """
        payment_intent = event['data']['object']
        amount = payment_intent['amount'] / 100  # Convert cents to dollars
        
        # Update customer lifetime value
        if payment_intent.get('customer'):
            await self._update_customer_ltv(payment_intent['customer'], amount)
        
        # Log successful payment
        await self.memory_store.add_knowledge(
            content=f"Payment received: ${amount:.2f}",
            metadata={
                "payment_intent_id": payment_intent['id'],
                "customer_id": payment_intent.get('customer'),
                "amount": amount,
                "currency": payment_intent['currency'],
                "payment_method": payment_intent['payment_method_types'][0]
            },
            memory_type="financial_event"
        )
        
        # Trigger post-payment workflows
        if amount >= 100:  # Significant payment threshold
            await self._trigger_high_value_customer_workflow(
                payment_intent.get('customer'), 
                amount
            )
    
    async def _handle_payment_failed(self, event: Dict[str, Any]):
        """
        Handle failed payment - a critical intervention point.
        
        Failed payments risk service disruption and customer churn.
        Respond quickly with appropriate dunning and support.
        """
        payment_intent = event['data']['object']
        failure_reason = payment_intent.get('last_payment_error', {}).get('message', 'Unknown')
        
        # Log failure with high importance
        await self.memory_store.add_knowledge(
            content=f"Payment failed - requires immediate attention",
            metadata={
                "payment_intent_id": payment_intent['id'],
                "customer_id": payment_intent.get('customer'),
                "amount": payment_intent['amount'] / 100,
                "failure_reason": failure_reason,
                "failure_code": payment_intent.get('last_payment_error', {}).get('code')
            },
            memory_type="financial_event",
            importance_score=10  # Maximum importance
        )
        
        # Trigger dunning sequence
        if payment_intent.get('customer'):
            await self._trigger_dunning_sequence(
                payment_intent['customer'],
                payment_intent['amount'] / 100,
                failure_reason
            )
        
        logger.error(f"Payment failed for customer {payment_intent.get('customer')}: {failure_reason}")
    
    async def _handle_invoice_paid(self, event: Dict[str, Any]):
        """
        Handle paid invoice - confirmation of continued business relationship.
        
        Use this moment to strengthen the relationship and ensure
        continued value delivery.
        """
        invoice = event['data']['object']
        
        # Store invoice record
        await self.memory_store.add_knowledge(
            content=f"Invoice paid: {invoice['number']}",
            metadata={
                "invoice_id": invoice['id'],
                "customer_id": invoice['customer'],
                "amount_paid": invoice['amount_paid'] / 100,
                "billing_reason": invoice['billing_reason'],
                "period_start": invoice['period_start'],
                "period_end": invoice['period_end']
            },
            memory_type="financial_event"
        )
    
    async def _handle_customer_created(self, event: Dict[str, Any]):
        """
        Handle new customer creation - the start of a valuable relationship.
        
        First impressions matter. Set up everything needed for a
        successful customer journey from the beginning.
        """
        customer = event['data']['object']
        
        # Create comprehensive customer profile
        await self.memory_store.add_knowledge(
            content=f"New customer created: {customer.get('email', 'Unknown')}",
            metadata={
                "customer_id": customer['id'],
                "email": customer.get('email'),
                "name": customer.get('name'),
                "created": customer['created'],
                "metadata": customer.get('metadata', {})
            },
            memory_type="customer_data"
        )
        
        # Initialize customer in internal systems
        await self._initialize_customer_profile(customer)
    
    async def _handle_checkout_completed(self, event: Dict[str, Any]):
        """
        Handle completed checkout - conversion achieved.
        
        This is a critical moment to ensure smooth transition from
        prospect to customer with all systems properly initialized.
        """
        session = event['data']['object']
        
        # Log successful checkout
        await self.memory_store.add_knowledge(
            content=f"Checkout completed for ${session['amount_total'] / 100:.2f}",
            metadata={
                "session_id": session['id'],
                "customer_id": session.get('customer'),
                "customer_email": session.get('customer_email'),
                "amount_total": session['amount_total'] / 100,
                "payment_status": session['payment_status'],
                "mode": session['mode']  # payment or subscription
            },
            memory_type="conversion_event"
        )
        
        # Trigger appropriate onboarding based on purchase
        if session['mode'] == 'subscription':
            await self._trigger_subscription_onboarding(session)
        else:
            await self._trigger_product_onboarding(session)
    
    # Helper methods for customer and workflow management
    
    async def _ensure_customer_record(self, customer_id: str) -> Dict[str, Any]:
        """Ensure we have a complete customer record from Stripe."""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve customer {customer_id}: {str(e)}")
            return {"id": customer_id}
    
    async def _update_customer_ltv(self, customer_id: str, amount: float):
        """Update customer lifetime value tracking."""
        # This would update the customer record in your database
        # For now, we'll store it in memory
        await self.memory_store.add_knowledge(
            content=f"Customer LTV increased by ${amount:.2f}",
            metadata={
                "customer_id": customer_id,
                "amount": amount,
                "timestamp": datetime.utcnow().isoformat()
            },
            memory_type="customer_metric"
        )
    
    def _is_upgrade(self, old_plan: str, new_plan: str) -> bool:
        """Determine if a plan change is an upgrade based on your pricing tiers."""
        # Define your plan hierarchy
        plan_hierarchy = {
            "starter": 1,
            "professional": 2,
            "enterprise": 3
        }
        
        # Extract plan tier from Stripe price IDs (customize based on your naming)
        old_tier = old_plan.split('_')[0].lower()
        new_tier = new_plan.split('_')[0].lower()
        
        return plan_hierarchy.get(new_tier, 0) > plan_hierarchy.get(old_tier, 0)
    
    async def _trigger_onboarding_sequence(self, customer_id: str, subscription_id: str):
        """Trigger automated onboarding sequence for new subscribers."""
        # Execute customer onboarding task
        OnboardingTask = task_registry.get("customer_onboarding")
        if OnboardingTask:
            task = OnboardingTask()
            await task.run(
                customer_id=customer_id,
                subscription_id=subscription_id,
                trigger_source="stripe_webhook"
            )
        
        logger.info(f"Onboarding sequence triggered for customer {customer_id}")
    
    async def _trigger_retention_sequence(self, customer_id: str, subscription_id: str):
        """Trigger retention workflow for cancelled subscriptions."""
        # This would trigger your retention campaign
        logger.info(f"Retention sequence triggered for customer {customer_id}")
    
    async def _trigger_dunning_sequence(self, customer_id: str, amount: float, reason: str):
        """Trigger dunning sequence for failed payments."""
        # This would trigger your payment recovery workflow
        logger.warning(f"Dunning sequence triggered for customer {customer_id} - ${amount:.2f}")
    
    async def _trigger_high_value_customer_workflow(self, customer_id: str, amount: float):
        """Special handling for high-value transactions."""
        # This would trigger VIP customer treatment
        logger.info(f"High-value customer workflow triggered for {customer_id} - ${amount:.2f}")
    
    async def _handle_plan_upgrade(self, customer_id: str, new_plan: str):
        """Handle customer plan upgrades with appropriate recognition."""
        logger.info(f"Customer {customer_id} upgraded to {new_plan}")
    
    async def _handle_plan_downgrade(self, customer_id: str, new_plan: str):
        """Handle plan downgrades with retention focus."""
        logger.warning(f"Customer {customer_id} downgraded to {new_plan}")
    
    async def _initialize_customer_profile(self, customer: Dict[str, Any]):
        """Initialize new customer in all integrated systems."""
        logger.info(f"Initializing profile for customer {customer['id']}")
    
    async def _trigger_subscription_onboarding(self, session: Dict[str, Any]):
        """Trigger onboarding for subscription purchases."""
        logger.info(f"Subscription onboarding triggered from checkout {session['id']}")
    
    async def _trigger_product_onboarding(self, session: Dict[str, Any]):
        """Trigger onboarding for one-time product purchases."""
        logger.info(f"Product onboarding triggered from checkout {session['id']}")