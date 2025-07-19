"""
Government API integrations for permits, compliance, and regulatory data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import httpx
import asyncio
import json
from urllib.parse import urlencode


class PermitType(str, Enum):
    BUILDING = "building"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    MECHANICAL = "mechanical"
    DEMOLITION = "demolition"
    ROOFING = "roofing"
    SOLAR = "solar"


class PermitStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    ISSUED = "issued"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CLOSED = "closed"


class InspectionType(str, Enum):
    PRE_CONSTRUCTION = "pre_construction"
    FOUNDATION = "foundation"
    FRAMING = "framing"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    MECHANICAL = "mechanical"
    INSULATION = "insulation"
    FINAL = "final"


class GovernmentAPIClient:
    """Client for interacting with various government APIs."""
    
    def __init__(self):
        self.base_urls = {
            'federal': 'https://api.permits.gov/v1',
            'state': {},  # State-specific endpoints
            'local': {}   # City/county endpoints
        }
        self.api_keys = {}
        self.timeout = 30.0
        
    async def search_permit_requirements(
        self,
        address: Dict[str, str],
        project_type: str,
        project_scope: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Search for permit requirements based on location and project."""
        # Determine jurisdiction
        jurisdiction = self._determine_jurisdiction(address)
        
        # Mock implementation - would call actual APIs
        requirements = {
            'jurisdiction': jurisdiction,
            'required_permits': [],
            'estimated_fees': 0,
            'processing_time_days': 0,
            'documentation_required': []
        }
        
        # Building permit almost always required
        if project_scope.get('structural_changes') or project_scope.get('roof_replacement'):
            requirements['required_permits'].append({
                'type': PermitType.BUILDING,
                'name': 'Building Permit',
                'description': 'Required for structural modifications',
                'fee': 250.00,
                'processing_days': 10,
                'required_documents': [
                    'Site plan',
                    'Construction drawings',
                    'Contractor license',
                    'Insurance certificate'
                ]
            })
            requirements['estimated_fees'] += 250.00
            requirements['processing_time_days'] = max(
                requirements['processing_time_days'], 10
            )
        
        # Electrical permit for solar
        if project_scope.get('solar_installation'):
            requirements['required_permits'].append({
                'type': PermitType.ELECTRICAL,
                'name': 'Electrical Permit',
                'description': 'Required for solar panel installation',
                'fee': 150.00,
                'processing_days': 5,
                'required_documents': [
                    'Electrical diagram',
                    'Solar system specifications',
                    'Electrician license'
                ]
            })
            requirements['estimated_fees'] += 150.00
            
        # Demolition permit
        if project_scope.get('tear_off'):
            requirements['required_permits'].append({
                'type': PermitType.DEMOLITION,
                'name': 'Demolition Permit',
                'description': 'Required for complete roof tear-off',
                'fee': 100.00,
                'processing_days': 3,
                'required_documents': [
                    'Disposal plan',
                    'Asbestos test results (if applicable)'
                ]
            })
            requirements['estimated_fees'] += 100.00
        
        # Add documentation requirements
        requirements['documentation_required'] = list(set(
            doc for permit in requirements['required_permits']
            for doc in permit['required_documents']
        ))
        
        return requirements
    
    async def submit_permit_application(
        self,
        permit_type: PermitType,
        applicant_info: Dict[str, Any],
        project_info: Dict[str, Any],
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Submit a permit application to the appropriate authority."""
        # Generate application ID
        application_id = f"PERMIT-{datetime.utcnow().strftime('%Y%m%d')}-{permit_type.value.upper()[:3]}-001"
        
        # Validate required fields
        validation_errors = self._validate_application(
            permit_type, applicant_info, project_info, documents
        )
        
        if validation_errors:
            return {
                'success': False,
                'errors': validation_errors
            }
        
        # Mock submission - would call actual API
        submission_result = {
            'success': True,
            'application_id': application_id,
            'status': PermitStatus.SUBMITTED,
            'submitted_at': datetime.utcnow().isoformat(),
            'estimated_review_date': (
                datetime.utcnow() + timedelta(days=10)
            ).isoformat(),
            'tracking_number': f"TRK{application_id[-8:]}",
            'next_steps': [
                'Application is under review',
                'You will receive email updates',
                'Schedule inspection after approval'
            ]
        }
        
        return submission_result
    
    async def check_permit_status(
        self,
        application_id: str
    ) -> Dict[str, Any]:
        """Check the status of a permit application."""
        # Mock implementation
        # In production, would query actual government databases
        
        # Simulate different statuses based on application age
        mock_statuses = [
            {
                'status': PermitStatus.UNDER_REVIEW,
                'message': 'Application is being reviewed by planning department',
                'progress': 50,
                'reviewer': 'John Smith',
                'estimated_completion': (
                    datetime.utcnow() + timedelta(days=5)
                ).isoformat()
            },
            {
                'status': PermitStatus.APPROVED,
                'message': 'Permit approved and ready for issuance',
                'progress': 90,
                'approval_date': datetime.utcnow().isoformat(),
                'approved_by': 'Jane Doe',
                'conditions': [
                    'Work must be completed within 180 days',
                    'Final inspection required'
                ]
            }
        ]
        
        import random
        status_info = random.choice(mock_statuses)
        
        return {
            'application_id': application_id,
            'current_status': status_info['status'],
            'status_details': status_info,
            'history': [
                {
                    'status': PermitStatus.SUBMITTED,
                    'date': (datetime.utcnow() - timedelta(days=7)).isoformat(),
                    'notes': 'Application received'
                },
                {
                    'status': status_info['status'],
                    'date': datetime.utcnow().isoformat(),
                    'notes': status_info['message']
                }
            ],
            'documents': {
                'submitted': 5,
                'approved': 5,
                'pending': 0
            }
        }
    
    async def search_contractor_licenses(
        self,
        license_number: Optional[str] = None,
        contractor_name: Optional[str] = None,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for contractor license information."""
        # Mock implementation
        results = []
        
        if license_number:
            results.append({
                'license_number': license_number,
                'contractor_name': 'ABC Roofing Company',
                'business_name': 'ABC Roofing LLC',
                'license_type': 'C-39 Roofing',
                'status': 'Active',
                'issue_date': '2020-01-15',
                'expiration_date': '2025-01-14',
                'insurance': {
                    'general_liability': {
                        'coverage': 1000000,
                        'expires': '2025-06-30'
                    },
                    'workers_comp': {
                        'policy_number': 'WC123456',
                        'expires': '2025-12-31'
                    }
                },
                'classifications': ['Roofing', 'Waterproofing', 'Solar'],
                'disciplinary_actions': []
            })
        
        return results
    
    async def verify_business_license(
        self,
        business_name: str,
        city: str,
        state: str
    ) -> Dict[str, Any]:
        """Verify business license status."""
        # Mock implementation
        return {
            'business_name': business_name,
            'license_number': f"BL-{state}-2024-0001",
            'status': 'Active',
            'type': 'General Business License',
            'issued_date': '2024-01-01',
            'expiration_date': '2024-12-31',
            'location': {
                'city': city,
                'state': state
            },
            'authorized_activities': [
                'Construction',
                'Roofing',
                'Home Improvement'
            ]
        }
    
    async def get_building_codes(
        self,
        location: Dict[str, str],
        code_type: str = 'roofing'
    ) -> Dict[str, Any]:
        """Get applicable building codes for a location."""
        state = location.get('state', '').upper()
        
        # Mock building code data
        codes = {
            'jurisdiction': f"{location.get('city')}, {state}",
            'adopted_codes': {
                'building': 'International Building Code 2021',
                'residential': 'International Residential Code 2021',
                'energy': 'International Energy Conservation Code 2021'
            },
            'local_amendments': [],
            'roofing_specific': {
                'wind_rating': self._get_wind_rating(state),
                'fire_rating': self._get_fire_rating(location),
                'snow_load': self._get_snow_load(state),
                'underlayment_required': True,
                'ice_barrier_required': state in ['ME', 'NH', 'VT', 'NY', 'MI', 'WI', 'MN'],
                'minimum_slope': '2:12',
                'ventilation_ratio': '1:150'
            }
        }
        
        # Add hurricane zones
        if state in ['FL', 'TX', 'LA', 'SC', 'NC']:
            codes['roofing_specific']['hurricane_zone'] = True
            codes['roofing_specific']['enhanced_fastening'] = True
            
        return codes
    
    async def schedule_inspection(
        self,
        permit_number: str,
        inspection_type: InspectionType,
        preferred_dates: List[datetime],
        contact_info: Dict[str, str]
    ) -> Dict[str, Any]:
        """Schedule a required inspection."""
        # Find first available date
        available_date = None
        for date in preferred_dates:
            if date.weekday() < 5:  # Weekday
                available_date = date
                break
                
        if not available_date:
            available_date = preferred_dates[0]
            # Move to next weekday if weekend
            while available_date.weekday() >= 5:
                available_date += timedelta(days=1)
        
        inspection_id = f"INSP-{available_date.strftime('%Y%m%d')}-{inspection_type.value[:3].upper()}-001"
        
        return {
            'success': True,
            'inspection_id': inspection_id,
            'permit_number': permit_number,
            'type': inspection_type.value,
            'scheduled_date': available_date.isoformat(),
            'time_window': '8:00 AM - 12:00 PM',
            'inspector': 'TBD',
            'contact': contact_info,
            'requirements': self._get_inspection_requirements(inspection_type),
            'confirmation_sent_to': contact_info.get('email')
        }
    
    async def get_tax_assessor_data(
        self,
        address: Dict[str, str]
    ) -> Dict[str, Any]:
        """Get property data from tax assessor records."""
        # Mock implementation
        return {
            'parcel_number': 'APN-123-456-789',
            'owner': {
                'name': 'Property Owner LLC',
                'mailing_address': '123 Main St, City, ST 12345'
            },
            'property_details': {
                'year_built': 1985,
                'square_footage': 2500,
                'lot_size': 7500,
                'roof_type': 'Composition Shingle',
                'last_roof_replacement': 2010,
                'stories': 2,
                'construction_type': 'Wood Frame'
            },
            'assessed_values': {
                'land': 150000,
                'improvements': 350000,
                'total': 500000,
                'tax_year': 2024
            },
            'tax_history': [
                {'year': 2023, 'amount': 6250, 'status': 'Paid'},
                {'year': 2022, 'amount': 6000, 'status': 'Paid'}
            ]
        }
    
    async def check_liens_and_violations(
        self,
        address: Dict[str, str]
    ) -> Dict[str, Any]:
        """Check for property liens and code violations."""
        # Mock implementation
        return {
            'address': f"{address.get('street')}, {address.get('city')}, {address.get('state')}",
            'liens': [],  # Empty for clean property
            'violations': [],
            'permits_on_file': [
                {
                    'permit_number': 'B2020-1234',
                    'type': 'Roof Replacement',
                    'issued_date': '2020-06-15',
                    'status': 'Closed',
                    'final_inspection': 'Passed'
                }
            ],
            'last_checked': datetime.utcnow().isoformat()
        }
    
    async def get_environmental_requirements(
        self,
        location: Dict[str, str],
        project_type: str
    ) -> Dict[str, Any]:
        """Get environmental requirements and restrictions."""
        requirements = {
            'asbestos_testing': False,
            'lead_paint_testing': False,
            'disposal_requirements': [],
            'protected_species': [],
            'wetlands_permit': False,
            'historical_review': False
        }
        
        # Asbestos requirements for older buildings
        building_age = location.get('building_age', 0)
        if building_age > 40:
            requirements['asbestos_testing'] = True
            requirements['disposal_requirements'].append(
                'Licensed asbestos disposal facility required'
            )
            
        # Lead paint for pre-1978
        if building_age > 45:
            requirements['lead_paint_testing'] = True
            requirements['disposal_requirements'].append(
                'RRP certification required for lead paint'
            )
            
        # Standard disposal
        requirements['disposal_requirements'].extend([
            'Construction debris must be sorted for recycling',
            'Hazardous materials require special handling',
            'Disposal receipts required for permit closeout'
        ])
        
        return requirements
    
    def _determine_jurisdiction(self, address: Dict[str, str]) -> Dict[str, str]:
        """Determine the jurisdiction for permitting."""
        return {
            'city': address.get('city', 'Unknown'),
            'county': address.get('county', 'Unknown County'),
            'state': address.get('state', 'Unknown'),
            'permitting_authority': f"{address.get('city')} Building Department",
            'website': f"https://permits.{address.get('city', 'city').lower().replace(' ', '')}.gov"
        }
    
    def _validate_application(
        self,
        permit_type: PermitType,
        applicant_info: Dict[str, Any],
        project_info: Dict[str, Any],
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """Validate permit application completeness."""
        errors = []
        
        # Check applicant info
        required_applicant_fields = ['name', 'address', 'phone', 'email', 'license_number']
        for field in required_applicant_fields:
            if not applicant_info.get(field):
                errors.append(f"Missing applicant {field}")
                
        # Check project info
        required_project_fields = ['address', 'description', 'estimated_cost', 'start_date']
        for field in required_project_fields:
            if not project_info.get(field):
                errors.append(f"Missing project {field}")
                
        # Check documents
        if not documents:
            errors.append("No documents attached")
            
        return errors
    
    def _get_wind_rating(self, state: str) -> str:
        """Get wind rating requirement by state."""
        high_wind_states = ['FL', 'TX', 'LA', 'SC', 'NC', 'OK', 'KS']
        if state in high_wind_states:
            return 'Class H - High Wind (110-150 mph)'
        return 'Class D - Standard (90 mph)'
    
    def _get_fire_rating(self, location: Dict[str, str]) -> str:
        """Get fire rating requirement."""
        # Would check wildfire risk maps
        # For now, use simple logic
        high_risk_states = ['CA', 'CO', 'AZ', 'NM', 'NV']
        if location.get('state') in high_risk_states:
            return 'Class A - Highest Fire Resistance'
        return 'Class C - Standard Fire Resistance'
    
    def _get_snow_load(self, state: str) -> int:
        """Get snow load requirement in PSF."""
        heavy_snow_states = {
            'ME': 50, 'NH': 50, 'VT': 50, 'NY': 40,
            'MI': 40, 'WI': 40, 'MN': 50, 'MT': 40,
            'ID': 40, 'WY': 40, 'CO': 40, 'UT': 40
        }
        return heavy_snow_states.get(state, 20)
    
    def _get_inspection_requirements(
        self,
        inspection_type: InspectionType
    ) -> List[str]:
        """Get requirements for specific inspection type."""
        requirements = {
            InspectionType.PRE_CONSTRUCTION: [
                'Site must be accessible',
                'Property lines marked',
                'Permit posted visibly'
            ],
            InspectionType.FINAL: [
                'All work completed',
                'Site cleaned up',
                'All debris removed',
                'Warranty documentation ready'
            ]
        }
        
        return requirements.get(inspection_type, ['Standard inspection requirements'])
    
    async def get_energy_rebates(
        self,
        location: Dict[str, str],
        improvements: List[str]
    ) -> List[Dict[str, Any]]:
        """Get available energy efficiency rebates."""
        rebates = []
        
        # Federal rebates
        if 'solar' in improvements:
            rebates.append({
                'program': 'Federal Solar Tax Credit',
                'type': 'Tax Credit',
                'amount': '30% of system cost',
                'requirements': [
                    'New solar installation',
                    'Primary or secondary residence',
                    'System must be operational'
                ],
                'expires': '2032-12-31',
                'authority': 'IRS'
            })
            
        # State rebates (mock)
        if 'insulation' in improvements:
            rebates.append({
                'program': f"{location.get('state')} Energy Efficiency Rebate",
                'type': 'Cash Rebate',
                'amount': 'Up to $500',
                'requirements': [
                    'R-38 or higher insulation',
                    'Professional installation',
                    'Pre and post inspection'
                ],
                'expires': '2024-12-31',
                'authority': f"{location.get('state')} Energy Office"
            })
            
        return rebates