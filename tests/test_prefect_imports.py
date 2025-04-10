"""
Test to verify that import paths work consistently across different contexts
"""
import unittest
import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path


class TestPrefectImportPaths(unittest.TestCase):
    """Test to verify that import paths work consistently in Prefect execution context"""
    
    def setUp(self):
        # Get the project root directory
        self.project_root = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
    def test_import_consistency(self):
        """Test that imports are consistent between agent files and flow files"""
        # Create a temp script to test imports
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w+', delete=False) as script_file:
            script_path = script_file.name
            # Write a script that examines the import paths
            script_file.write(f"""
import sys
import os
import json
from pathlib import Path

# Get the project root
project_root = Path('{self.project_root}')

# Dictionary to store test results
results = {{}}

# Test 1: Try importing the GitCogniAgent from gitcogni_flow.py's perspective
try:
    # Set up the path similar to how gitcogni_flow.py does it now
    sys.path.insert(0, os.path.abspath(os.path.join('{self.project_root}', 'infra_core/flows/gitcogni/../..')))
    sys.path.insert(0, '{self.project_root}')  # Add project root (new approach)
    from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent
    results["flow_import_test"] = "success"
except Exception as e:
    results["flow_import_test"] = f"failed: {{type(e).__name__}}: {{str(e)}}"

# Reset the path and sys.modules to avoid cached imports
sys.path = [p for p in sys.path if str(project_root) not in p]
for k in list(sys.modules.keys()):
    if 'cogni_agents' in k or 'infra_core' in k:
        del sys.modules[k]

# Test 2: Try importing the base CogniAgent from git_cogni.py's perspective
try:
    # Set up the path similar to how git_cogni.py would see it
    sys.path.insert(0, str(project_root))
    from infra_core.cogni_agents.base import CogniAgent
    results["agent_import_test"] = "success"
except Exception as e:
    results["agent_import_test"] = f"failed: {{type(e).__name__}}: {{str(e)}}"

# Reset the path and modules again
sys.path = [p for p in sys.path if str(project_root) not in p]
for k in list(sys.modules.keys()):
    if 'cogni_agents' in k or 'infra_core' in k:
        del sys.modules[k]

# Test 3: Try importing both ways from root with infra_core/flows/gitcogni as working directory
os.chdir(os.path.join('{self.project_root}', 'infra_core/flows/gitcogni'))
sys.path.insert(0, os.path.abspath(os.path.join('.')))

# Try the flow import first
try:
    # With gitcogni_flow.py's working directory (using absolute imports now)
    sys.path.insert(0, os.path.abspath(os.path.join('.', '../..')))
    sys.path.insert(0, '{self.project_root}')  # Add project root (new approach)
    from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent
    results["flow_import_in_prefect"] = "success"
except Exception as e:
    results["flow_import_in_prefect"] = f"failed: {{type(e).__name__}}: {{str(e)}}"

# Reset modules again
for k in list(sys.modules.keys()):
    if 'cogni_agents' in k or 'infra_core' in k:
        del sys.modules[k]

# Now try the agent import with the same path setup
try:
    from infra_core.cogni_agents.base import CogniAgent
    results["agent_import_in_prefect"] = "success"
except Exception as e:
    results["agent_import_in_prefect"] = f"failed: {{type(e).__name__}}: {{str(e)}}"

# Print results as JSON for parsing
print(json.dumps(results))
""")
        
        try:
            # Run the script to test imports in isolation
            result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
            
            # Parse the JSON output
            output = json.loads(result.stdout.strip())
            
            # Display detailed results
            print(f"Import test results: {output}")
            
            # Check if flow import works
            self.assertEqual(output.get("flow_import_test"), "success", 
                            f"Flow import test failed: {output.get('flow_import_test')}")
            
            # Check if agent import works
            self.assertEqual(output.get("agent_import_test"), "success", 
                            f"Agent import test failed: {output.get('agent_import_test')}")
            
            # This should fail with the current setup - the test that shows the incompatibility
            self.assertEqual(output.get("flow_import_in_prefect"), "success",
                            f"Flow import in Prefect context failed: {output.get('flow_import_in_prefect')}")
            
            # This will also fail with the current setup
            self.assertEqual(output.get("agent_import_in_prefect"), "success",
                            f"Agent import in Prefect context failed: {output.get('agent_import_in_prefect')}")
                            
        finally:
            # Clean up the temp file
            if os.path.exists(script_path):
                os.unlink(script_path)


if __name__ == '__main__':
    unittest.main() 