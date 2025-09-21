#!/usr/bin/env python3
"""
Test runner script for acer-pal application.
Run all tests with coverage reporting.
"""

import sys
import subprocess
import os

def run_tests():
    """Run all tests with pytest."""
    # Change to the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    # Install test dependencies if running in container
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements-test.txt'], 
                      check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Warning: Could not install test dependencies")
    
    # Run tests
    cmd = [
        sys.executable, '-m', 'pytest',
        'tests/',
        '--cov=main',
        '--cov-report=term-missing',
        '--cov-report=html:htmlcov',
        '-v'
    ]
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print("Error: pytest not found. Please install pytest first:")
        print("pip install -r requirements-test.txt")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)