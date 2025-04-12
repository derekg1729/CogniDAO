#!/usr/bin/env python3
"""
Simple test runner for the Cogni Memory Architecture.

This script discovers and runs all tests in the tests/ directory.
"""

import os
import sys
import pytest


if __name__ == "__main__":
    # Find the directory where this script is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Set up the test directory
    test_dir = os.path.join(current_dir, "tests")
    
    print(f"Discovering tests in: {test_dir}")
    
    # Add parent directory to path to ensure imports work correctly
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    # Use pytest to run the tests
    args = [
        "-v",                # Verbose output
        test_dir,            # Test directory
        "--tb=native",       # Traceback style
    ]
    
    # If additional arguments were provided, add them
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
    
    # Run the tests and exit with the appropriate status code
    sys.exit(pytest.main(args)) 