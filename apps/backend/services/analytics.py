"""
Analytics service for business intelligence and reporting.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import numpy as np
from collections import defaultdict


class AnalyticsService:
    """Service for generating analytics and insights."""
    
    async def calculate_revenue_metrics(
        self,
        db: Session,
        start_date: date,
        end_date: date,
        group_by: str = "month"
    ) -> Dict[str, Any]:
        """Calculate revenue metrics over time period."""
        # Mock implementation - would query actual data
        return {
            "total_revenue": 1250000.00,
            "recurring_revenue": 850000.00,
            "growth_rate": 15.5,
            "average_deal_size": 25000.00,
            "by_period": self._generate_time_series(start_date, end_date, group_by)
        }
    
    async def calculate_customer_metrics(
        self,
        db: Session,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate customer lifetime value and other metrics."""
        # Mock implementation
        return {
            "lifetime_value": 75000.00,
            "average_order_value": 15000.00,
            "purchase_frequency": 5,
            "churn_risk": "low",
            "satisfaction_score": 4.5
        }
    
    async def forecast_revenue(
        self,
        db: Session,
        months: int = 3,
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """Generate revenue forecast using ML models."""
        # Mock implementation - would use actual ML
        base_revenue = 100000
        growth_rate = 0.10
        
        forecast = []
        for i in range(months):
            month_revenue = base_revenue * (1 + growth_rate) ** (i + 1)
            variance = month_revenue * 0.15  # 15% variance
            
            forecast.append({
                "month": i + 1,
                "forecast": month_revenue,
                "lower_bound": month_revenue - variance,
                "upper_bound": month_revenue + variance,
                "confidence": confidence_level
            })
        
        return {
            "forecast": forecast,
            "total_forecast": sum(f["forecast"] for f in forecast),
            "confidence_level": confidence_level,
            "methodology": "ARIMA with seasonal adjustments"
        }
    
    async def analyze_sales_velocity(
        self,
        db: Session,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Analyze sales velocity and pipeline movement."""
        # Mock implementation
        return {
            "average_sales_cycle": 45,
            "velocity_score": 7.5,
            "bottlenecks": [
                {"stage": "proposal", "average_days": 15},
                {"stage": "negotiation", "average_days": 12}
            ],
            "acceleration_opportunities": [
                "Automate proposal generation",
                "Implement pricing calculator"
            ]
        }
    
    async def segment_customers(
        self,
        db: Session,
        segmentation_type: str = "rfm"
    ) -> Dict[str, Any]:
        """Perform customer segmentation analysis."""
        # Mock RFM (Recency, Frequency, Monetary) segmentation
        segments = {
            "champions": {"count": 45, "value": 450000},
            "loyal_customers": {"count": 120, "value": 850000},
            "at_risk": {"count": 35, "value": 125000},
            "new_customers": {"count": 85, "value": 225000},
            "lost": {"count": 25, "value": 0}
        }
        
        return {
            "segmentation_type": segmentation_type,
            "segments": segments,
            "recommendations": {
                "champions": "Exclusive offers and early access",
                "at_risk": "Re-engagement campaign needed",
                "new_customers": "Onboarding sequence optimization"
            }
        }
    
    async def calculate_team_performance(
        self,
        db: Session,
        team_id: Optional[str] = None,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Calculate team and individual performance metrics."""
        # Mock implementation
        return {
            "team_metrics": {
                "total_revenue": 650000,
                "deals_closed": 26,
                "win_rate": 35.5,
                "average_deal_size": 25000
            },
            "top_performers": [
                {"user": "John Doe", "revenue": 185000, "deals": 8},
                {"user": "Jane Smith", "revenue": 165000, "deals": 7}
            ],
            "activity_metrics": {
                "calls_made": 450,
                "meetings_held": 85,
                "proposals_sent": 35
            }
        }
    
    async def analyze_lead_sources(
        self,
        db: Session,
        period_days: int = 90
    ) -> Dict[str, Any]:
        """Analyze lead source effectiveness."""
        # Mock implementation
        sources = [
            {
                "source": "Website",
                "leads": 250,
                "conversion_rate": 12.5,
                "revenue": 125000,
                "cost": 5000,
                "roi": 2400
            },
            {
                "source": "Referral",
                "leads": 85,
                "conversion_rate": 35.2,
                "revenue": 185000,
                "cost": 2000,
                "roi": 9150
            },
            {
                "source": "Events",
                "leads": 120,
                "conversion_rate": 22.5,
                "revenue": 95000,
                "cost": 15000,
                "roi": 533
            }
        ]
        
        return {
            "sources": sources,
            "best_performing": "Referral",
            "recommendations": [
                "Increase referral program incentives",
                "Optimize website conversion funnel",
                "Re-evaluate event ROI"
            ]
        }
    
    async def predict_churn(
        self,
        db: Session,
        customer_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Predict customer churn using ML models."""
        # Mock implementation
        return {
            "high_risk_customers": 12,
            "medium_risk_customers": 28,
            "low_risk_customers": 145,
            "churn_factors": [
                {"factor": "No activity in 60 days", "weight": 0.35},
                {"factor": "Support tickets unresolved", "weight": 0.25},
                {"factor": "Usage decline", "weight": 0.20}
            ],
            "recommended_actions": [
                "Personal outreach to high-risk customers",
                "Resolve outstanding support tickets",
                "Offer training sessions"
            ]
        }
    
    async def analyze_product_performance(
        self,
        db: Session,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Analyze product/service performance."""
        # Mock implementation
        return {
            "top_products": [
                {"name": "Premium Plan", "revenue": 450000, "units": 45},
                {"name": "Standard Plan", "revenue": 320000, "units": 80}
            ],
            "growth_trends": {
                "premium": "+25%",
                "standard": "+10%",
                "basic": "-5%"
            },
            "cross_sell_opportunities": [
                {"from": "Standard", "to": "Premium", "probability": 0.35},
                {"from": "Basic", "to": "Standard", "probability": 0.45}
            ]
        }
    
    def _generate_time_series(
        self,
        start_date: date,
        end_date: date,
        group_by: str
    ) -> List[Dict[str, Any]]:
        """Generate time series data for charts."""
        # Mock implementation
        series = []
        current = start_date
        
        while current <= end_date:
            value = np.random.randint(80000, 120000)
            series.append({
                "date": current.isoformat(),
                "value": value
            })
            
            if group_by == "day":
                current += timedelta(days=1)
            elif group_by == "week":
                current += timedelta(weeks=1)
            elif group_by == "month":
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
        
        return series
    
    async def generate_executive_dashboard(
        self,
        db: Session,
        period: str = "current_month"
    ) -> Dict[str, Any]:
        """Generate executive dashboard data."""
        # Mock implementation combining various metrics
        return {
            "kpis": {
                "revenue": {"value": 850000, "target": 1000000, "progress": 85},
                "new_customers": {"value": 45, "target": 50, "progress": 90},
                "nps_score": {"value": 72, "target": 70, "progress": 103},
                "churn_rate": {"value": 2.5, "target": 3.0, "progress": 117}
            },
            "trends": {
                "revenue": "+15%",
                "customers": "+12%",
                "satisfaction": "+5%"
            },
            "alerts": [
                {"type": "warning", "message": "Pipeline value below target"},
                {"type": "success", "message": "Customer satisfaction improved"}
            ],
            "focus_areas": [
                "Accelerate deal closure in negotiation stage",
                "Improve lead qualification process",
                "Expand referral program"
            ]
        }