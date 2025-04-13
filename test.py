#!/usr/bin/env python
"""
Simple test runner script that executes pytest with appropriate options.
Run with: python test
"""
import sys
import subprocess
import importlib.util
import os

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

def find_test_directories():
    """Find all directories containing test files recursively."""
    test_dirs = set()
    exclude_dirs = {'.git', '.github', '.pytest_cache', '__pycache__', 'env', 'venv', 'build', 'dist'}
    
    for root, dirs, files in os.walk('.'):
        # Skip directories we want to exclude
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        
        # Check if directory contains test files
        if any(f.startswith('test_') and f.endswith('.py') for f in files):
            # Convert path to relative format
            rel_path = os.path.relpath(root, '.')
            if rel_path == '.':
                continue
            test_dirs.add(rel_path)
    
    return test_dirs

if __name__ == "__main__":
    # Ensure pytest is installed
    check_pytest()
    
    # Default arguments
    pytest_args = [
        "--color=yes",      # Colorized output
    ]
    
    # Check for summary mode
    if "-s" in sys.argv or "--summary" in sys.argv:
        # Remove the flags from sys.argv
        if "-s" in sys.argv:
            sys.argv.remove("-s")
        if "--summary" in sys.argv:
            sys.argv.remove("--summary")
        # In summary mode, don't use verbose output
    else:
        # Default to verbose output
        pytest_args.append("-v")
    
    # Process command line arguments
    if len(sys.argv) > 1:
        # User specified specific tests/directories to run
        pytest_args.extend(sys.argv[1:])
    else:
        # Run all tests in the project
        print("Running all tests in the project")
        pytest_args.extend(["."])
        
        # Auto-discover test directories (for information only)
        test_dirs = find_test_directories()
        if test_dirs:
            print("Found test directories:")
            for test_dir in sorted(test_dirs):
                print(f"  - {test_dir}")
    
    # Print the command being run
    print(f"Running: pytest {' '.join(pytest_args)}")
    
    # Run pytest with the given arguments
    result = subprocess.run([sys.executable, "-m", "pytest"] + pytest_args)
    
    # Exit with the same code as pytest
    sys.exit(result.returncode) 