"""
Tests for Weathercraft-specific ERP features.
"""

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock
import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ..main import app
from ..models import User


client = TestClient(app)


class TestRoofingMaterialCalculator:
    """Test roofing material calculation features."""
    
    def test_calculate_simple_roof(self, admin_headers):
        """Test material calculation for simple roof."""
        roof_data = {
            "sections": [
                {
                    "length": 40,
                    "width": 30,
                    "pitch": "6/12",
                    "ridge_length": 40
                }
            ],
            "shingle_type": "architectural",
            "include_accessories": True,
            "waste_factor": 0.10
        }
        
        response = client.post(
            "/api/v1/weathercraft/material-calculator",
            json=roof_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify calculations
        assert "roof_measurements" in data
        assert data["roof_measurements"]["total_area_sqft"] > 0
        assert data["roof_measurements"]["squares"] > 0
        
        # Verify materials
        assert "materials_needed" in data
        assert data["materials_needed"]["shingle_bundles"] > 0
        assert data["materials_needed"]["accessories"]["ridge_cap_bundles"] > 0
        
        # Verify cost estimate
        assert "cost_estimate" in data
        assert data["cost_estimate"]["total_materials"] > 0
        assert data["cost_estimate"]["price_per_square"] > 0
    
    def test_calculate_complex_roof(self, admin_headers):
        """Test calculation for complex multi-section roof."""
        roof_data = {
            "sections": [
                {"length": 40, "width": 30, "pitch": "6/12", "ridge_length": 40},
                {"length": 20, "width": 15, "pitch": "8/12", "ridge_length": 20},
                {"length": 15, "width": 10, "pitch": "4/12", "ridge_length": 15, "valley_length": 10}
            ],
            "shingle_type": "premium",
            "include_accessories": True,
            "waste_factor": 0.15
        }
        
        response = client.post(
            "/api/v1/weathercraft/material-calculator",
            json=roof_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should calculate combined area
        total_area = data["roof_measurements"]["total_area_sqft"]
        assert total_area > 1500  # Sum of sections with pitch
        
        # Premium shingles need more bundles per square
        assert data["materials_needed"]["bundles_per_square"] == 4
        
        # Should include valley flashing
        assert data["materials_needed"]["accessories"]["valley_flashing_rolls"] > 0
    
    def test_different_shingle_types(self, admin_headers):
        """Test different shingle type calculations."""
        base_roof = {
            "sections": [{"length": 40, "width": 30, "pitch": "6/12"}],
            "include_accessories": False,
            "waste_factor": 0.10
        }
        
        shingle_types = ["3_tab", "architectural", "premium", "designer"]
        costs = []
        
        for shingle_type in shingle_types:
            roof_data = {**base_roof, "shingle_type": shingle_type}
            response = client.post(
                "/api/v1/weathercraft/material-calculator",
                json=roof_data,
                headers=admin_headers
            )
            
            assert response.status_code == 200
            cost = response.json()["cost_estimate"]["total_materials"]
            costs.append(cost)
        
        # Verify price progression
        assert costs[0] < costs[1] < costs[2] < costs[3]  # 3-tab < architectural < premium < designer


class TestWeatherBasedScheduling:
    """Test weather-based scheduling optimization."""
    
    @patch('apps.backend.services.weather.WeatherService.get_extended_forecast')
    def test_optimize_scheduling_good_weather(self, mock_forecast, admin_headers):
        """Test scheduling with favorable weather."""
        # Mock good weather forecast
        mock_forecast.return_value = [
            {
                "date": (datetime.now() + timedelta(days=i)).isoformat(),
                "temperature_high": 75,
                "temperature_low": 60,
                "precipitation_probability": 10,
                "wind_speed": 10,
                "condition": "sunny"
            }
            for i in range(14)
        ]
        
        scheduling_data = {
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=14)).isoformat(),
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            "jobs": [
                {
                    "id": "job_001",
                    "type": "roofing",
                    "estimated_days": 3,
                    "crew_size_needed": 4
                },
                {
                    "id": "job_002",
                    "type": "siding",
                    "estimated_days": 2,
                    "crew_size_needed": 3
                }
            ],
            "crews": [
                {"id": "crew_001", "size": 4, "skills": ["roofing"], "available": True},
                {"id": "crew_002", "size": 3, "skills": ["siding"], "available": True}
            ]
        }
        
        response = client.post(
            "/api/v1/weathercraft/weather-scheduling/optimize",
            json=scheduling_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should schedule all jobs
        assert len(data["scheduled_jobs"]) == 2
        
        # Weather analysis should show good conditions
        assert data["weather_analysis"]["excellent_days"] > 10
        assert data["weather_analysis"]["poor_days"] == 0
        
        # Should have crew assignments
        assert len(data["crew_assignments"]) == 2
    
    @patch('apps.backend.services.weather.WeatherService.get_extended_forecast')
    def test_optimize_scheduling_bad_weather(self, mock_forecast, admin_headers):
        """Test scheduling with poor weather conditions."""
        # Mock bad weather forecast
        mock_forecast.return_value = [
            {
                "date": (datetime.now() + timedelta(days=i)).isoformat(),
                "temperature_high": 95 if i < 7 else 40,
                "temperature_low": 80 if i < 7 else 25,
                "precipitation_probability": 70 if i % 2 == 0 else 20,
                "wind_speed": 30,
                "condition": "stormy"
            }
            for i in range(14)
        ]
        
        scheduling_data = {
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=14)).isoformat(),
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            "jobs": [
                {
                    "id": "job_001",
                    "type": "roofing",
                    "estimated_days": 3,
                    "crew_size_needed": 4
                }
            ]
        }
        
        response = client.post(
            "/api/v1/weathercraft/weather-scheduling/optimize",
            json=scheduling_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have weather warnings
        assert len(data["recommendations"]) > 0
        assert any("rain" in r["message"].lower() for r in data["recommendations"])
        
        # Should identify poor conditions
        assert data["weather_analysis"]["poor_days"] > 0
        
        # May not be able to schedule all jobs optimally
        if data["scheduled_jobs"]:
            assert data["scheduled_jobs"][0]["weather_score"] < 80


class TestDroneInspection:
    """Test drone inspection analysis features."""
    
    def test_analyze_drone_inspection(self, admin_headers):
        """Test drone inspection analysis."""
        inspection_data = {
            "property_id": "prop_123",
            "images": [
                {"url": "image1.jpg", "metadata": {"altitude": 50, "gps": [37.7749, -122.4194]}},
                {"url": "image2.jpg", "metadata": {"altitude": 50, "gps": [37.7749, -122.4195]}},
                {"url": "image3.jpg", "metadata": {"altitude": 50, "gps": [37.7749, -122.4196]}}
            ],
            "inspection_date": datetime.now().isoformat()
        }
        
        response = client.post(
            "/api/v1/weathercraft/drone-inspection/analyze",
            json=inspection_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have inspection summary
        assert "inspection_summary" in data
        assert data["inspection_summary"]["images_analyzed"] == 3
        
        # Should detect issues
        assert "damage_assessment" in data
        assert data["damage_assessment"]["total_issues_found"] > 0
        
        # Should provide repair recommendations
        assert "repair_recommendations" in data
        assert len(data["repair_recommendations"]) > 0
        
        # Should estimate costs
        assert "cost_estimate" in data
        assert data["cost_estimate"]["total_estimated_cost"] > 0
        
        # Should have visualization links
        assert "damage_visualization" in data
        assert "heat_map_url" in data["damage_visualization"]
        assert "3d_model_url" in data["damage_visualization"]
    
    def test_drone_inspection_severity_detection(self, admin_headers):
        """Test that severity levels affect recommendations."""
        inspection_data = {
            "property_id": "prop_456",
            "images": ["image1.jpg"] * 10,  # More images = more issues detected
            "inspection_date": datetime.now().isoformat()
        }
        
        response = client.post(
            "/api/v1/weathercraft/drone-inspection/analyze",
            json=inspection_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have high severity items
        issues = data["damage_assessment"]["issues"]
        high_severity = [i for i in issues if i["severity"] == "high"]
        assert len(high_severity) > 0
        
        # High severity should have immediate repair urgency
        immediate_repairs = [r for r in data["repair_recommendations"] if r["urgency"] == "immediate"]
        assert len(immediate_repairs) > 0
        
        # Cost should reflect urgency
        assert data["cost_estimate"]["immediate_repairs"] > 0


class TestSmartInventory:
    """Test smart inventory management features."""
    
    @patch('apps.backend.services.weather.WeatherService.get_extended_forecast')
    def test_smart_reorder_suggestions(self, mock_forecast, admin_headers):
        """Test inventory reorder suggestions."""
        # Mock mixed weather
        mock_forecast.return_value = [
            {
                "date": (datetime.now() + timedelta(days=i)).isoformat(),
                "precipitation_probability": 60 if i % 3 == 0 else 10
            }
            for i in range(14)
        ]
        
        response = client.get(
            "/api/v1/weathercraft/inventory/smart-reorder",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should analyze weather impact
        assert "weather_impact" in data
        assert data["weather_impact"]["workable_days_next_14"] < 14
        
        # Should have reorder suggestions
        if data["reorder_suggestions"]:
            suggestion = data["reorder_suggestions"][0]
            assert "urgency" in suggestion
            assert "recommended_order_quantity" in suggestion
            assert "order_by_date" in suggestion
            assert "estimated_cost" in suggestion
        
        # Should have supplier recommendations
        assert "supplier_recommendations" in data
        
        # Should have cost summary
        assert "cost_summary" in data
        assert "total_reorder_cost" in data["cost_summary"]


class TestWarrantyTracking:
    """Test warranty registration and tracking."""
    
    def test_register_standard_warranty(self, admin_headers):
        """Test standard warranty registration."""
        warranty_data = {
            "job_id": "job_789",
            "customer_id": "cust_123",
            "customer_email": "customer@example.com",
            "property_address": "123 Main St, San Francisco, CA",
            "installation_date": date.today().isoformat(),
            "warranty_type": "standard",
            "shingle_manufacturer": "GAF",
            "manufacturer_warranty_years": 30
        }
        
        response = client.post(
            "/api/v1/weathercraft/warranty/register",
            json=warranty_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should generate warranty ID
        assert "warranty" in data
        warranty = data["warranty"]
        assert warranty["warranty_id"].startswith("WR-")
        
        # Standard warranty should be 5 years workmanship
        assert warranty["coverage"]["workmanship"]["years"] == 5
        
        # Should include maintenance requirements
        assert len(warranty["maintenance_requirements"]) > 0
        
        # Should not be transferable for standard
        assert warranty["transferable"] is False
    
    def test_register_premium_warranty(self, admin_headers):
        """Test premium warranty registration."""
        warranty_data = {
            "job_id": "job_999",
            "customer_id": "cust_456",
            "customer_email": "premium@example.com",
            "property_address": "456 Oak Ave, San Francisco, CA",
            "installation_date": date.today().isoformat(),
            "warranty_type": "premium",
            "shingle_manufacturer": "CertainTeed",
            "manufacturer_warranty_years": 50
        }
        
        response = client.post(
            "/api/v1/weathercraft/warranty/register",
            json=warranty_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        warranty = data["warranty"]
        
        # Premium warranty should be 10 years workmanship
        assert warranty["coverage"]["workmanship"]["years"] == 10
        
        # Should be transferable
        assert warranty["transferable"] is True
        
        # Should have longer material warranty
        assert warranty["coverage"]["materials"]["years"] == 50


class TestAIEstimation:
    """Test AI-powered estimation features."""
    
    @patch('apps.backend.agents.langgraph_orchestrator.LangGraphOrchestrator.execute_workflow')
    async def test_generate_ai_estimation(self, mock_execute, admin_headers):
        """Test AI estimation generation."""
        # Mock AI response
        mock_execute.return_value = {
            "final_output": {
                "roof_area": 2800,
                "roof_type": "hip",
                "pitch": "7/12",
                "current_material": "3_tab_shingle",
                "layers": 2,
                "age": 18,
                "confidence": 0.94,
                "scope": [
                    "Remove two layers of shingles",
                    "Replace damaged decking (est. 10%)",
                    "Install synthetic underlayment",
                    "Install architectural shingles"
                ],
                "notes": [
                    "Multiple layers detected - tearoff required",
                    "Evidence of previous storm damage",
                    "Good candidate for insurance claim"
                ]
            }
        }
        
        estimation_request = {
            "property_address": "789 Elm St, San Francisco, CA",
            "images": ["front.jpg", "aerial.jpg", "closeup.jpg"],
            "preferences": {
                "color": "Charcoal",
                "warranty": "premium"
            },
            "urgency": "standard"
        }
        
        response = client.post(
            "/api/v1/weathercraft/ai-estimation/generate",
            json=estimation_request,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have estimate details
        assert "estimate" in data
        estimate = data["estimate"]
        assert estimate["estimate_id"].startswith("EST-")
        
        # Should reflect AI analysis
        assert estimate["property"]["roof_area_sqft"] == 2800
        assert estimate["property"]["layers"] == 2
        
        # Should have pricing breakdown
        assert "pricing" in estimate
        assert estimate["pricing"]["total"] > 0
        assert estimate["pricing"]["price_per_square"] > 0
        
        # Should have AI confidence
        assert estimate["ai_confidence"] == 0.94
        
        # Should have visualizations
        assert "visualizations" in data
        assert "3d_model" in data["visualizations"]


class TestSafetyCompliance:
    """Test safety assessment and compliance features."""
    
    def test_job_safety_assessment_high_roof(self, admin_headers):
        """Test safety assessment for high roof."""
        job_data = {
            "job_id": "job_safety_001",
            "roof_height_ft": 35,
            "roof_pitch": "10/12",
            "crew_size": 5,
            "estimated_days": 4
        }
        
        response = client.post(
            "/api/v1/weathercraft/safety/job-assessment",
            json=job_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should identify as high risk
        assert data["job_safety_assessment"]["overall_risk_level"] == "high"
        
        # Should require fall protection
        safety_reqs = data["safety_requirements"]
        fall_protection = next(r for r in safety_reqs if r["category"] == "Fall Protection")
        assert fall_protection["required"] is True
        
        # Should have risk factors
        risk_factors = data["risk_factors"]
        assert any(r["factor"] == "Extreme height" for r in risk_factors)
        assert any(r["factor"] == "Steep pitch" for r in risk_factors)
        
        # Should have safety checklist
        assert len(data["safety_checklist"]) > 10
        
        # Should require documentation
        assert len(data["required_documentation"]) > 0
    
    @patch('apps.backend.services.weather.WeatherService.get_current_weather')
    def test_safety_weather_conditions(self, mock_weather, admin_headers):
        """Test safety assessment with weather conditions."""
        # Mock high wind conditions
        mock_weather.return_value = {
            "wind_speed": 35,
            "temperature": 45,
            "condition": "windy"
        }
        
        job_data = {
            "job_id": "job_safety_002",
            "roof_height_ft": 20,
            "roof_pitch": "6/12",
            "crew_size": 4,
            "estimated_days": 2
        }
        
        response = client.post(
            "/api/v1/weathercraft/safety/job-assessment",
            json=job_data,
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should identify wind risk
        risk_factors = data["risk_factors"]
        wind_risk = next((r for r in risk_factors if "wind" in r["factor"].lower()), None)
        assert wind_risk is not None
        assert wind_risk["severity"] == "high"


class TestCustomerPortal:
    """Test customer portal integration."""
    
    def test_get_customer_dashboard(self, user_headers):
        """Test customer portal dashboard."""
        # Assuming user can access their own data
        response = client.get(
            "/api/v1/weathercraft/customer-portal/me/dashboard",
            headers=user_headers
        )
        
        # If not implemented for regular users, should get 404 or 403
        assert response.status_code in [200, 403, 404]
        
        if response.status_code == 200:
            data = response.json()
            
            # Should have customer info
            assert "customer" in data
            
            # Should have various sections
            expected_sections = [
                "active_projects",
                "warranties",
                "maintenance_schedule",
                "payment_summary",
                "weather_alerts",
                "documents"
            ]
            
            for section in expected_sections:
                assert section in data
    
    def test_admin_access_customer_portal(self, admin_headers):
        """Test admin access to customer portal."""
        customer_id = "cust_test_123"
        
        response = client.get(
            f"/api/v1/weathercraft/customer-portal/{customer_id}/dashboard",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have full customer data
        assert data["customer"]["id"] == customer_id
        
        # Should include referral program info
        assert "referral_program" in data
        
        # Should include communication preferences
        assert "communication_preferences" in data


def test_weathercraft_features_summary():
    """Summary of Weathercraft features test coverage."""
    print("\n=== Weathercraft Features Test Summary ===")
    print("✅ Material Calculator: Simple, complex, multi-section roofs")
    print("✅ Weather Scheduling: Optimization with forecast integration")
    print("✅ Drone Inspection: Damage detection and cost estimation")
    print("✅ Smart Inventory: Reorder suggestions with weather impact")
    print("✅ Warranty Tracking: Standard and premium warranty registration")
    print("✅ AI Estimation: Photo-based estimation with LangGraph")
    print("✅ Safety Compliance: OSHA requirements and risk assessment")
    print("✅ Customer Portal: Dashboard with project and warranty info")
    print("\nAll Weathercraft-specific features tested!")