"""
Maps Integration Service for location and geocoding
"""
import httpx
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote
from ..core.logging import logger
from ..core.settings import settings


class MapsService:
    """Service for maps and geocoding functionality"""
    
    def __init__(self):
        self.google_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None)
        self.mapbox_api_key = getattr(settings, 'MAPBOX_API_KEY', None)
        self.geocoding_api = "https://maps.googleapis.com/maps/api/geocode/json"
        self.places_api = "https://maps.googleapis.com/maps/api/place"
        self.directions_api = "https://maps.googleapis.com/maps/api/directions/json"
        self.static_map_api = "https://maps.googleapis.com/maps/api/staticmap"
    
    async def geocode_address(
        self,
        address: str,
        use_mapbox: bool = False
    ) -> Dict[str, Any]:
        """
        Convert address to coordinates
        
        Args:
            address: Street address
            use_mapbox: Use Mapbox instead of Google
        
        Returns:
            Geocoding results with coordinates
        """
        try:
            if use_mapbox and self.mapbox_api_key:
                # Use Mapbox Geocoding
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://api.mapbox.com/geocoding/v5/mapbox.places/{quote(address)}.json",
                        params={
                            'access_token': self.mapbox_api_key,
                            'limit': 1
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data['features']:
                            feature = data['features'][0]
                            return {
                                'success': True,
                                'location': {
                                    'lat': feature['center'][1],
                                    'lng': feature['center'][0],
                                    'formatted_address': feature['place_name'],
                                    'place_id': feature['id']
                                }
                            }
            
            elif self.google_api_key:
                # Use Google Geocoding
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        self.geocoding_api,
                        params={
                            'address': address,
                            'key': self.google_api_key
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data['status'] == 'OK' and data['results']:
                            result = data['results'][0]
                            return {
                                'success': True,
                                'location': {
                                    'lat': result['geometry']['location']['lat'],
                                    'lng': result['geometry']['location']['lng'],
                                    'formatted_address': result['formatted_address'],
                                    'place_id': result.get('place_id'),
                                    'types': result.get('types', [])
                                }
                            }
            
            return {
                'success': False,
                'error': 'No geocoding API key configured'
            }
            
        except Exception as e:
            logger.error(f"Geocoding failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Convert coordinates to address
        
        Args:
            latitude: Latitude
            longitude: Longitude
        
        Returns:
            Address information
        """
        try:
            if not self.google_api_key:
                return {
                    'success': False,
                    'error': 'Google Maps API key not configured'
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.geocoding_api,
                    params={
                        'latlng': f"{latitude},{longitude}",
                        'key': self.google_api_key
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK' and data['results']:
                        result = data['results'][0]
                        
                        # Parse address components
                        components = {}
                        for comp in result.get('address_components', []):
                            types = comp.get('types', [])
                            if 'street_number' in types:
                                components['street_number'] = comp['long_name']
                            elif 'route' in types:
                                components['street'] = comp['long_name']
                            elif 'locality' in types:
                                components['city'] = comp['long_name']
                            elif 'administrative_area_level_1' in types:
                                components['state'] = comp['short_name']
                            elif 'postal_code' in types:
                                components['zip_code'] = comp['long_name']
                            elif 'country' in types:
                                components['country'] = comp['long_name']
                        
                        return {
                            'success': True,
                            'address': {
                                'formatted': result['formatted_address'],
                                'components': components,
                                'place_id': result.get('place_id'),
                                'types': result.get('types', [])
                            }
                        }
            
            return {
                'success': False,
                'error': 'Reverse geocoding failed'
            }
            
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def calculate_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Dict[str, Any]:
        """
        Calculate distance between two points
        
        Args:
            origin: (latitude, longitude) tuple
            destination: (latitude, longitude) tuple
            mode: Travel mode ('driving', 'walking', 'bicycling', 'transit')
        
        Returns:
            Distance and duration information
        """
        try:
            if not self.google_api_key:
                # Use Haversine formula for straight-line distance
                import math
                
                lat1, lon1 = origin
                lat2, lon2 = destination
                
                # Convert to radians
                lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
                
                # Haversine formula
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                c = 2 * math.asin(math.sqrt(a))
                r = 3956  # Radius of Earth in miles
                
                distance_miles = c * r
                
                return {
                    'success': True,
                    'distance': {
                        'value': distance_miles,
                        'unit': 'miles',
                        'text': f"{distance_miles:.1f} miles"
                    },
                    'duration': None,
                    'method': 'haversine'
                }
            
            # Use Google Directions API
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.directions_api,
                    params={
                        'origin': f"{origin[0]},{origin[1]}",
                        'destination': f"{destination[0]},{destination[1]}",
                        'mode': mode,
                        'key': self.google_api_key
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK' and data['routes']:
                        route = data['routes'][0]['legs'][0]
                        
                        return {
                            'success': True,
                            'distance': {
                                'value': route['distance']['value'] / 1609.34,  # Convert meters to miles
                                'unit': 'miles',
                                'text': route['distance']['text']
                            },
                            'duration': {
                                'value': route['duration']['value'] / 60,  # Convert seconds to minutes
                                'unit': 'minutes',
                                'text': route['duration']['text']
                            },
                            'method': 'google_directions'
                        }
            
            return {
                'success': False,
                'error': 'Distance calculation failed'
            }
            
        except Exception as e:
            logger.error(f"Distance calculation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def search_nearby_places(
        self,
        latitude: float,
        longitude: float,
        place_type: str = "roofing_contractor",
        radius: int = 5000  # meters
    ) -> Dict[str, Any]:
        """
        Search for nearby places
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            place_type: Type of place to search
            radius: Search radius in meters
        
        Returns:
            List of nearby places
        """
        try:
            if not self.google_api_key:
                return {
                    'success': False,
                    'error': 'Google Maps API key not configured'
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.places_api}/nearbysearch/json",
                    params={
                        'location': f"{latitude},{longitude}",
                        'radius': radius,
                        'type': place_type,
                        'key': self.google_api_key
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK':
                        places = []
                        for place in data.get('results', []):
                            places.append({
                                'name': place.get('name'),
                                'address': place.get('vicinity'),
                                'place_id': place.get('place_id'),
                                'rating': place.get('rating'),
                                'user_ratings': place.get('user_ratings_total'),
                                'location': {
                                    'lat': place['geometry']['location']['lat'],
                                    'lng': place['geometry']['location']['lng']
                                },
                                'types': place.get('types', []),
                                'business_status': place.get('business_status')
                            })
                        
                        return {
                            'success': True,
                            'places': places,
                            'count': len(places)
                        }
            
            return {
                'success': False,
                'error': 'Places search failed'
            }
            
        except Exception as e:
            logger.error(f"Places search failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_static_map_url(
        self,
        latitude: float,
        longitude: float,
        zoom: int = 17,
        size: str = "600x400",
        maptype: str = "satellite",
        markers: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate static map URL
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            zoom: Zoom level (1-20)
            size: Image size (e.g., "600x400")
            maptype: Map type ('roadmap', 'satellite', 'hybrid', 'terrain')
            markers: Optional list of markers
        
        Returns:
            Static map URL
        """
        try:
            if not self.google_api_key:
                return {
                    'success': False,
                    'error': 'Google Maps API key not configured'
                }
            
            params = {
                'center': f"{latitude},{longitude}",
                'zoom': zoom,
                'size': size,
                'maptype': maptype,
                'key': self.google_api_key
            }
            
            # Add markers if provided
            if markers:
                marker_strings = []
                for marker in markers:
                    marker_str = []
                    if marker.get('color'):
                        marker_str.append(f"color:{marker['color']}")
                    if marker.get('label'):
                        marker_str.append(f"label:{marker['label']}")
                    marker_str.append(f"{marker['lat']},{marker['lng']}")
                    marker_strings.append("|".join(marker_str))
                params['markers'] = marker_strings
            else:
                # Add default center marker
                params['markers'] = f"color:red|{latitude},{longitude}"
            
            # Build URL
            param_strings = []
            for key, value in params.items():
                if isinstance(value, list):
                    for v in value:
                        param_strings.append(f"{key}={quote(str(v))}")
                else:
                    param_strings.append(f"{key}={quote(str(value))}")
            
            url = f"{self.static_map_api}?{'&'.join(param_strings)}"
            
            return {
                'success': True,
                'url': url,
                'parameters': params
            }
            
        except Exception as e:
            logger.error(f"Static map URL generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Create singleton instance
maps_service = MapsService()


# Convenience functions
async def geocode_address(*args, **kwargs):
    return await maps_service.geocode_address(*args, **kwargs)

async def reverse_geocode(*args, **kwargs):
    return await maps_service.reverse_geocode(*args, **kwargs)

async def calculate_distance(*args, **kwargs):
    return await maps_service.calculate_distance(*args, **kwargs)

async def search_nearby_places(*args, **kwargs):
    return await maps_service.search_nearby_places(*args, **kwargs)