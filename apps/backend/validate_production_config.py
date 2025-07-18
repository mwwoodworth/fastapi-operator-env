#!/usr/bin/env python3
"""
Production Configuration Validator
Ensures all required environment variables and infrastructure are properly configured
"""

import os
import sys
import psycopg2
import redis
import requests
from typing import Dict, List, Tuple
from datetime import datetime
import json
from urllib.parse import urlparse
import boto3
from colorama import init, Fore, Style

init(autoreset=True)


class ConfigValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.successes = []
        
    def log_error(self, message: str):
        self.errors.append(message)
        print(f"{Fore.RED}❌ ERROR: {message}{Style.RESET_ALL}")
        
    def log_warning(self, message: str):
        self.warnings.append(message)
        print(f"{Fore.YELLOW}⚠️  WARNING: {message}{Style.RESET_ALL}")
        
    def log_success(self, message: str):
        self.successes.append(message)
        print(f"{Fore.GREEN}✅ SUCCESS: {message}{Style.RESET_ALL}")
        
    def check_env_file(self):
        """Check if .env file exists and is properly configured."""
        print(f"\n{Fore.BLUE}=== Checking Environment Configuration ==={Style.RESET_ALL}")
        
        if not os.path.exists('.env'):
            self.log_error(".env file not found. Copy .env.example and configure.")
            return False
            
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Required variables
        required_vars = {
            # Core
            'DATABASE_URL': 'PostgreSQL connection string',
            'REDIS_URL': 'Redis connection string',
            'SECRET_KEY': 'Application secret key',
            'JWT_SECRET_KEY': 'JWT signing key',
            
            # Supabase
            'SUPABASE_URL': 'Supabase project URL',
            'SUPABASE_ANON_KEY': 'Supabase anonymous key',
            
            # AI Services
            'OPENAI_API_KEY': 'OpenAI API key',
            'ANTHROPIC_API_KEY': 'Anthropic API key',
            
            # Integrations
            'STRIPE_API_KEY': 'Stripe API key',
            'STRIPE_WEBHOOK_SECRET': 'Stripe webhook secret',
        }
        
        # Optional but recommended
        optional_vars = {
            'SENTRY_DSN': 'Error tracking',
            'SLACK_BOT_TOKEN': 'Slack notifications',
            'SENDGRID_API_KEY': 'Email service',
            'WEATHER_API_KEY': 'Weather service',
        }
        
        missing_required = []
        missing_optional = []
        
        for var, description in required_vars.items():
            value = os.getenv(var)
            if not value or value.startswith('your-'):
                missing_required.append(f"{var} ({description})")
            else:
                self.log_success(f"{var} configured")
                
        for var, description in optional_vars.items():
            value = os.getenv(var)
            if not value or value.startswith('your-'):
                missing_optional.append(f"{var} ({description})")
            else:
                self.log_success(f"{var} configured")
                
        if missing_required:
            self.log_error(f"Missing required variables: {', '.join(missing_required)}")
            
        if missing_optional:
            self.log_warning(f"Missing optional variables: {', '.join(missing_optional)}")
            
        return len(missing_required) == 0
        
    def check_database(self):
        """Verify database connection and schema."""
        print(f"\n{Fore.BLUE}=== Checking Database Connection ==={Style.RESET_ALL}")
        
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            self.log_error("DATABASE_URL not set")
            return False
            
        try:
            # Parse connection string
            result = urlparse(db_url)
            
            # Connect to database
            conn = psycopg2.connect(
                database=result.path[1:],
                user=result.username,
                password=result.password,
                host=result.hostname,
                port=result.port
            )
            
            # Check connection
            cur = conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            self.log_success(f"PostgreSQL connected: {version.split(',')[0]}")
            
            # Check tables exist
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            
            tables = [row[0] for row in cur.fetchall()]
            
            expected_tables = [
                'users', 'projects', 'tasks', 'workflows', 
                'workflow_runs', 'integrations', 'customers',
                'invoices', 'estimates', 'jobs'
            ]
            
            missing_tables = set(expected_tables) - set(tables)
            
            if missing_tables:
                self.log_error(f"Missing tables: {', '.join(missing_tables)}")
                self.log_warning("Run database migrations: alembic upgrade head")
            else:
                self.log_success(f"All required tables present ({len(tables)} total)")
                
            conn.close()
            return len(missing_tables) == 0
            
        except Exception as e:
            self.log_error(f"Database connection failed: {str(e)}")
            return False
            
    def check_redis(self):
        """Verify Redis connection."""
        print(f"\n{Fore.BLUE}=== Checking Redis Connection ==={Style.RESET_ALL}")
        
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            self.log_error("REDIS_URL not set")
            return False
            
        try:
            r = redis.from_url(redis_url)
            r.ping()
            
            # Get Redis info
            info = r.info()
            version = info.get('redis_version', 'Unknown')
            memory_used = info.get('used_memory_human', 'Unknown')
            
            self.log_success(f"Redis connected: v{version}, Memory: {memory_used}")
            
            # Test set/get
            r.set('test_key', 'test_value', ex=10)
            value = r.get('test_key')
            
            if value == b'test_value':
                self.log_success("Redis read/write test passed")
                r.delete('test_key')
                return True
            else:
                self.log_error("Redis read/write test failed")
                return False
                
        except Exception as e:
            self.log_error(f"Redis connection failed: {str(e)}")
            return False
            
    def check_external_services(self):
        """Verify external service connections."""
        print(f"\n{Fore.BLUE}=== Checking External Services ==={Style.RESET_ALL}")
        
        services_ok = True
        
        # Check OpenAI
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key and not openai_key.startswith('sk-...'):
            try:
                headers = {'Authorization': f'Bearer {openai_key}'}
                response = requests.get(
                    'https://api.openai.com/v1/models',
                    headers=headers,
                    timeout=5
                )
                if response.status_code == 200:
                    self.log_success("OpenAI API key valid")
                else:
                    self.log_error(f"OpenAI API key invalid: {response.status_code}")
                    services_ok = False
            except Exception as e:
                self.log_warning(f"Could not verify OpenAI: {str(e)}")
                
        # Check Stripe
        stripe_key = os.getenv('STRIPE_API_KEY')
        if stripe_key and not stripe_key.startswith('sk_live_...'):
            self.log_warning("Stripe API key appears to be test mode")
            
        # Check Supabase
        supabase_url = os.getenv('SUPABASE_URL')
        if supabase_url:
            try:
                response = requests.get(f"{supabase_url}/rest/v1/", timeout=5)
                if response.status_code in [200, 401]:  # 401 expected without auth
                    self.log_success("Supabase URL reachable")
                else:
                    self.log_error(f"Supabase unreachable: {response.status_code}")
                    services_ok = False
            except Exception as e:
                self.log_error(f"Supabase connection failed: {str(e)}")
                services_ok = False
                
        return services_ok
        
    def check_security(self):
        """Verify security configurations."""
        print(f"\n{Fore.BLUE}=== Checking Security Configuration ==={Style.RESET_ALL}")
        
        # Check secret strength
        secret_key = os.getenv('SECRET_KEY', '')
        jwt_key = os.getenv('JWT_SECRET_KEY', '')
        
        if len(secret_key) < 32:
            self.log_error("SECRET_KEY too short (minimum 32 characters)")
        else:
            self.log_success("SECRET_KEY length adequate")
            
        if len(jwt_key) < 32:
            self.log_error("JWT_SECRET_KEY too short (minimum 32 characters)")
        else:
            self.log_success("JWT_SECRET_KEY length adequate")
            
        # Check for default values
        if secret_key == 'your-secret-key-here-change-in-production':
            self.log_error("SECRET_KEY is still default value!")
            
        # Check CORS settings
        cors_origins = os.getenv('CORS_ORIGINS', '[]')
        if 'localhost' in cors_origins and os.getenv('ENVIRONMENT') == 'production':
            self.log_warning("CORS allows localhost in production")
            
        return True
        
    def check_monitoring(self):
        """Verify monitoring setup."""
        print(f"\n{Fore.BLUE}=== Checking Monitoring Configuration ==={Style.RESET_ALL}")
        
        # Check Sentry
        sentry_dsn = os.getenv('SENTRY_DSN')
        if sentry_dsn and sentry_dsn.startswith('https://'):
            self.log_success("Sentry DSN configured")
        else:
            self.log_warning("Sentry error tracking not configured")
            
        # Check log level
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        if log_level == 'DEBUG' and os.getenv('ENVIRONMENT') == 'production':
            self.log_warning("DEBUG logging enabled in production")
        else:
            self.log_success(f"Log level set to {log_level}")
            
        return True
        
    def generate_report(self):
        """Generate final validation report."""
        print(f"\n{Fore.BLUE}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}=== PRODUCTION CONFIGURATION VALIDATION REPORT ==={Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*60}{Style.RESET_ALL}")
        
        total_checks = len(self.successes) + len(self.warnings) + len(self.errors)
        
        print(f"\nTotal Checks: {total_checks}")
        print(f"{Fore.GREEN}✅ Passed: {len(self.successes)}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}⚠️  Warnings: {len(self.warnings)}{Style.RESET_ALL}")
        print(f"{Fore.RED}❌ Errors: {len(self.errors)}{Style.RESET_ALL}")
        
        if self.errors:
            print(f"\n{Fore.RED}CRITICAL ISSUES TO FIX:{Style.RESET_ALL}")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
                
        if self.warnings:
            print(f"\n{Fore.YELLOW}WARNINGS TO REVIEW:{Style.RESET_ALL}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
                
        # Save report
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_checks": total_checks,
                "passed": len(self.successes),
                "warnings": len(self.warnings),
                "errors": len(self.errors)
            },
            "successes": self.successes,
            "warnings": self.warnings,
            "errors": self.errors,
            "ready_for_production": len(self.errors) == 0
        }
        
        with open("production_validation_report.json", "w") as f:
            json.dump(report, f, indent=2)
            
        print(f"\nDetailed report saved to: production_validation_report.json")
        
        if len(self.errors) == 0:
            print(f"\n{Fore.GREEN}✅ SYSTEM READY FOR PRODUCTION DEPLOYMENT{Style.RESET_ALL}")
            return True
        else:
            print(f"\n{Fore.RED}❌ SYSTEM NOT READY - FIX ERRORS FIRST{Style.RESET_ALL}")
            return False
            
    def run_all_checks(self):
        """Run all validation checks."""
        print(f"{Fore.BLUE}🔍 BrainOps Production Configuration Validator{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*60}{Style.RESET_ALL}")
        
        # Run checks
        self.check_env_file()
        self.check_database()
        self.check_redis()
        self.check_external_services()
        self.check_security()
        self.check_monitoring()
        
        # Generate report
        return self.generate_report()


def main():
    """Run production configuration validation."""
    validator = ConfigValidator()
    success = validator.run_all_checks()
    
    if not success:
        print(f"\n{Fore.RED}Please fix all errors before proceeding with deployment.{Style.RESET_ALL}")
        sys.exit(1)
    else:
        print(f"\n{Fore.GREEN}Configuration validated! Ready to deploy.{Style.RESET_ALL}")
        sys.exit(0)


if __name__ == "__main__":
    main()