"""
Compliance checking service for regulatory requirements.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import uuid


class ComplianceType(str, Enum):
    BUILDING_CODE = "building_code"
    SAFETY_REGULATION = "safety_regulation"
    ENVIRONMENTAL = "environmental"
    PERMIT = "permit"
    LICENSE = "license"
    INSURANCE = "insurance"
    WARRANTY = "warranty"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"
    EXPIRED = "expired"
    WARNING = "warning"


class ComplianceCheck:
    """Individual compliance check result."""
    
    def __init__(
        self,
        check_type: ComplianceType,
        status: ComplianceStatus,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        expiry_date: Optional[datetime] = None
    ):
        self.id = str(uuid.uuid4())
        self.check_type = check_type
        self.status = status
        self.message = message
        self.details = details or {}
        self.expiry_date = expiry_date
        self.checked_at = datetime.utcnow()


class ComplianceChecker:
    """Service for checking regulatory compliance."""
    
    def __init__(self):
        self.compliance_rules = self._load_compliance_rules()
        self.check_history = {}
    
    def _load_compliance_rules(self) -> Dict[str, Any]:
        """Load compliance rules and requirements."""
        return {
            ComplianceType.BUILDING_CODE: {
                "min_pitch": 2.0,
                "max_pitch": 12.0,
                "min_ventilation_sqft": 150,
                "required_ice_dam_protection": True,
                "fire_rating_required": "Class A"
            },
            ComplianceType.SAFETY_REGULATION: {
                "fall_protection_required": True,
                "min_workers": 2,
                "safety_equipment": ["harness", "hard_hat", "safety_glasses"],
                "osha_compliant": True
            },
            ComplianceType.ENVIRONMENTAL: {
                "disposal_method": "licensed_facility",
                "recycling_required": True,
                "hazmat_handling": "certified_only"
            },
            ComplianceType.PERMIT: {
                "building_permit": True,
                "electrical_permit": False,
                "demo_permit": "if_tearoff"
            },
            ComplianceType.LICENSE: {
                "contractor_license": "required",
                "business_license": "required",
                "specialty_endorsements": ["roofing"]
            },
            ComplianceType.INSURANCE: {
                "general_liability_min": 1000000,
                "workers_comp": "required",
                "bond_amount": 50000
            },
            ComplianceType.WARRANTY: {
                "manufacturer_warranty": "required",
                "workmanship_warranty_years": 10,
                "transferable": True
            }
        }
    
    async def check_project_compliance(
        self,
        project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check all compliance requirements for a project."""
        checks = []
        overall_compliant = True
        
        # Building code compliance
        building_check = await self._check_building_code(project_data)
        checks.append(building_check)
        if building_check.status != ComplianceStatus.COMPLIANT:
            overall_compliant = False
        
        # Safety compliance
        safety_check = await self._check_safety_compliance(project_data)
        checks.append(safety_check)
        if safety_check.status != ComplianceStatus.COMPLIANT:
            overall_compliant = False
        
        # Environmental compliance
        env_check = await self._check_environmental_compliance(project_data)
        checks.append(env_check)
        if env_check.status != ComplianceStatus.COMPLIANT:
            overall_compliant = False
        
        # Permit compliance
        permit_check = await self._check_permits(project_data)
        checks.append(permit_check)
        if permit_check.status == ComplianceStatus.NON_COMPLIANT:
            overall_compliant = False
        
        # License compliance
        license_check = await self._check_licenses(project_data)
        checks.append(license_check)
        if license_check.status != ComplianceStatus.COMPLIANT:
            overall_compliant = False
        
        # Insurance compliance
        insurance_check = await self._check_insurance(project_data)
        checks.append(insurance_check)
        if insurance_check.status != ComplianceStatus.COMPLIANT:
            overall_compliant = False
        
        # Store check history
        project_id = project_data.get('id', str(uuid.uuid4()))
        self.check_history[project_id] = {
            'checks': checks,
            'checked_at': datetime.utcnow(),
            'overall_compliant': overall_compliant
        }
        
        return {
            'project_id': project_id,
            'overall_compliant': overall_compliant,
            'checks': [
                {
                    'type': check.check_type.value,
                    'status': check.status.value,
                    'message': check.message,
                    'details': check.details,
                    'expiry_date': check.expiry_date.isoformat() if check.expiry_date else None
                }
                for check in checks
            ],
            'checked_at': datetime.utcnow().isoformat()
        }
    
    async def _check_building_code(
        self,
        project_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check building code compliance."""
        rules = self.compliance_rules[ComplianceType.BUILDING_CODE]
        issues = []
        
        # Check roof pitch
        pitch = project_data.get('roof_pitch', 0)
        if pitch < rules['min_pitch'] or pitch > rules['max_pitch']:
            issues.append(f"Roof pitch {pitch}/12 outside allowed range")
        
        # Check ventilation
        roof_area = project_data.get('roof_area', 0)
        ventilation_sqft = project_data.get('ventilation_sqft', 0)
        if roof_area > 0 and ventilation_sqft < roof_area / rules['min_ventilation_sqft']:
            issues.append("Insufficient ventilation for roof area")
        
        # Check ice dam protection
        if project_data.get('climate_zone') in ['cold', 'very_cold']:
            if not project_data.get('ice_dam_protection'):
                issues.append("Ice dam protection required for climate zone")
        
        if issues:
            return ComplianceCheck(
                ComplianceType.BUILDING_CODE,
                ComplianceStatus.NON_COMPLIANT,
                "Building code violations found",
                {'issues': issues}
            )
        
        return ComplianceCheck(
            ComplianceType.BUILDING_CODE,
            ComplianceStatus.COMPLIANT,
            "Meets all building code requirements"
        )
    
    async def _check_safety_compliance(
        self,
        project_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check safety regulation compliance."""
        rules = self.compliance_rules[ComplianceType.SAFETY_REGULATION]
        issues = []
        
        # Check crew size
        crew_size = project_data.get('crew_size', 0)
        if crew_size < rules['min_workers']:
            issues.append(f"Minimum {rules['min_workers']} workers required")
        
        # Check safety equipment
        equipment = project_data.get('safety_equipment', [])
        missing = [eq for eq in rules['safety_equipment'] if eq not in equipment]
        if missing:
            issues.append(f"Missing required safety equipment: {', '.join(missing)}")
        
        # Check fall protection for steep roofs
        if project_data.get('roof_pitch', 0) > 6:
            if not project_data.get('fall_protection'):
                issues.append("Fall protection required for steep slope")
        
        if issues:
            return ComplianceCheck(
                ComplianceType.SAFETY_REGULATION,
                ComplianceStatus.NON_COMPLIANT,
                "Safety violations found",
                {'issues': issues}
            )
        
        return ComplianceCheck(
            ComplianceType.SAFETY_REGULATION,
            ComplianceStatus.COMPLIANT,
            "Meets all safety requirements"
        )
    
    async def _check_environmental_compliance(
        self,
        project_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check environmental compliance."""
        rules = self.compliance_rules[ComplianceType.ENVIRONMENTAL]
        issues = []
        
        # Check disposal plan
        if project_data.get('disposal_method') != rules['disposal_method']:
            issues.append("Must use licensed disposal facility")
        
        # Check recycling
        if rules['recycling_required'] and not project_data.get('recycling_plan'):
            issues.append("Recycling plan required")
        
        # Check for asbestos in old roofs
        if project_data.get('building_age', 0) > 40:
            if not project_data.get('asbestos_test'):
                issues.append("Asbestos testing required for buildings over 40 years")
        
        if issues:
            return ComplianceCheck(
                ComplianceType.ENVIRONMENTAL,
                ComplianceStatus.WARNING,
                "Environmental compliance issues",
                {'issues': issues}
            )
        
        return ComplianceCheck(
            ComplianceType.ENVIRONMENTAL,
            ComplianceStatus.COMPLIANT,
            "Environmentally compliant"
        )
    
    async def _check_permits(
        self,
        project_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check permit requirements."""
        rules = self.compliance_rules[ComplianceType.PERMIT]
        required_permits = []
        
        # Building permit always required
        if rules['building_permit']:
            required_permits.append('building')
        
        # Electrical permit if solar or electrical work
        if project_data.get('includes_electrical'):
            required_permits.append('electrical')
        
        # Demo permit for tear-offs
        if project_data.get('project_type') == 'tear_off':
            required_permits.append('demolition')
        
        # Check which permits are obtained
        obtained_permits = project_data.get('permits', [])
        missing_permits = [p for p in required_permits if p not in obtained_permits]
        
        if missing_permits:
            return ComplianceCheck(
                ComplianceType.PERMIT,
                ComplianceStatus.PENDING_REVIEW,
                "Permits pending",
                {'required': required_permits, 'missing': missing_permits}
            )
        
        return ComplianceCheck(
            ComplianceType.PERMIT,
            ComplianceStatus.COMPLIANT,
            "All required permits obtained",
            {'permits': required_permits}
        )
    
    async def _check_licenses(
        self,
        project_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check license compliance."""
        contractor_data = project_data.get('contractor', {})
        issues = []
        
        # Check contractor license
        if not contractor_data.get('license_number'):
            issues.append("Valid contractor license required")
        else:
            # Check expiration
            expiry = contractor_data.get('license_expiry')
            if expiry:
                expiry_date = datetime.fromisoformat(expiry)
                if expiry_date < datetime.utcnow():
                    issues.append("Contractor license expired")
                elif expiry_date < datetime.utcnow() + timedelta(days=30):
                    issues.append("Contractor license expiring soon")
        
        # Check business license
        if not contractor_data.get('business_license'):
            issues.append("Business license required")
        
        # Check specialty endorsements
        endorsements = contractor_data.get('endorsements', [])
        if 'roofing' not in endorsements:
            issues.append("Roofing endorsement required")
        
        if issues:
            status = ComplianceStatus.NON_COMPLIANT if len(issues) > 1 else ComplianceStatus.WARNING
            return ComplianceCheck(
                ComplianceType.LICENSE,
                status,
                "License issues found",
                {'issues': issues}
            )
        
        return ComplianceCheck(
            ComplianceType.LICENSE,
            ComplianceStatus.COMPLIANT,
            "All licenses valid and current"
        )
    
    async def _check_insurance(
        self,
        project_data: Dict[str, Any]
    ) -> ComplianceCheck:
        """Check insurance compliance."""
        rules = self.compliance_rules[ComplianceType.INSURANCE]
        contractor_data = project_data.get('contractor', {})
        issues = []
        
        # Check general liability
        gl_coverage = contractor_data.get('general_liability_coverage', 0)
        if gl_coverage < rules['general_liability_min']:
            issues.append(f"General liability must be at least ${rules['general_liability_min']:,}")
        
        # Check workers comp
        if not contractor_data.get('workers_comp_policy'):
            issues.append("Workers compensation insurance required")
        
        # Check bond
        bond_amount = contractor_data.get('bond_amount', 0)
        if bond_amount < rules['bond_amount']:
            issues.append(f"Bond must be at least ${rules['bond_amount']:,}")
        
        # Check expiration dates
        insurance_expiry = contractor_data.get('insurance_expiry')
        if insurance_expiry:
            expiry_date = datetime.fromisoformat(insurance_expiry)
            if expiry_date < datetime.utcnow():
                issues.append("Insurance coverage expired")
                return ComplianceCheck(
                    ComplianceType.INSURANCE,
                    ComplianceStatus.EXPIRED,
                    "Insurance expired",
                    {'issues': issues},
                    expiry_date=expiry_date
                )
        
        if issues:
            return ComplianceCheck(
                ComplianceType.INSURANCE,
                ComplianceStatus.NON_COMPLIANT,
                "Insurance requirements not met",
                {'issues': issues}
            )
        
        return ComplianceCheck(
            ComplianceType.INSURANCE,
            ComplianceStatus.COMPLIANT,
            "Insurance coverage adequate"
        )
    
    async def generate_compliance_report(
        self,
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """Generate detailed compliance report for a project."""
        if project_id not in self.check_history:
            return None
        
        history = self.check_history[project_id]
        report = {
            'project_id': project_id,
            'report_date': datetime.utcnow().isoformat(),
            'overall_status': 'COMPLIANT' if history['overall_compliant'] else 'NON-COMPLIANT',
            'last_checked': history['checked_at'].isoformat(),
            'compliance_summary': {},
            'required_actions': [],
            'warnings': []
        }
        
        for check in history['checks']:
            check_type = check.check_type.value
            status = check.status.value
            
            report['compliance_summary'][check_type] = {
                'status': status,
                'message': check.message,
                'details': check.details
            }
            
            if check.status == ComplianceStatus.NON_COMPLIANT:
                report['required_actions'].extend(
                    check.details.get('issues', [])
                )
            elif check.status == ComplianceStatus.WARNING:
                report['warnings'].extend(
                    check.details.get('issues', [])
                )
        
        return report
    
    def get_compliance_requirements(
        self,
        project_type: str,
        location: Dict[str, str]
    ) -> Dict[str, List[str]]:
        """Get compliance requirements for a project type and location."""
        # This would be expanded with location-specific requirements
        base_requirements = {
            'permits': ['building'],
            'licenses': ['contractor', 'business'],
            'insurance': ['general_liability', 'workers_comp'],
            'inspections': ['pre_work', 'final']
        }
        
        # Add location-specific requirements
        state = location.get('state', '').upper()
        if state in ['CA', 'FL', 'TX']:
            base_requirements['permits'].append('hurricane_compliance')
        
        if project_type == 'commercial':
            base_requirements['permits'].append('commercial_building')
            base_requirements['insurance'].append('commercial_liability')
        
        return base_requirements