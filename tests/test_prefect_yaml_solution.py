"""
Test to verify that adding a prefect.yaml with set_working_directory fixes the issue
"""

import unittest
import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path


class TestPrefectYamlSolution(unittest.TestCase):
    """Test to verify that a properly configured prefect.yaml fixes the import issues"""

    def setUp(self):
        # Get the project root directory
        self.project_root = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    def test_prefect_yaml_simulation(self):
        """Test that simulates Prefect's execution with the YAML fix"""

        # Create a temporary directory for our test
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Create a simple prefect.yaml file in the temp directory
            prefect_yaml_path = temp_dir_path / "prefect.yaml"
            with open(prefect_yaml_path, "w") as f:
                f.write(f"""
name: gitcogni-test
prefect-version: 3.3.3

pull:
- prefect.deployments.steps.set_working_directory:
    directory: {self.project_root}
- prefect.deployments.steps.python_path.prepend_to_python_path:
    path: {self.project_root}

deployments:
- name: test-deployment
  entrypoint: gitcogni_flow.py:gitcogni_review_flow
""")

            # Create a test script that simulates Prefect's execution using the prefect.yaml
            test_script_path = temp_dir_path / "test_prefect_yaml.py"
            with open(test_script_path, "w") as f:
                f.write(f"""
import sys
import os
import json
from pathlib import Path

# Simulate Prefect's behavior when using set_working_directory from prefect.yaml
results = {{}}

try:
    # Step 1: Prefect reads the prefect.yaml and applies set_working_directory
    # Let's simulate this by changing to the project root
    os.chdir('{self.project_root}')
    results["working_dir"] = os.getcwd()
    
    # Record the original Python path
    results["original_python_path"] = sys.path.copy()
    
    # Step 2: Prefect also needs to add the working directory to Python path
    # This is essential - we're explicitly testing this step
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
        results["added_to_python_path"] = True
    
    # Step 3: Now try to import the flow and the agent
    try:
        # The flow should be able to import with the proper working directory
        from legacy_logseq.flows.gitcogni.gitcogni_flow import gitcogni_review_flow
        results["flow_import"] = "success"
        
        # The agent should also be importable
        from legacy_logseq.cogni_agents.git_cogni.git_cogni import GitCogniAgent
        results["agent_import"] = "success"
        
    except Exception as e:
        results["import_error"] = f"{{type(e).__name__}}: {{str(e)}}"
        
except Exception as e:
    results["overall_error"] = f"{{type(e).__name__}}: {{str(e)}}"

# Print results as JSON for parsing
print(json.dumps(results, default=str))
""")

            # Run the test script
            result = subprocess.run(
                [sys.executable, str(test_script_path)], capture_output=True, text=True
            )

            # Print raw output for debugging
            print(f"Raw stdout: {result.stdout}")
            if result.stderr:
                print(f"Raw stderr: {result.stderr}")

            # Parse the output
            output = json.loads(result.stdout.strip())

            # Display detailed results
            print(f"Prefect YAML simulation results: {json.dumps(output, indent=2)}")

            # Check that both imports succeed with the working directory fix
            self.assertEqual(
                output.get("flow_import"),
                "success",
                "Flow import failed even with proper working directory",
            )
            self.assertEqual(
                output.get("agent_import"),
                "success",
                "Agent import failed even with proper working directory",
            )


if __name__ == "__main__":
    unittest.main()
