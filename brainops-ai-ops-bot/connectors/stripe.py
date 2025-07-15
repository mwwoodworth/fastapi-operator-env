"""
Stripe connector for payment processing
"""

from typing import Dict, Any, List, Optional
import logging
import stripe
from .base import BaseConnector


logger = logging.getLogger(__name__)


class StripeConnector(BaseConnector):
    """Stripe API connector"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key_live = config.get('api_key_live')
        self.api_key_test = config.get('api_key_test')
        self.use_live = bool(self.api_key_live)
        
        # Use live key if available, otherwise test key
        stripe.api_key = self.api_key_live if self.use_live else self.api_key_test
    
    def authenticate(self) -> bool:
        """Test Stripe API key"""
        try:
            stripe.Account.retrieve()
            self._is_authenticated = True
            logger.info(f"Stripe authentication successful ({'live' if self.use_live else 'test'} mode)")
            return True
            
        except Exception as e:
            logger.error(f"Stripe authentication error: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Check Stripe API health"""
        try:
            account = stripe.Account.retrieve()
            
            return {
                'healthy': True,
                'message': f"Connected to Stripe account: {account.id}",
                'details': {
                    'account_id': account.id,
                    'mode': 'live' if self.use_live else 'test',
                    'country': account.country,
                    'currency': account.default_currency
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'message': f"Health check failed: {str(e)}"
            }
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List Stripe resources"""
        if resource_type == 'customers':
            return self.list_customers()
        elif resource_type == 'charges':
            return self.list_charges()
        elif resource_type == 'products':
            return self.list_products()
        
        raise ValueError(f"Unknown resource type: {resource_type}")
    
    def list_customers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List Stripe customers"""
        try:
            customers = stripe.Customer.list(limit=limit)
            
            return [
                {
                    'id': customer.id,
                    'email': customer.email,
                    'name': customer.name,
                    'created': customer.created
                }
                for customer in customers.data
            ]
            
        except Exception as e:
            logger.error(f"Error listing customers: {e}")
            return []
    
    def list_charges(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List Stripe charges"""
        try:
            charges = stripe.Charge.list(limit=limit)
            
            return [
                {
                    'id': charge.id,
                    'amount': charge.amount,
                    'currency': charge.currency,
                    'status': charge.status,
                    'created': charge.created
                }
                for charge in charges.data
            ]
            
        except Exception as e:
            logger.error(f"Error listing charges: {e}")
            return []
    
    def list_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List Stripe products"""
        try:
            products = stripe.Product.list(limit=limit)
            
            return [
                {
                    'id': product.id,
                    'name': product.name,
                    'active': product.active,
                    'created': product.created
                }
                for product in products.data
            ]
            
        except Exception as e:
            logger.error(f"Error listing products: {e}")
            return []