"""
Measurement Service for roofing calculations and estimations
"""
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from ..core.logging import logger


class RoofType(Enum):
    """Common roof types"""
    GABLE = "gable"
    HIP = "hip"
    FLAT = "flat"
    SHED = "shed"
    MANSARD = "mansard"
    GAMBREL = "gambrel"
    BUTTERFLY = "butterfly"


@dataclass
class RoofSection:
    """Represents a section of roof"""
    length: float
    width: float
    pitch: float  # Rise over run (e.g., 6/12 = 0.5)
    roof_type: RoofType
    
    @property
    def pitch_multiplier(self) -> float:
        """Calculate pitch multiplier for area adjustment"""
        # Formula: sqrt(1 + pitch^2)
        return math.sqrt(1 + self.pitch ** 2)
    
    @property
    def base_area(self) -> float:
        """Calculate base area (flat projection)"""
        return self.length * self.width
    
    @property
    def actual_area(self) -> float:
        """Calculate actual surface area accounting for pitch"""
        return self.base_area * self.pitch_multiplier


class MeasurementService:
    """Service for roof measurements and calculations"""
    
    # Standard roofing square = 100 sq ft
    SQUARE_FEET_PER_SQUARE = 100
    
    # Waste factors by complexity
    WASTE_FACTORS = {
        "simple": 0.10,     # 10% waste
        "moderate": 0.15,   # 15% waste
        "complex": 0.20,    # 20% waste
        "very_complex": 0.25  # 25% waste
    }
    
    # Standard bundle coverage (sq ft)
    BUNDLE_COVERAGE = {
        "3_tab_shingles": 33.33,  # 3 bundles per square
        "architectural_shingles": 33.33,
        "cedar_shakes": 25,  # 4 bundles per square
        "metal_panels": 100,  # Varies by panel
        "clay_tiles": 80,
        "concrete_tiles": 90
    }
    
    def calculate_roof_area(
        self,
        sections: List[Dict[str, Any]],
        include_waste: bool = True,
        complexity: str = "moderate"
    ) -> Dict[str, Any]:
        """
        Calculate total roof area from sections
        
        Args:
            sections: List of roof section measurements
            include_waste: Whether to include waste factor
            complexity: Roof complexity for waste calculation
        
        Returns:
            Area calculations and material requirements
        """
        try:
            roof_sections = []
            total_base_area = 0
            total_actual_area = 0
            
            # Process each section
            for section_data in sections:
                section = RoofSection(
                    length=section_data['length'],
                    width=section_data['width'],
                    pitch=section_data.get('pitch', 0.5),  # Default 6/12 pitch
                    roof_type=RoofType(section_data.get('type', 'gable'))
                )
                roof_sections.append(section)
                total_base_area += section.base_area
                total_actual_area += section.actual_area
            
            # Apply waste factor
            waste_factor = self.WASTE_FACTORS.get(complexity, 0.15)
            total_with_waste = total_actual_area * (1 + waste_factor)
            
            # Calculate squares
            squares = total_actual_area / self.SQUARE_FEET_PER_SQUARE
            squares_with_waste = total_with_waste / self.SQUARE_FEET_PER_SQUARE
            
            return {
                'success': True,
                'measurements': {
                    'base_area_sqft': round(total_base_area, 2),
                    'actual_area_sqft': round(total_actual_area, 2),
                    'area_with_waste_sqft': round(total_with_waste, 2) if include_waste else None,
                    'squares': round(squares, 2),
                    'squares_with_waste': round(squares_with_waste, 2) if include_waste else None,
                    'waste_percentage': waste_factor * 100 if include_waste else 0,
                    'sections_count': len(sections)
                },
                'sections': [
                    {
                        'base_area': round(s.base_area, 2),
                        'actual_area': round(s.actual_area, 2),
                        'pitch_multiplier': round(s.pitch_multiplier, 3),
                        'type': s.roof_type.value
                    } for s in roof_sections
                ]
            }
            
        except Exception as e:
            logger.error(f"Roof area calculation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def calculate_materials(
        self,
        area_sqft: float,
        material_type: str = "architectural_shingles",
        include_accessories: bool = True
    ) -> Dict[str, Any]:
        """
        Calculate material requirements for given area
        
        Args:
            area_sqft: Total roof area in square feet
            material_type: Type of roofing material
            include_accessories: Include underlayment, nails, etc.
        
        Returns:
            Material requirements
        """
        try:
            squares = area_sqft / self.SQUARE_FEET_PER_SQUARE
            bundle_coverage = self.BUNDLE_COVERAGE.get(material_type, 33.33)
            bundles_needed = math.ceil(area_sqft / bundle_coverage)
            
            materials = {
                'primary_material': {
                    'type': material_type,
                    'squares': round(squares, 2),
                    'bundles': bundles_needed,
                    'coverage_per_bundle': bundle_coverage
                }
            }
            
            if include_accessories:
                # Underlayment (15# or 30# felt)
                underlayment_rolls = math.ceil(area_sqft / 400)  # 400 sqft per roll
                
                # Ridge cap (estimate 35 linear feet per 100 sqft for average roof)
                ridge_linear_feet = (area_sqft / 100) * 35
                ridge_bundles = math.ceil(ridge_linear_feet / 35)  # 35 LF per bundle
                
                # Nails (1.5 lbs per square)
                nails_lbs = math.ceil(squares * 1.5)
                
                # Drip edge (perimeter estimate)
                perimeter_estimate = math.sqrt(area_sqft) * 4  # Rough estimate
                drip_edge_pieces = math.ceil(perimeter_estimate / 10)  # 10' pieces
                
                materials['accessories'] = {
                    'underlayment_rolls': underlayment_rolls,
                    'ridge_cap_bundles': ridge_bundles,
                    'nails_lbs': nails_lbs,
                    'drip_edge_pieces': drip_edge_pieces,
                    'ice_water_shield_rolls': math.ceil(perimeter_estimate / 75)  # 75 LF per roll
                }
            
            return {
                'success': True,
                'materials': materials,
                'area_sqft': area_sqft,
                'total_squares': round(squares, 2)
            }
            
        except Exception as e:
            logger.error(f"Material calculation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def estimate_from_footprint(
        self,
        length: float,
        width: float,
        stories: int = 1,
        roof_type: str = "gable",
        pitch: float = 0.5,
        overhang: float = 1.0
    ) -> Dict[str, Any]:
        """
        Estimate roof area from building footprint
        
        Args:
            length: Building length
            width: Building width
            stories: Number of stories
            roof_type: Type of roof
            pitch: Roof pitch (rise/run)
            overhang: Roof overhang in feet
        
        Returns:
            Estimated measurements
        """
        try:
            # Adjust for overhang
            roof_length = length + (2 * overhang)
            roof_width = width + (2 * overhang)
            
            # Base area calculation
            base_area = roof_length * roof_width
            
            # Adjust for roof type
            if roof_type == "gable":
                # Two rectangular sections
                sections = [
                    {
                        'length': roof_length,
                        'width': roof_width / 2,
                        'pitch': pitch,
                        'type': 'gable'
                    },
                    {
                        'length': roof_length,
                        'width': roof_width / 2,
                        'pitch': pitch,
                        'type': 'gable'
                    }
                ]
            elif roof_type == "hip":
                # Four triangular/trapezoidal sections (simplified)
                # Hip roofs have approximately 1.1x the area of gable roofs
                area_multiplier = 1.1
                sections = [
                    {
                        'length': roof_length,
                        'width': roof_width,
                        'pitch': pitch,
                        'type': 'hip'
                    }
                ]
            elif roof_type == "flat":
                sections = [
                    {
                        'length': roof_length,
                        'width': roof_width,
                        'pitch': 0,
                        'type': 'flat'
                    }
                ]
            else:
                # Default to gable
                sections = [
                    {
                        'length': roof_length,
                        'width': roof_width,
                        'pitch': pitch,
                        'type': roof_type
                    }
                ]
            
            # Calculate area
            result = self.calculate_roof_area(sections)
            
            if result['success']:
                result['footprint'] = {
                    'building_length': length,
                    'building_width': width,
                    'stories': stories,
                    'roof_type': roof_type,
                    'pitch': pitch,
                    'overhang': overhang
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Footprint estimation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def calculate_pitch(
        self,
        rise: float,
        run: float
    ) -> Dict[str, Any]:
        """
        Calculate pitch and related values
        
        Args:
            rise: Vertical rise
            run: Horizontal run
        
        Returns:
            Pitch calculations
        """
        try:
            pitch_ratio = rise / run
            pitch_degrees = math.degrees(math.atan(pitch_ratio))
            pitch_multiplier = math.sqrt(1 + pitch_ratio ** 2)
            
            # Common pitch notation (e.g., "6/12")
            pitch_notation = f"{int(rise)}/{int(run)}" if run == 12 else f"{rise}/{run}"
            
            return {
                'success': True,
                'pitch': {
                    'ratio': round(pitch_ratio, 3),
                    'degrees': round(pitch_degrees, 1),
                    'notation': pitch_notation,
                    'multiplier': round(pitch_multiplier, 3),
                    'rise': rise,
                    'run': run
                }
            }
            
        except Exception as e:
            logger.error(f"Pitch calculation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Create singleton instance
measurement_service = MeasurementService()


# Convenience functions
def calculate_roof_area(*args, **kwargs):
    return measurement_service.calculate_roof_area(*args, **kwargs)

def calculate_materials(*args, **kwargs):
    return measurement_service.calculate_materials(*args, **kwargs)

def estimate_from_footprint(*args, **kwargs):
    return measurement_service.estimate_from_footprint(*args, **kwargs)