"""
Health monitoring module for all integrated services
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from apps.backend.core.settings import Settings
from apps.backend.connectors import get_connector


logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitor health of all integrated services"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._health_cache = {}
        self._cache_lock = threading.Lock()
        self._cache_ttl = 60  # Cache for 60 seconds
        self._executor = ThreadPoolExecutor(max_workers=10)
    
    def check_service(self, service_name: str) -> Dict[str, Any]:
        """
        Check health of a specific service
        
        Returns:
            dict: Health check result
        """
        # Check cache first
        cached_result = self._get_cached_result(service_name)
        if cached_result:
            logger.debug(f"Using cached health check for {service_name}")
            return cached_result
        
        try:
            connector = get_connector(service_name, self.settings)
            result = connector.check_health()
            
            # Cache the result
            self._cache_result(service_name, result)
            
            # Log if unhealthy
            if not result.get('healthy', False):
                logger.warning(f"Service {service_name} is unhealthy: {result.get('message')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking {service_name}: {e}")
            error_result = {
                'healthy': False,
                'response_time': 0,
                'message': f"Error: {str(e)}",
                'checked_at': datetime.utcnow().isoformat()
            }
            self._cache_result(service_name, error_result)
            return error_result
    
    def check_all_services(self, parallel: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all enabled services
        
        Args:
            parallel: Whether to check services in parallel
            
        Returns:
            dict: Health status for all services
        """
        enabled_services = self.settings.get_enabled_services()
        results = {}
        
        if parallel:
            # Check services in parallel
            futures = {
                self._executor.submit(self.check_service, service): service
                for service in enabled_services
            }
            
            for future in as_completed(futures):
                service = futures[future]
                try:
                    results[service] = future.result()
                except Exception as e:
                    logger.error(f"Error checking {service}: {e}")
                    results[service] = {
                        'healthy': False,
                        'message': f"Check failed: {str(e)}"
                    }
        else:
            # Check services sequentially
            for service in enabled_services:
                results[service] = self.check_service(service)
        
        return results
    
    def get_unhealthy_services(self) -> List[Dict[str, Any]]:
        """Get list of currently unhealthy services"""
        all_results = self.check_all_services()
        unhealthy = []
        
        for service, result in all_results.items():
            if not result.get('healthy', False):
                unhealthy.append({
                    'service': service,
                    'message': result.get('message', 'Unknown error'),
                    'checked_at': result.get('checked_at'),
                    'response_time': result.get('response_time', 0)
                })
        
        return unhealthy
    
    def get_service_uptime(self, service_name: str, 
                          hours: int = 24) -> Dict[str, Any]:
        """
        Calculate service uptime percentage
        
        Args:
            service_name: Name of the service
            hours: Number of hours to calculate uptime for
            
        Returns:
            dict: Uptime statistics
        """
        # This would typically query from a database
        # For now, return current status
        current_health = self.check_service(service_name)
        
        return {
            'service': service_name,
            'current_status': 'up' if current_health['healthy'] else 'down',
            'uptime_percentage': 100.0 if current_health['healthy'] else 0.0,
            'period_hours': hours,
            'last_check': current_health.get('checked_at')
        }
    
    def get_response_times(self) -> Dict[str, float]:
        """Get response times for all services"""
        all_results = self.check_all_services()
        response_times = {}
        
        for service, result in all_results.items():
            response_times[service] = result.get('response_time', 0)
        
        return response_times
    
    def _get_cached_result(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get cached health check result if still valid"""
        with self._cache_lock:
            if service_name in self._health_cache:
                cached_time, cached_result = self._health_cache[service_name]
                if time.time() - cached_time < self._cache_ttl:
                    return cached_result
        return None
    
    def _cache_result(self, service_name: str, result: Dict[str, Any]):
        """Cache health check result"""
        with self._cache_lock:
            self._health_cache[service_name] = (time.time(), result)
    
    def clear_cache(self):
        """Clear health check cache"""
        with self._cache_lock:
            self._health_cache.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get overall health summary"""
        all_results = self.check_all_services()
        
        total_services = len(all_results)
        healthy_services = sum(1 for r in all_results.values() if r.get('healthy', False))
        unhealthy_services = total_services - healthy_services
        
        avg_response_time = 0
        if all_results:
            response_times = [r.get('response_time', 0) for r in all_results.values()]
            avg_response_time = sum(response_times) / len(response_times)
        
        return {
            'total_services': total_services,
            'healthy_services': healthy_services,
            'unhealthy_services': unhealthy_services,
            'health_percentage': (healthy_services / total_services * 100) if total_services > 0 else 0,
            'average_response_time': round(avg_response_time, 2),
            'services': all_results,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def __del__(self):
        """Clean up executor on deletion"""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)