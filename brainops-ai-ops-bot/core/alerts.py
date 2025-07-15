"""
Alert management module for sending notifications across channels
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from pathlib import Path
import yaml

from config.settings import Settings
from connectors.slack import SlackConnector


logger = logging.getLogger(__name__)


class AlertManager:
    """Manage alerts across multiple channels"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._alert_history = defaultdict(list)
        self._history_lock = threading.Lock()
        self._cooldown_minutes = settings.alert_cooldown_minutes
        self._slack_connector = None
        
        # Load alert rules
        self.alert_rules = self._load_alert_rules()
        
        # Initialize connectors
        self._init_connectors()
    
    def _init_connectors(self):
        """Initialize alert channel connectors"""
        if self.settings.enable_slack_alerts and self.settings.slack_bot_token:
            try:
                slack_config = self.settings.get_service_config('slack')
                self._slack_connector = SlackConnector(slack_config)
                self._slack_connector.authenticate()
            except Exception as e:
                logger.error(f"Failed to initialize Slack connector: {e}")
    
    def _load_alert_rules(self) -> Dict[str, Any]:
        """Load alert rules from configuration file"""
        rules_file = Path(__file__).parent.parent / 'config' / 'alerts.yaml'
        
        if rules_file.exists():
            try:
                with open(rules_file, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load alert rules: {e}")
        
        # Default rules if file doesn't exist
        return {
            'severity_levels': {
                'critical': {
                    'channels': ['slack', 'email'],
                    'cooldown_minutes': 5,
                    'escalate_after': 3
                },
                'error': {
                    'channels': ['slack'],
                    'cooldown_minutes': 15,
                    'escalate_after': 5
                },
                'warning': {
                    'channels': ['slack'],
                    'cooldown_minutes': 30,
                    'escalate_after': 10
                },
                'info': {
                    'channels': ['slack'],
                    'cooldown_minutes': 60,
                    'escalate_after': None
                }
            },
            'service_rules': {
                'database': {
                    'down_severity': 'critical',
                    'slow_severity': 'warning'
                },
                'api': {
                    'down_severity': 'error',
                    'slow_severity': 'warning'
                }
            }
        }
    
    def send_alert(self, service: str, severity: str, message: str, 
                  details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Send an alert with cooldown management
        
        Args:
            service: Service name
            severity: Alert severity (critical, error, warning, info)
            message: Alert message
            details: Additional details
            
        Returns:
            bool: True if alert was sent
        """
        # Check cooldown
        if self._is_in_cooldown(service, severity):
            logger.debug(f"Alert for {service} is in cooldown period")
            return False
        
        # Record alert
        self._record_alert(service, severity)
        
        # Determine channels based on severity
        severity_config = self.alert_rules.get('severity_levels', {}).get(
            severity, {'channels': ['slack']}
        )
        channels = severity_config.get('channels', ['slack'])
        
        success = False
        
        # Send to each channel
        for channel in channels:
            try:
                if channel == 'slack' and self.settings.enable_slack_alerts:
                    success |= self._send_slack_alert(service, severity, message, details)
                elif channel == 'email' and self.settings.enable_email_alerts:
                    success |= self._send_email_alert(service, severity, message, details)
                else:
                    logger.debug(f"Channel {channel} not enabled or not implemented")
            except Exception as e:
                logger.error(f"Failed to send alert via {channel}: {e}")
        
        # Check for escalation
        self._check_escalation(service, severity)
        
        return success
    
    def _send_slack_alert(self, service: str, severity: str, 
                         message: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Send alert via Slack"""
        if not self._slack_connector:
            logger.error("Slack connector not initialized")
            return False
        
        try:
            # Format fields
            fields = {
                'Service': service,
                'Severity': severity.upper(),
                'Time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            }
            
            if details:
                fields.update(details)
            
            return self._slack_connector.send_alert(
                title=f"{service} Alert",
                message=message,
                severity=severity,
                fields=fields
            )
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    def _send_email_alert(self, service: str, severity: str, 
                         message: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Send alert via email (using Resend)"""
        try:
            import requests
            
            if not self.settings.resend_api_key:
                logger.error("Resend API key not configured")
                return False
            
            recipients = self.settings.email_alert_recipients
            if not recipients:
                logger.error("No email recipients configured")
                return False
            
            # Format email body
            body_lines = [
                f"Service: {service}",
                f"Severity: {severity.upper()}",
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                "",
                "Message:",
                message,
            ]
            
            if details:
                body_lines.extend(["", "Details:"])
                for key, value in details.items():
                    body_lines.append(f"  {key}: {value}")
            
            email_body = "\n".join(body_lines)
            
            # Send via Resend API
            response = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": self.settings.resend_from_address or "alerts@brainops.com",
                    "to": recipients,
                    "subject": f"[{severity.upper()}] {service} Alert - BrainOps",
                    "text": email_body
                },
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _is_in_cooldown(self, service: str, severity: str) -> bool:
        """Check if alert is in cooldown period"""
        with self._history_lock:
            history = self._alert_history.get(f"{service}:{severity}", [])
            
            if not history:
                return False
            
            # Get cooldown for this severity
            severity_config = self.alert_rules.get('severity_levels', {}).get(
                severity, {'cooldown_minutes': self._cooldown_minutes}
            )
            cooldown = severity_config.get('cooldown_minutes', self._cooldown_minutes)
            
            # Check last alert time
            last_alert_time = history[-1]
            cooldown_end = last_alert_time + timedelta(minutes=cooldown)
            
            return datetime.utcnow() < cooldown_end
    
    def _record_alert(self, service: str, severity: str):
        """Record alert in history"""
        with self._history_lock:
            key = f"{service}:{severity}"
            self._alert_history[key].append(datetime.utcnow())
            
            # Keep only last 100 alerts per key
            if len(self._alert_history[key]) > 100:
                self._alert_history[key] = self._alert_history[key][-100:]
    
    def _check_escalation(self, service: str, severity: str):
        """Check if alert should be escalated"""
        severity_config = self.alert_rules.get('severity_levels', {}).get(severity, {})
        escalate_after = severity_config.get('escalate_after')
        
        if not escalate_after:
            return
        
        with self._history_lock:
            key = f"{service}:{severity}"
            history = self._alert_history.get(key, [])
            
            # Count recent alerts (last hour)
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_alerts = [t for t in history if t > one_hour_ago]
            
            if len(recent_alerts) >= escalate_after:
                # Escalate to next severity level
                escalated_severity = self._get_next_severity(severity)
                if escalated_severity != severity:
                    logger.warning(
                        f"Escalating {service} alert from {severity} to {escalated_severity}"
                    )
                    # Send escalated alert
                    self.send_alert(
                        service=service,
                        severity=escalated_severity,
                        message=f"ESCALATED: Multiple {severity} alerts for {service}",
                        details={'original_severity': severity, 'alert_count': len(recent_alerts)}
                    )
    
    def _get_next_severity(self, current_severity: str) -> str:
        """Get next severity level for escalation"""
        severity_order = ['info', 'warning', 'error', 'critical']
        
        try:
            current_index = severity_order.index(current_severity)
            if current_index < len(severity_order) - 1:
                return severity_order[current_index + 1]
        except ValueError:
            pass
        
        return current_severity
    
    def test_slack_alert(self) -> bool:
        """Test Slack alert configuration"""
        return self._send_slack_alert(
            service="test",
            severity="info",
            message="This is a test alert from BrainOps AI Ops Bot",
            details={'test': True, 'timestamp': datetime.utcnow().isoformat()}
        )
    
    def test_email_alert(self) -> bool:
        """Test email alert configuration"""
        return self._send_email_alert(
            service="test",
            severity="info",
            message="This is a test alert from BrainOps AI Ops Bot",
            details={'test': True, 'timestamp': datetime.utcnow().isoformat()}
        )
    
    def get_alert_history(self, service: Optional[str] = None, 
                         hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history"""
        with self._history_lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            history = []
            
            for key, timestamps in self._alert_history.items():
                svc, severity = key.split(':', 1)
                
                if service and svc != service:
                    continue
                
                recent_timestamps = [t for t in timestamps if t > cutoff_time]
                
                if recent_timestamps:
                    history.append({
                        'service': svc,
                        'severity': severity,
                        'count': len(recent_timestamps),
                        'first_alert': min(recent_timestamps).isoformat(),
                        'last_alert': max(recent_timestamps).isoformat()
                    })
            
            return sorted(history, key=lambda x: x['last_alert'], reverse=True)
    
    def clear_history(self, service: Optional[str] = None):
        """Clear alert history"""
        with self._history_lock:
            if service:
                # Clear specific service
                keys_to_remove = [k for k in self._alert_history.keys() 
                                 if k.startswith(f"{service}:")]
                for key in keys_to_remove:
                    del self._alert_history[key]
            else:
                # Clear all
                self._alert_history.clear()