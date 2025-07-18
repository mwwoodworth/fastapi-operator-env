#!/usr/bin/env python3
"""
Script to systematically fix all failing tests.
"""

import subprocess
import re
import os
import sys

def run_pytest(test_path=None):
    """Run pytest and return results."""
    cmd = ["python", "-m", "pytest", "-v", "--tb=short", "--no-header"]
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append("apps/backend/tests/")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr

def extract_test_summary(output):
    """Extract test summary from pytest output."""
    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    
    # Look for the summary line
    match = re.search(r'(\d+) failed.*?(\d+) passed.*?(\d+) error', output)
    if match:
        failed = int(match.group(1))
        passed = int(match.group(2))
        errors = int(match.group(3))
    else:
        # Try alternative patterns
        if 'passed' in output:
            match = re.search(r'(\d+) passed', output)
            if match:
                passed = int(match.group(1))
        if 'failed' in output:
            match = re.search(r'(\d+) failed', output)
            if match:
                failed = int(match.group(1))
        if 'error' in output:
            match = re.search(r'(\d+) error', output)
            if match:
                errors = int(match.group(1))
    
    return {
        'passed': passed,
        'failed': failed,
        'errors': errors,
        'skipped': skipped,
        'total': passed + failed + errors + skipped
    }

def main():
    """Main test fixing loop."""
    print("Starting comprehensive test fixing process...")
    print("=" * 80)
    
    # Activate virtual environment
    venv_activate = "source venv/bin/activate && "
    
    iteration = 0
    while True:
        iteration += 1
        print(f"\nIteration {iteration}")
        print("-" * 40)
        
        # Run all tests
        output = run_pytest()
        summary = extract_test_summary(output)
        
        print(f"Test Results:")
        print(f"  Passed:  {summary['passed']:3d}")
        print(f"  Failed:  {summary['failed']:3d}")
        print(f"  Errors:  {summary['errors']:3d}")
        print(f"  Skipped: {summary['skipped']:3d}")
        print(f"  Total:   {summary['total']:3d}")
        
        # Check if all tests pass
        if summary['failed'] == 0 and summary['errors'] == 0:
            print("\n✅ All tests passing! 🎉")
            break
        
        # Find first failing test
        failing_tests = re.findall(r'(apps/backend/tests/.*?::.*?)\s+(?:FAILED|ERROR)', output)
        if failing_tests:
            print(f"\nFirst failing test: {failing_tests[0]}")
            # TODO: Implement automatic fix logic here
            # For now, just report
        
        if iteration > 5:
            print("\n⚠️  Reached maximum iterations. Manual intervention needed.")
            break
    
    print("\n" + "=" * 80)
    print("Test fixing process complete!")
    
    # Generate final report
    with open("TEST_REPORT.md", "w") as f:
        f.write("# Test Report\n\n")
        f.write(f"## Final Results\n\n")
        f.write(f"- **Passed**: {summary['passed']}\n")
        f.write(f"- **Failed**: {summary['failed']}\n")
        f.write(f"- **Errors**: {summary['errors']}\n")
        f.write(f"- **Skipped**: {summary['skipped']}\n")
        f.write(f"- **Total**: {summary['total']}\n")

if __name__ == "__main__":
    main()