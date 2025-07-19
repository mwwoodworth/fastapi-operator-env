"""
Weather API Integration Client
"""
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from ..core.settings import settings
from ..core.logging import logger


class WeatherAPIClient:
    """Client for weather data integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENWEATHER_API_KEY', None)
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.geocoding_url = "https://api.openweathermap.org/geo/1.0"
    
    async def get_current_weather(
        self,
        latitude: float,
        longitude: float,
        units: str = "imperial"
    ) -> Dict[str, Any]:
        """
        Get current weather for location
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            units: Temperature units ('imperial', 'metric', 'kelvin')
        
        Returns:
            Current weather data
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'error': 'Weather API key not configured'
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/weather",
                    params={
                        'lat': latitude,
                        'lon': longitude,
                        'appid': self.api_key,
                        'units': units
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'success': True,
                        'weather': {
                            'temperature': data['main']['temp'],
                            'feels_like': data['main']['feels_like'],
                            'humidity': data['main']['humidity'],
                            'pressure': data['main']['pressure'],
                            'description': data['weather'][0]['description'],
                            'icon': data['weather'][0]['icon'],
                            'wind_speed': data['wind']['speed'],
                            'wind_direction': data['wind'].get('deg'),
                            'clouds': data['clouds']['all'],
                            'visibility': data.get('visibility'),
                            'sunrise': datetime.fromtimestamp(data['sys']['sunrise']).isoformat(),
                            'sunset': datetime.fromtimestamp(data['sys']['sunset']).isoformat()
                        },
                        'location': {
                            'name': data['name'],
                            'country': data['sys']['country'],
                            'lat': data['coord']['lat'],
                            'lon': data['coord']['lon']
                        }
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Weather API error: {response.status_code}'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get current weather: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = 5,
        units: str = "imperial"
    ) -> Dict[str, Any]:
        """
        Get weather forecast
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            days: Number of days (max 5 for free tier)
            units: Temperature units
        
        Returns:
            Weather forecast data
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'error': 'Weather API key not configured'
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/forecast",
                    params={
                        'lat': latitude,
                        'lon': longitude,
                        'appid': self.api_key,
                        'units': units,
                        'cnt': days * 8  # 8 forecasts per day (3-hour intervals)
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Group forecasts by day
                    daily_forecasts = {}
                    for item in data['list']:
                        date = datetime.fromtimestamp(item['dt']).date().isoformat()
                        if date not in daily_forecasts:
                            daily_forecasts[date] = []
                        daily_forecasts[date].append({
                            'time': datetime.fromtimestamp(item['dt']).isoformat(),
                            'temperature': item['main']['temp'],
                            'feels_like': item['main']['feels_like'],
                            'humidity': item['main']['humidity'],
                            'description': item['weather'][0]['description'],
                            'icon': item['weather'][0]['icon'],
                            'wind_speed': item['wind']['speed'],
                            'precipitation': item.get('rain', {}).get('3h', 0) + item.get('snow', {}).get('3h', 0)
                        })
                    
                    return {
                        'success': True,
                        'forecast': daily_forecasts,
                        'location': {
                            'name': data['city']['name'],
                            'country': data['city']['country'],
                            'lat': data['city']['coord']['lat'],
                            'lon': data['city']['coord']['lon']
                        }
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Weather API error: {response.status_code}'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get weather forecast: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_weather_alerts(
        self,
        latitude: float,
        longitude: float
    ) -> Dict[str, Any]:
        """
        Get weather alerts for location
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
        
        Returns:
            Active weather alerts
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'error': 'Weather API key not configured'
                }
            
            # Use One Call API for alerts
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openweathermap.org/data/3.0/onecall",
                    params={
                        'lat': latitude,
                        'lon': longitude,
                        'appid': self.api_key,
                        'exclude': 'current,minutely,hourly,daily'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    alerts = data.get('alerts', [])
                    
                    return {
                        'success': True,
                        'alerts': [
                            {
                                'sender': alert.get('sender_name'),
                                'event': alert.get('event'),
                                'start': datetime.fromtimestamp(alert['start']).isoformat(),
                                'end': datetime.fromtimestamp(alert['end']).isoformat(),
                                'description': alert.get('description'),
                                'tags': alert.get('tags', [])
                            } for alert in alerts
                        ],
                        'alert_count': len(alerts)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Weather API error: {response.status_code}'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get weather alerts: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def geocode_location(
        self,
        location: str,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Convert location name to coordinates
        
        Args:
            location: Location name (city, state, country)
            limit: Maximum number of results
        
        Returns:
            Geocoding results
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'error': 'Weather API key not configured'
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.geocoding_url}/direct",
                    params={
                        'q': location,
                        'limit': limit,
                        'appid': self.api_key
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    return {
                        'success': True,
                        'results': [
                            {
                                'name': item['name'],
                                'state': item.get('state'),
                                'country': item['country'],
                                'lat': item['lat'],
                                'lon': item['lon']
                            } for item in data
                        ],
                        'count': len(data)
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Geocoding API error: {response.status_code}'
                    }
                    
        except Exception as e:
            logger.error(f"Failed to geocode location: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def is_suitable_for_roofing(
        self,
        latitude: float,
        longitude: float,
        hours_ahead: int = 24
    ) -> Dict[str, Any]:
        """
        Check if weather is suitable for roofing work
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            hours_ahead: Hours to check ahead
        
        Returns:
            Suitability assessment
        """
        try:
            # Get current weather
            current = await self.get_current_weather(latitude, longitude)
            if not current['success']:
                return current
            
            # Get forecast
            forecast = await self.get_forecast(latitude, longitude, days=2)
            if not forecast['success']:
                return forecast
            
            current_weather = current['weather']
            suitable = True
            warnings = []
            
            # Check temperature (not too hot or cold)
            temp = current_weather['temperature']
            if temp < 40:
                suitable = False
                warnings.append(f"Temperature too cold: {temp}°F")
            elif temp > 95:
                suitable = False
                warnings.append(f"Temperature too hot: {temp}°F")
            
            # Check wind speed (not too windy)
            wind = current_weather['wind_speed']
            if wind > 20:
                suitable = False
                warnings.append(f"Wind too strong: {wind} mph")
            
            # Check precipitation
            if 'rain' in current_weather['description'].lower() or 'snow' in current_weather['description'].lower():
                suitable = False
                warnings.append(f"Precipitation: {current_weather['description']}")
            
            # Check forecast for next hours
            rain_probability = 0
            for date_forecasts in list(forecast['forecast'].values())[:1]:  # Next 24 hours
                for hourly in date_forecasts[:8]:  # Next 8 3-hour periods
                    if hourly['precipitation'] > 0:
                        rain_probability += 1
            
            rain_chance = (rain_probability / 8) * 100
            if rain_chance > 30:
                warnings.append(f"High chance of rain: {rain_chance:.0f}%")
                suitable = False
            
            return {
                'success': True,
                'suitable': suitable,
                'warnings': warnings,
                'current_conditions': {
                    'temperature': temp,
                    'wind_speed': wind,
                    'description': current_weather['description'],
                    'humidity': current_weather['humidity']
                },
                'rain_chance_24h': rain_chance
            }
            
        except Exception as e:
            logger.error(f"Failed to assess roofing suitability: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Create singleton instance
weather_client = WeatherAPIClient()


# Convenience functions
async def get_current_weather(*args, **kwargs):
    return await weather_client.get_current_weather(*args, **kwargs)

async def get_weather_forecast(*args, **kwargs):
    return await weather_client.get_forecast(*args, **kwargs)

async def is_suitable_for_roofing(*args, **kwargs):
    return await weather_client.is_suitable_for_roofing(*args, **kwargs)