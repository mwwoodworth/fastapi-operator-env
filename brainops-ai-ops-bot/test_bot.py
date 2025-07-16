#!/usr/bin/env python3
"""
Test script to verify bot functionality and catch errors
"""

import sys
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_imports():
    """Test all imports work correctly"""
    logger.info("Testing imports...")
    
    try:
        from config.settings import Settings
        logger.info("✓ Settings import successful")
        
        from core.monitor import HealthMonitor
        logger.info("✓ HealthMonitor import successful")
        
        from core.alerts import AlertManager
        logger.info("✓ AlertManager import successful")
        
        from core.scheduler import JobScheduler
        logger.info("✓ JobScheduler import successful")
        
        from api.app import create_app
        logger.info("✓ API app import successful")
        
        from connectors import get_connector
        logger.info("✓ Connectors import successful")
        
        return True
        
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return False

def test_scheduler():
    """Test scheduler initialization"""
    logger.info("\nTesting scheduler...")
    
    try:
        from config.settings import Settings
        from core.scheduler import JobScheduler
        
        settings = Settings()
        scheduler = JobScheduler(settings)
        logger.info("✓ Scheduler created successfully")
        
        # Test starting the scheduler
        scheduler.start()
        logger.info("✓ Scheduler started successfully")
        
        # Test stopping the scheduler
        scheduler.stop()
        logger.info("✓ Scheduler stopped successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Scheduler test failed: {e}", exc_info=True)
        return False

def test_api():
    """Test API app creation"""
    logger.info("\nTesting API app...")
    
    try:
        from config.settings import Settings
        from api.app import create_app
        
        settings = Settings()
        app = create_app(settings)
        logger.info("✓ API app created successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"API test failed: {e}", exc_info=True)
        return False

def main():
    """Run all tests"""
    logger.info("Starting BrainOps AI Ops Bot tests...\n")
    
    tests = [
        ("Imports", test_imports),
        ("Scheduler", test_scheduler),
        ("API", test_api),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {test_name} test...")
        logger.info(f"{'='*50}")
        
        success = test_func()
        results.append((test_name, success))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("Test Summary:")
    logger.info(f"{'='*50}")
    
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        logger.info("\n✓ All tests passed!")
        return 0
    else:
        logger.error("\n✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())