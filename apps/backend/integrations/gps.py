"""
GPS and location services integration.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import math
import uuid


class GPSIntegration:
    """Service for GPS tracking and location services."""
    
    def __init__(self):
        self.tracked_vehicles = {}
        self.geofences = {}
    
    async def track_vehicle(
        self,
        vehicle_id: str,
        latitude: float,
        longitude: float,
        speed: Optional[float] = None,
        heading: Optional[float] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Track vehicle location."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        location_data = {
            'vehicle_id': vehicle_id,
            'latitude': latitude,
            'longitude': longitude,
            'speed': speed,
            'heading': heading,
            'timestamp': timestamp.isoformat(),
            'address': await self._reverse_geocode(latitude, longitude)
        }
        
        # Store in tracking history
        if vehicle_id not in self.tracked_vehicles:
            self.tracked_vehicles[vehicle_id] = []
        
        self.tracked_vehicles[vehicle_id].append(location_data)
        
        # Check geofence violations
        violations = self._check_geofences(vehicle_id, latitude, longitude)
        
        return {
            'status': 'tracked',
            'location': location_data,
            'geofence_violations': violations
        }
    
    async def get_vehicle_location(
        self,
        vehicle_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get current vehicle location."""
        if vehicle_id in self.tracked_vehicles and self.tracked_vehicles[vehicle_id]:
            return self.tracked_vehicles[vehicle_id][-1]
        return None
    
    async def get_vehicle_history(
        self,
        vehicle_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get vehicle location history."""
        if vehicle_id not in self.tracked_vehicles:
            return []
        
        history = self.tracked_vehicles[vehicle_id]
        
        # Filter by time range if provided
        if start_time or end_time:
            filtered = []
            for loc in history:
                loc_time = datetime.fromisoformat(loc['timestamp'])
                if start_time and loc_time < start_time:
                    continue
                if end_time and loc_time > end_time:
                    continue
                filtered.append(loc)
            return filtered
        
        return history
    
    async def calculate_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        waypoints: Optional[List[Tuple[float, float]]] = None
    ) -> Dict[str, Any]:
        """Calculate optimal route between points."""
        # Mock route calculation
        distance = self._calculate_distance(start_lat, start_lon, end_lat, end_lon)
        duration_minutes = distance * 1.5  # Rough estimate
        
        route = {
            'start': {'lat': start_lat, 'lon': start_lon},
            'end': {'lat': end_lat, 'lon': end_lon},
            'waypoints': waypoints or [],
            'distance_km': round(distance, 2),
            'duration_minutes': round(duration_minutes, 0),
            'polyline': 'mock_polyline_string'  # Would be actual encoded route
        }
        
        return route
    
    async def create_geofence(
        self,
        name: str,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        alert_on_enter: bool = True,
        alert_on_exit: bool = True
    ) -> Dict[str, Any]:
        """Create a geofence for monitoring."""
        geofence_id = str(uuid.uuid4())
        
        self.geofences[geofence_id] = {
            'id': geofence_id,
            'name': name,
            'center': {'lat': center_lat, 'lon': center_lon},
            'radius_km': radius_km,
            'alert_on_enter': alert_on_enter,
            'alert_on_exit': alert_on_exit,
            'created_at': datetime.utcnow().isoformat()
        }
        
        return self.geofences[geofence_id]
    
    async def get_nearby_technicians(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 50
    ) -> List[Dict[str, Any]]:
        """Find technicians within radius of location."""
        nearby = []
        
        # Check all tracked vehicles (assuming they're technicians)
        for vehicle_id, history in self.tracked_vehicles.items():
            if history:
                last_location = history[-1]
                distance = self._calculate_distance(
                    latitude, longitude,
                    last_location['latitude'], last_location['longitude']
                )
                
                if distance <= radius_km:
                    nearby.append({
                        'vehicle_id': vehicle_id,
                        'distance_km': round(distance, 2),
                        'location': last_location,
                        'eta_minutes': round(distance * 1.5, 0)
                    })
        
        # Sort by distance
        nearby.sort(key=lambda x: x['distance_km'])
        return nearby
    
    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate distance between two points in kilometers."""
        # Haversine formula
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _check_geofences(
        self,
        vehicle_id: str,
        latitude: float,
        longitude: float
    ) -> List[Dict[str, Any]]:
        """Check if location violates any geofences."""
        violations = []
        
        for geofence in self.geofences.values():
            distance = self._calculate_distance(
                latitude, longitude,
                geofence['center']['lat'], geofence['center']['lon']
            )
            
            inside = distance <= geofence['radius_km']
            
            # Would need to track previous state to detect enter/exit
            if inside and geofence['alert_on_enter']:
                violations.append({
                    'geofence_id': geofence['id'],
                    'geofence_name': geofence['name'],
                    'violation_type': 'entered',
                    'vehicle_id': vehicle_id
                })
        
        return violations
    
    async def _reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> str:
        """Convert coordinates to address."""
        # Mock implementation - would use real geocoding service
        return f"{latitude:.4f}, {longitude:.4f}"


class GPSTracker:
    """Main GPS tracking service."""
    
    def __init__(self):
        self.integration = GPSIntegration()
    
    async def update_technician_location(
        self,
        technician_id: str,
        location_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update technician's GPS location."""
        return await self.integration.track_vehicle(
            vehicle_id=f"tech_{technician_id}",
            latitude=location_data['latitude'],
            longitude=location_data['longitude'],
            speed=location_data.get('speed'),
            heading=location_data.get('heading')
        )
    
    async def find_nearest_technician(
        self,
        job_location: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Find the nearest available technician to a job."""
        nearby = await self.integration.get_nearby_technicians(
            latitude=job_location['latitude'],
            longitude=job_location['longitude']
        )
        
        if nearby:
            return nearby[0]
        return None
    
    async def calculate_job_route(
        self,
        technician_id: str,
        job_location: Dict[str, float]
    ) -> Dict[str, Any]:
        """Calculate route from technician to job."""
        current_location = await self.integration.get_vehicle_location(
            f"tech_{technician_id}"
        )
        
        if current_location:
            return await self.integration.calculate_route(
                start_lat=current_location['latitude'],
                start_lon=current_location['longitude'],
                end_lat=job_location['latitude'],
                end_lon=job_location['longitude']
            )
        
        return {'error': 'Technician location not found'}