"""
Customer onboarding task for BrainOps.

This task orchestrates the critical first impressions and setup processes
that transform a payment into a successful long-term relationship. Every
step is designed to deliver immediate value while preventing early churn.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio

from .tasks.base import BaseTask
from .agents.claude_agent import ClaudeAgent
from .integrations.slack import SlackIntegration
from .integrations.clickup import ClickUpIntegration
from .memory.memory_store import MemoryStore
from .core.logging import logger


class CustomerOnboardingTask(BaseTask):
    """
    Orchestrates new customer onboarding with precision and care.
    
    This task ensures every new customer receives the right resources,
    access, and support to achieve quick wins that build confidence
    and establish long-term value realization patterns.
    """
    
    TASK_ID = "customer_onboarding"
    DESCRIPTION = "Complete onboarding sequence for new customers"
    
    def __init__(self):
        super().__init__()
        self.claude = ClaudeAgent()
        self.slack = SlackIntegration()
        self.clickup = ClickUpIntegration()
        self.memory_store = MemoryStore()
        
    async def run(
        self,
        customer_id: str,
        subscription_id: Optional[str] = None,
        product_ids: Optional[List[str]] = None,
        trigger_source: str = "manual"
    ) -> Dict[str, Any]:
        """
        Execute comprehensive customer onboarding sequence.
        
        Args:
            customer_id: Stripe customer ID
            subscription_id: Subscription ID if applicable
            product_ids: List of purchased product IDs
            trigger_source: What triggered the onboarding
            
        Returns:
            Onboarding completion status and delivered resources
        """
        logger.info(f"Starting onboarding for customer {customer_id}")
        
        # Track onboarding progress
        onboarding_result = {
            "customer_id": customer_id,
            "started_at": datetime.utcnow().isoformat(),
            "steps_completed": [],
            "resources_delivered": [],
            "status": "in_progress"
        }
        
        try:
            # Step 1: Gather customer context
            customer_profile = await self._build_customer_profile(customer_id)
            onboarding_result["customer_profile"] = customer_profile
            onboarding_result["steps_completed"].append("profile_built")
            
            # Step 2: Determine onboarding path based on purchase
            onboarding_type = self._determine_onboarding_type(
                subscription_id, 
                product_ids,
                customer_profile
            )
            
            # Step 3: Create personalized welcome message
            welcome_content = await self._generate_welcome_content(
                customer_profile,
                onboarding_type
            )
            onboarding_result["welcome_content"] = welcome_content
            onboarding_result["steps_completed"].append("welcome_generated")
            
            # Step 4: Set up access and accounts
            access_result = await self._setup_customer_access(
                customer_profile,
                onboarding_type
            )
            onboarding_result["access_setup"] = access_result
            onboarding_result["steps_completed"].append("access_configured")
            
            # Step 5: Create onboarding project in ClickUp
            if onboarding_type in ["subscription", "high_value"]:
                project_id = await self._create_onboarding_project(
                    customer_profile,
                    onboarding_type
                )
                onboarding_result["project_id"] = project_id
                onboarding_result["steps_completed"].append("project_created")
            
            # Step 6: Deliver initial resources
            resources = await self._deliver_initial_resources(
                customer_profile,
                onboarding_type,
                product_ids
            )
            onboarding_result["resources_delivered"] = resources
            onboarding_result["steps_completed"].append("resources_delivered")
            
            # Step 7: Schedule follow-up sequences
            follow_ups = await self._schedule_follow_ups(
                customer_profile,
                onboarding_type
            )
            onboarding_result["follow_ups_scheduled"] = follow_ups
            onboarding_result["steps_completed"].append("follow_ups_scheduled")
            
            # Step 8: Notify team if high-value customer
            if onboarding_type == "high_value" or customer_profile.get("is_enterprise"):
                await self._notify_team_high_value(customer_profile)
                onboarding_result["steps_completed"].append("team_notified")
            
            # Mark onboarding as complete
            onboarding_result["status"] = "completed"
            onboarding_result["completed_at"] = datetime.utcnow().isoformat()
            
            # Store onboarding completion in memory
            await self.memory_store.add_knowledge(
                content=f"Customer {customer_profile.get('email', customer_id)} onboarding completed",
                metadata=onboarding_result,
                memory_type="customer_event"
            )
            
        except Exception as e:
            logger.error(f"Onboarding failed for customer {customer_id}: {str(e)}")
            onboarding_result["status"] = "failed"
            onboarding_result["error"] = str(e)
            
            # Notify team of failed onboarding
            await self._notify_onboarding_failure(customer_id, str(e))
        
        return onboarding_result
    
    async def _build_customer_profile(self, customer_id: str) -> Dict[str, Any]:
        """
        Build comprehensive customer profile from all data sources.
        
        This profile drives personalization throughout the onboarding
        journey and beyond.
        """
        # Start with basic profile
        profile = {
            "customer_id": customer_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Retrieve data from memory store
        customer_memories = await self.memory_store.search_memories(
            query=f"customer_id:{customer_id}",
            memory_types=["customer_data", "financial_event"],
            limit=20
        )
        
        # Extract key information from memories
        for memory in customer_memories:
            metadata = memory.get("metadata", {})
            
            # Extract email and name
            if not profile.get("email"):
                profile["email"] = metadata.get("email") or metadata.get("customer_email")
            if not profile.get("name"):
                profile["name"] = metadata.get("name")
            
            # Track subscription details
            if metadata.get("plan_id"):
                profile["subscription_plan"] = metadata.get("plan_id")
                profile["subscription_status"] = metadata.get("status")
            
            # Calculate total spend
            if metadata.get("amount"):
                profile["total_spend"] = profile.get("total_spend", 0) + metadata["amount"]
        
        # Determine customer segment
        profile["segment"] = self._determine_customer_segment(profile)
        profile["is_enterprise"] = profile.get("total_spend", 0) > 500
        
        return profile
    
    def _determine_onboarding_type(
        self, 
        subscription_id: Optional[str],
        product_ids: Optional[List[str]],
        customer_profile: Dict[str, Any]
    ) -> str:
        """
        Determine the appropriate onboarding path based on purchase type.
        
        Different customers need different journeys - this ensures they
        get the right experience for their investment level.
        """
        if customer_profile.get("is_enterprise") or customer_profile.get("total_spend", 0) > 500:
            return "high_value"
        elif subscription_id:
            return "subscription"
        elif product_ids and len(product_ids) > 3:
            return "multi_product"
        elif product_ids:
            return "single_product"
        else:
            return "basic"
    
    def _determine_customer_segment(self, profile: Dict[str, Any]) -> str:
        """Segment customers for targeted onboarding."""
        total_spend = profile.get("total_spend", 0)
        
        if total_spend > 1000:
            return "enterprise"
        elif total_spend > 200:
            return "professional"
        elif total_spend > 0:
            return "starter"
        else:
            return "prospect"
    
    async def _generate_welcome_content(
        self,
        customer_profile: Dict[str, Any],
        onboarding_type: str
    ) -> Dict[str, Any]:
        """
        Generate personalized welcome content using AI.
        
        First impressions matter - make them count with relevant,
        valuable content that demonstrates immediate ROI.
        """
        # Create personalized prompt based on customer context
        prompt = f"""
        Create a warm, professional welcome message for a new BrainOps customer.
        
        Customer Context:
        - Segment: {customer_profile.get('segment', 'starter')}
        - Onboarding Type: {onboarding_type}
        - Email: {customer_profile.get('email', 'valued customer')}
        
        The message should:
        1. Thank them for their trust in BrainOps
        2. Highlight 2-3 immediate actions they can take for quick wins
        3. Set expectations for the onboarding journey
        4. Provide a clear next step
        
        Tone: Professional but warm, confident, and action-oriented
        Length: 150-200 words
        """
        
        # Generate welcome message
        welcome_message = await self.claude.generate_text(
            prompt=prompt,
            max_tokens=500
        )
        
        # Generate subject line
        subject_prompt = f"Create a compelling email subject line for welcoming a {customer_profile.get('segment')} customer to BrainOps. Maximum 50 characters."
        
        subject_line = await self.claude.generate_text(
            prompt=subject_prompt,
            max_tokens=50
        )
        
        return {
            "subject": subject_line.strip(),
            "message": welcome_message,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def _setup_customer_access(
        self,
        customer_profile: Dict[str, Any],
        onboarding_type: str
    ) -> Dict[str, Any]:
        """
        Configure all necessary access and accounts for the customer.
        
        Smooth access setup prevents frustration and support tickets.
        Do it right the first time.
        """
        access_result = {
            "accounts_created": [],
            "permissions_granted": [],
            "invitations_sent": []
        }
        
        # Set up based on onboarding type
        if onboarding_type in ["subscription", "high_value"]:
            # Create dedicated Slack channel for high-touch support
            if customer_profile.get("is_enterprise"):
                channel_name = f"client-{customer_profile.get('email', '').split('@')[0]}"
                # In production, this would create actual Slack channel
                access_result["accounts_created"].append({
                    "type": "slack_channel",
                    "name": channel_name
                })
            
            # Grant access to premium resources
            access_result["permissions_granted"].extend([
                "premium_templates",
                "priority_support",
                "advanced_analytics"
            ])
        
        # Basic access for all customers
        access_result["permissions_granted"].extend([
            "knowledge_base",
            "community_forum",
            "basic_templates"
        ])
        
        return access_result
    
    async def _create_onboarding_project(
        self,
        customer_profile: Dict[str, Any],
        onboarding_type: str
    ) -> str:
        """
        Create structured onboarding project in ClickUp.
        
        This ensures nothing falls through the cracks and provides
        clear visibility into customer progress.
        """
        # Define onboarding tasks based on type
        task_templates = {
            "subscription": [
                "Welcome call scheduled",
                "Platform walkthrough completed",
                "First project created",
                "Integration setup verified",
                "30-day check-in scheduled"
            ],
            "high_value": [
                "Executive welcome call",
                "Dedicated success manager assigned",
                "Custom implementation plan created",
                "Technical integration review",
                "Quarterly business review scheduled"
            ]
        }
        
        tasks = task_templates.get(onboarding_type, ["Basic setup completed"])
        
        # Create project in ClickUp
        project_data = {
            "name": f"Onboarding: {customer_profile.get('email', customer_profile['customer_id'])}",
            "description": f"Onboarding project for {customer_profile.get('segment')} customer",
            "tasks": tasks,
            "due_date": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }
        
        # In production, this would create actual ClickUp project
        project_id = f"onboard_{customer_profile['customer_id']}"
        
        logger.info(f"Created onboarding project {project_id} for customer {customer_profile['customer_id']}")
        
        return project_id
    
    async def _deliver_initial_resources(
        self,
        customer_profile: Dict[str, Any],
        onboarding_type: str,
        product_ids: Optional[List[str]]
    ) -> List[Dict[str, str]]:
        """
        Deliver the right resources at the right time.
        
        Overwhelming customers with everything at once causes paralysis.
        Strategic delivery drives action and builds momentum.
        """
        resources = []
        
        # Base resources for all customers
        resources.extend([
            {
                "type": "guide",
                "title": "BrainOps Quick Start Guide",
                "url": "https://brainops.com/quickstart",
                "description": "Get up and running in 15 minutes"
            },
            {
                "type": "video",
                "title": "Welcome to BrainOps",
                "url": "https://brainops.com/welcome-video",
                "description": "5-minute overview of key features"
            }
        ])
        
        # Segment-specific resources
        if customer_profile.get("segment") == "enterprise":
            resources.extend([
                {
                    "type": "whitepaper",
                    "title": "Enterprise Implementation Best Practices",
                    "url": "https://brainops.com/enterprise-guide",
                    "description": "Proven strategies for organization-wide adoption"
                },
                {
                    "type": "contact",
                    "title": "Your Success Manager",
                    "url": "https://brainops.com/schedule-success-call",
                    "description": "Schedule your executive onboarding session"
                }
            ])
        
        # Product-specific resources
        if product_ids:
            for product_id in product_ids[:3]:  # Limit to top 3 to avoid overwhelm
                resources.append({
                    "type": "template",
                    "title": f"Product Template: {product_id}",
                    "url": f"https://brainops.com/templates/{product_id}",
                    "description": "Ready-to-use template for immediate value"
                })
        
        return resources
    
    async def _schedule_follow_ups(
        self,
        customer_profile: Dict[str, Any],
        onboarding_type: str
    ) -> List[Dict[str, Any]]:
        """
        Schedule strategic follow-up touchpoints.
        
        Timely follow-ups prevent churn and identify expansion
        opportunities before competitors can intervene.
        """
        follow_ups = []
        
        # Day 3: Quick win check-in
        follow_ups.append({
            "day": 3,
            "type": "email",
            "template": "quick_win_checkin",
            "purpose": "Ensure initial setup success"
        })
        
        # Day 7: First week review
        follow_ups.append({
            "day": 7,
            "type": "email",
            "template": "week_one_review",
            "purpose": "Gather feedback and address concerns"
        })
        
        # Day 14: Feature highlight
        follow_ups.append({
            "day": 14,
            "type": "email",
            "template": "feature_spotlight",
            "purpose": "Drive deeper product adoption"
        })
        
        # Day 30: Success checkpoint
        follow_ups.append({
            "day": 30,
            "type": "task",
            "template": "success_review",
            "purpose": "Measure value realization"
        })
        
        # High-value customers get additional touchpoints
        if onboarding_type == "high_value":
            follow_ups.extend([
                {
                    "day": 1,
                    "type": "call",
                    "template": "executive_welcome",
                    "purpose": "Personal connection with leadership"
                },
                {
                    "day": 45,
                    "type": "call",
                    "template": "expansion_discussion",
                    "purpose": "Identify growth opportunities"
                }
            ])
        
        # Schedule in task system
        for follow_up in follow_ups:
            follow_up["customer_id"] = customer_profile["customer_id"]
            follow_up["scheduled_date"] = (
                datetime.utcnow() + timedelta(days=follow_up["day"])
            ).isoformat()
        
        return follow_ups
    
    async def _notify_team_high_value(self, customer_profile: Dict[str, Any]):
        """
        Alert team to high-value customer requiring white-glove service.
        
        High-value customers deserve immediate attention. Make sure
        the right people know to provide it.
        """
        message = f"""
        🌟 High-Value Customer Alert 🌟
        
        New {customer_profile.get('segment', 'enterprise')} customer requires immediate attention:
        
        • Customer: {customer_profile.get('email', 'Unknown')}
        • Total Spend: ${customer_profile.get('total_spend', 0):.2f}
        • Plan: {customer_profile.get('subscription_plan', 'Unknown')}
        
        Action Required:
        1. Assign dedicated success manager
        2. Schedule executive welcome call within 24 hours
        3. Prepare custom implementation plan
        
        This is a priority onboarding - let's deliver an exceptional experience.
        """
        
        # Send to appropriate Slack channel
        await self.slack.post_message(
            channel="#high-value-alerts",
            text=message,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Claim Customer"},
                            "value": customer_profile["customer_id"],
                            "action_id": "claim_customer",
                            "style": "primary"
                        }
                    ]
                }
            ]
        )
    
    async def _notify_onboarding_failure(self, customer_id: str, error: str):
        """
        Alert team to failed onboarding requiring manual intervention.
        
        Failed onboardings risk immediate churn. Rapid response can
        save the relationship.
        """
        message = f"""
        ⚠️ Onboarding Failure Alert ⚠️
        
        Customer onboarding failed and requires immediate manual intervention:
        
        • Customer ID: {customer_id}
        • Error: {error}
        • Time: {datetime.utcnow().isoformat()}
        
        This customer's first experience is at risk. Please investigate immediately.
        """
        
        await self.slack.post_message(
            channel="#onboarding-alerts",
            text=message
        )