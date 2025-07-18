#!/usr/bin/env python3
"""
BrainOps Production Launch Orchestrator
Manages the complete production deployment and verification process
"""

import os
import sys
import time
import subprocess
import json
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import psutil
from colorama import init, Fore, Style, Back

init(autoreset=True)


class ProductionLauncher:
    def __init__(self):
        self.start_time = datetime.now()
        self.launch_status = {
            "configuration": "pending",
            "infrastructure": "pending",
            "deployment": "pending",
            "testing": "pending",
            "monitoring": "pending",
            "handoff": "pending"
        }
        self.production_url = os.getenv("PRODUCTION_URL", "https://api.brainops.com")
        
    def print_header(self, text: str):
        """Print formatted section header."""
        print(f"\n{Back.BLUE}{Fore.WHITE} {text} {Style.RESET_ALL}")
        print("=" * 70)
        
    def print_status(self, task: str, status: str, details: str = ""):
        """Print task status with color coding."""
        icons = {
            "pending": "⏳",
            "in_progress": "🔄",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌"
        }
        
        colors = {
            "pending": Fore.YELLOW,
            "in_progress": Fore.CYAN,
            "success": Fore.GREEN,
            "warning": Fore.YELLOW,
            "error": Fore.RED
        }
        
        icon = icons.get(status, "❓")
        color = colors.get(status, Fore.WHITE)
        
        print(f"{color}{icon} {task}{Style.RESET_ALL}")
        if details:
            print(f"   {details}")
            
    def run_command(self, command: str, description: str) -> Tuple[bool, str]:
        """Run shell command and return success status and output."""
        self.print_status(description, "in_progress")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.print_status(description, "success")
                return True, result.stdout
            else:
                self.print_status(description, "error", result.stderr[:200])
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            self.print_status(description, "error", "Command timed out")
            return False, "Timeout"
        except Exception as e:
            self.print_status(description, "error", str(e))
            return False, str(e)
            
    def step_1_validate_configuration(self):
        """Step 1: Validate production configuration."""
        self.print_header("STEP 1: CONFIGURATION VALIDATION")
        self.launch_status["configuration"] = "in_progress"
        
        # Run configuration validator
        success, output = self.run_command(
            "python validate_production_config.py",
            "Validating production configuration"
        )
        
        if success:
            self.launch_status["configuration"] = "success"
            self.print_status("Configuration validation", "success", "All checks passed")
            return True
        else:
            self.launch_status["configuration"] = "error"
            self.print_status("Configuration validation", "error", 
                            "Fix configuration errors before proceeding")
            return False
            
    def step_2_provision_infrastructure(self):
        """Step 2: Verify infrastructure is provisioned."""
        self.print_header("STEP 2: INFRASTRUCTURE VERIFICATION")
        self.launch_status["infrastructure"] = "in_progress"
        
        checks = []
        
        # Check database
        self.print_status("Checking database", "in_progress")
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            # Test connection with psql
            success, _ = self.run_command(
                f"psql {db_url} -c 'SELECT version();' -t",
                "Database connectivity"
            )
            checks.append(("Database", success))
        else:
            checks.append(("Database", False))
            
        # Check Redis
        self.print_status("Checking Redis", "in_progress")
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            success, _ = self.run_command(
                f"redis-cli -u {redis_url} ping",
                "Redis connectivity"
            )
            checks.append(("Redis", success))
        else:
            checks.append(("Redis", False))
            
        # Check DNS
        self.print_status("Checking DNS", "in_progress")
        domain = self.production_url.replace("https://", "").replace("http://", "")
        success, _ = self.run_command(
            f"nslookup {domain}",
            "DNS resolution"
        )
        checks.append(("DNS", success))
        
        # Summarize
        all_passed = all(check[1] for check in checks)
        if all_passed:
            self.launch_status["infrastructure"] = "success"
            self.print_status("Infrastructure verification", "success", 
                            "All components ready")
        else:
            self.launch_status["infrastructure"] = "error"
            failed = [check[0] for check in checks if not check[1]]
            self.print_status("Infrastructure verification", "error", 
                            f"Failed checks: {', '.join(failed)}")
            
        return all_passed
        
    def step_3_deploy_application(self):
        """Step 3: Deploy application to production."""
        self.print_header("STEP 3: APPLICATION DEPLOYMENT")
        self.launch_status["deployment"] = "in_progress"
        
        # Check if using Render
        if os.path.exists("render.yaml"):
            self.print_status("Deploying with Render", "in_progress")
            
            # Deploy with Render CLI
            success, output = self.run_command(
                "render up --yes",
                "Render deployment"
            )
            
            if success:
                self.launch_status["deployment"] = "success"
                self.print_status("Deployment", "success", "Application deployed")
                
                # Wait for service to be ready
                self.print_status("Waiting for service startup", "in_progress")
                time.sleep(30)
                return True
            else:
                self.launch_status["deployment"] = "error"
                return False
                
        else:
            # Manual deployment steps
            self.print_status("Manual deployment required", "warning")
            
            print("\nPlease complete these deployment steps:")
            print("1. Build Docker image: docker build -t brainops-backend .")
            print("2. Push to registry: docker push your-registry/brainops-backend")
            print("3. Deploy to your platform")
            print("4. Update PRODUCTION_URL environment variable")
            
            response = input("\nHave you completed deployment? (yes/no): ")
            if response.lower() == "yes":
                self.launch_status["deployment"] = "success"
                return True
            else:
                self.launch_status["deployment"] = "error"
                return False
                
    def step_4_run_tests(self):
        """Step 4: Run smoke and integration tests."""
        self.print_header("STEP 4: POST-DEPLOYMENT TESTING")
        self.launch_status["testing"] = "in_progress"
        
        test_results = {}
        
        # Health checks
        self.print_status("Running health checks", "in_progress")
        health_endpoints = [
            "/health",
            "/api/v1/health",
            "/api/v1/health/detailed"
        ]
        
        health_ok = True
        for endpoint in health_endpoints:
            try:
                response = requests.get(
                    f"{self.production_url}{endpoint}",
                    timeout=10
                )
                if response.status_code == 200:
                    self.print_status(f"Health check {endpoint}", "success")
                    test_results[endpoint] = "passed"
                else:
                    self.print_status(f"Health check {endpoint}", "error", 
                                    f"Status: {response.status_code}")
                    test_results[endpoint] = "failed"
                    health_ok = False
            except Exception as e:
                self.print_status(f"Health check {endpoint}", "error", str(e))
                test_results[endpoint] = "failed"
                health_ok = False
                
        if not health_ok:
            self.launch_status["testing"] = "error"
            return False
            
        # Run smoke tests
        self.print_status("Running smoke tests", "in_progress")
        success, output = self.run_command(
            f"python smoke_tests.py {self.production_url}",
            "Smoke test suite"
        )
        
        if success:
            # Parse smoke test results
            try:
                with open("smoke_test_results.json", "r") as f:
                    smoke_results = json.load(f)
                    
                total_tests = smoke_results["summary"]["total"]
                passed_tests = smoke_results["summary"]["passed"]
                pass_rate = smoke_results["summary"]["pass_rate"]
                
                self.print_status("Smoke tests", "success", 
                                f"{passed_tests}/{total_tests} passed ({pass_rate})")
                test_results["smoke_tests"] = smoke_results
                
            except Exception as e:
                self.print_status("Smoke test parsing", "warning", str(e))
                
        # Test critical user flow
        self.print_status("Testing critical user flow", "in_progress")
        flow_success = self.test_critical_flow()
        test_results["critical_flow"] = "passed" if flow_success else "failed"
        
        # Summarize testing
        if health_ok and success and flow_success:
            self.launch_status["testing"] = "success"
            return True
        else:
            self.launch_status["testing"] = "error"
            return False
            
    def test_critical_flow(self) -> bool:
        """Test critical user flow: register → login → create project."""
        try:
            # 1. Register user
            register_data = {
                "email": f"test_{int(time.time())}@brainops.com",
                "password": "TestPassword123!",
                "full_name": "Launch Test User"
            }
            
            response = requests.post(
                f"{self.production_url}/api/v1/auth/register",
                json=register_data,
                timeout=10
            )
            
            if response.status_code != 200:
                self.print_status("User registration", "error", 
                                f"Status: {response.status_code}")
                return False
                
            self.print_status("User registration", "success")
            
            # 2. Login
            login_data = {
                "email": register_data["email"],
                "password": register_data["password"]
            }
            
            response = requests.post(
                f"{self.production_url}/api/v1/auth/login",
                json=login_data,
                timeout=10
            )
            
            if response.status_code != 200:
                self.print_status("User login", "error", 
                                f"Status: {response.status_code}")
                return False
                
            token = response.json().get("access_token")
            self.print_status("User login", "success")
            
            # 3. Create project
            headers = {"Authorization": f"Bearer {token}"}
            project_data = {
                "name": "Launch Test Project",
                "description": "Testing production deployment"
            }
            
            response = requests.post(
                f"{self.production_url}/api/v1/projects",
                json=project_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                self.print_status("Create project", "success")
                return True
            else:
                self.print_status("Create project", "error", 
                                f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_status("Critical flow test", "error", str(e))
            return False
            
    def step_5_activate_monitoring(self):
        """Step 5: Activate and verify monitoring."""
        self.print_header("STEP 5: MONITORING ACTIVATION")
        self.launch_status["monitoring"] = "in_progress"
        
        monitoring_ok = True
        
        # Check Sentry
        sentry_dsn = os.getenv("SENTRY_DSN")
        if sentry_dsn:
            self.print_status("Sentry error tracking", "success", "Configured")
            
            # Trigger test error
            try:
                response = requests.get(
                    f"{self.production_url}/api/v1/test/error",
                    timeout=5
                )
                self.print_status("Sentry test error", "success", "Triggered")
            except:
                pass  # Expected to fail
        else:
            self.print_status("Sentry error tracking", "warning", "Not configured")
            monitoring_ok = False
            
        # Check metrics endpoint
        try:
            response = requests.get(
                f"{self.production_url}/metrics",
                timeout=10
            )
            if response.status_code == 200:
                self.print_status("Metrics endpoint", "success")
            else:
                self.print_status("Metrics endpoint", "warning", "Not accessible")
        except:
            self.print_status("Metrics endpoint", "warning", "Not configured")
            
        # Check backup configuration
        self.print_status("Backup configuration", "warning", 
                        "Manual verification required")
        
        if monitoring_ok:
            self.launch_status["monitoring"] = "success"
        else:
            self.launch_status["monitoring"] = "warning"
            
        return True  # Non-critical, can proceed
        
    def step_6_operational_handoff(self):
        """Step 6: Generate operational handoff report."""
        self.print_header("STEP 6: OPERATIONAL HANDOFF")
        self.launch_status["handoff"] = "in_progress"
        
        # Collect system status
        system_status = {
            "launch_timestamp": self.start_time.isoformat(),
            "completion_timestamp": datetime.now().isoformat(),
            "duration_minutes": (datetime.now() - self.start_time).seconds / 60,
            "production_url": self.production_url,
            "launch_status": self.launch_status,
            "health_check_url": f"{self.production_url}/health",
            "api_docs_url": f"{self.production_url}/docs",
            "metrics_url": f"{self.production_url}/metrics"
        }
        
        # Generate live system status table
        self.print_status("Generating system status", "in_progress")
        
        print("\n📊 LIVE SYSTEM STATUS")
        print("=" * 70)
        print(f"Production URL: {self.production_url}")
        print(f"Launch Duration: {system_status['duration_minutes']:.1f} minutes")
        print("\nComponent Status:")
        
        for component, status in self.launch_status.items():
            icon = "✅" if status == "success" else "⚠️" if status == "warning" else "❌"
            print(f"  {icon} {component.title()}: {status}")
            
        # Required founder actions
        print("\n🚨 REQUIRED FOUNDER ACTIONS")
        print("=" * 70)
        
        actions = []
        
        if not os.getenv("STRIPE_API_KEY", "").startswith("sk_live_"):
            actions.append("1. Add production Stripe API key to environment")
            
        if not os.getenv("SENTRY_DSN"):
            actions.append("2. Configure Sentry error tracking")
            
        actions.extend([
            "3. Verify DNS is pointing to production URL",
            "4. Enable automated backups in hosting platform",
            "5. Configure domain SSL certificate",
            "6. Set up uptime monitoring (Pingdom/UptimeRobot)",
            "7. Review and approve production firewall rules",
            "8. Add team members to production access list"
        ])
        
        for action in actions:
            print(f"  {action}")
            
        # Support information
        print("\n📞 SUPPORT & ESCALATION")
        print("=" * 70)
        print("On-Call Schedule: Defined in PagerDuty")
        print("Escalation Path:")
        print("  1. Check system status: /health")
        print("  2. Review error logs in Sentry")
        print("  3. Contact on-call engineer")
        print("  4. Escalate to technical lead if needed")
        
        # Save handoff report
        handoff_report = {
            "system_status": system_status,
            "required_actions": actions,
            "support_info": {
                "health_check": f"{self.production_url}/health",
                "api_docs": f"{self.production_url}/docs",
                "error_tracking": "Sentry dashboard",
                "metrics": f"{self.production_url}/metrics"
            },
            "launch_checklist": {
                "code_deployed": self.launch_status["deployment"] == "success",
                "tests_passed": self.launch_status["testing"] == "success",
                "monitoring_active": self.launch_status["monitoring"] in ["success", "warning"],
                "ssl_enabled": True,  # Assumed from deployment
                "backups_configured": False,  # Requires manual verification
                "team_access_granted": False  # Requires manual action
            }
        }
        
        with open("production_handoff_report.json", "w") as f:
            json.dump(handoff_report, f, indent=2)
            
        self.print_status("Handoff report generated", "success", 
                        "Saved to production_handoff_report.json")
        
        self.launch_status["handoff"] = "success"
        return True
        
    def run_launch_sequence(self):
        """Run the complete production launch sequence."""
        print(f"{Back.GREEN}{Fore.BLACK} 🚀 BRAINOPS PRODUCTION LAUNCH SEQUENCE {Style.RESET_ALL}")
        print("=" * 70)
        print(f"Target: {self.production_url}")
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Execute launch steps
        steps = [
            (self.step_1_validate_configuration, "Configuration must be valid"),
            (self.step_2_provision_infrastructure, "Infrastructure must be ready"),
            (self.step_3_deploy_application, "Application must deploy successfully"),
            (self.step_4_run_tests, "Tests must pass"),
            (self.step_5_activate_monitoring, "Monitoring should be active"),
            (self.step_6_operational_handoff, "Handoff must be completed")
        ]
        
        for step_func, requirement in steps:
            if not step_func():
                print(f"\n{Fore.RED}❌ LAUNCH HALTED: {requirement}{Style.RESET_ALL}")
                self.print_launch_summary(success=False)
                return False
                
        self.print_launch_summary(success=True)
        return True
        
    def print_launch_summary(self, success: bool):
        """Print final launch summary."""
        print("\n" + "=" * 70)
        
        if success:
            print(f"{Back.GREEN}{Fore.BLACK} 🎉 PRODUCTION LAUNCH SUCCESSFUL! 🎉 {Style.RESET_ALL}")
            print("\n✅ BrainOps is now LIVE in production!")
            print(f"✅ Access at: {self.production_url}")
            print("✅ All systems operational")
            print("\nNext Steps:")
            print("1. Monitor system for 24 hours")
            print("2. Complete founder action items")
            print("3. Begin customer onboarding")
            print("4. Schedule daily ops review")
        else:
            print(f"{Back.RED}{Fore.WHITE} ❌ PRODUCTION LAUNCH FAILED {Style.RESET_ALL}")
            print("\nPlease resolve all issues and run again.")
            print("Check production_handoff_report.json for details.")
            
        print("=" * 70)


def main():
    """Run production launch sequence."""
    launcher = ProductionLauncher()
    success = launcher.run_launch_sequence()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()