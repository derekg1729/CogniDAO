#!/usr/bin/env python
"""
Simple test runner script that executes pytest with appropriate options.
Run with: python test
"""
import sys
import subprocess
import importlib.util

def check_pytest():
    """Check if pytest is installed and install it if not."""
    if importlib.util.find_spec("pytest") is None:
        print("pytest not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest>=7.0.0", "pytest-mock>=3.10.0"])
        print("pytest installed successfully.")
        
    # Verify installation
    try:
        import pytest
        print(f"Using pytest version {pytest.__version__}")
    except ImportError:
        print("Failed to import pytest after installation. Please install manually with:")
        print("pip install pytest>=7.0.0 pytest-mock>=3.10.0")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure pytest is installed
    check_pytest()
    
    # Default arguments
    pytest_args = [
        "-v",               # Verbose output
        "--color=yes",      # Colorized output
        "tests",            # Test directory
    ]
    
    # Add any additional arguments passed to this script
    if len(sys.argv) > 1:
        pytest_args.extend(sys.argv[1:])
    
    # Print the command being run
    print(f"Running: pytest {' '.join(pytest_args)}")
    
    # Run pytest with the given arguments
    result = subprocess.run([sys.executable, "-m", "pytest"] + pytest_args)
    
    # Exit with the same code as pytest
    sys.exit(result.returncode) 