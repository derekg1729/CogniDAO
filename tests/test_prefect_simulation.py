"""
Test that simulates Prefect's execution environment to demonstrate the import issue
"""

import unittest
import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path


class TestPrefectSimulation(unittest.TestCase):
    """Test that simulates how Prefect loads and executes flows"""

    def setUp(self):
        # Get the project root directory
        self.project_root = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    def test_prefect_simulation(self):
        """Simulate exactly how Prefect loads and executes the gitcogni flow"""

        # Path to the flow file
        gitcogni_flow_path = (
            self.project_root / "legacy_logseq" / "flows" / "gitcogni" / "gitcogni_flow.py"
        )

        # Create a temp script that simulates Prefect loading
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False) as script_file:
            script_path = script_file.name
            # Write a script that simulates Prefect loading behavior
            script_file.write(f"""
import sys
import os
import json
import subprocess
from pathlib import Path

# This simulates what Prefect does when running a flow

results = {{}}

try:
    # Step 1: Prefect sets the working directory to the flow script's directory 
    # (this matches what the Prefect worker log shows)
    os.chdir('{gitcogni_flow_path.parent}')
    results["working_dir"] = os.getcwd()
    
    # Step 2: Prefect executes the flow file as a module/script
    try:
        # We'll attempt to import it instead of executing it directly
        # This should reveal the same error as in the Prefect logs
        script_path = '{gitcogni_flow_path}'
        
        # Use importlib to simulate how Prefect loads the module
        import importlib.util
        spec = importlib.util.spec_from_file_location("gitcogni_flow", script_path)
        module = importlib.util.module_from_spec(spec)
        
        # Before loading, check the Python path
        results["python_path_before"] = sys.path
        
        # Emulate Prefect loading the module
        try:
            spec.loader.exec_module(module)
            results["import_result"] = "success"
        except Exception as e:
            results["import_result"] = f"failed: {{type(e).__name__}}: {{str(e)}}"
            
            # Now let's try with the project root added to path
            try:
                sys.path.insert(0, str(Path('{self.project_root}')))
                results["added_project_root"] = True
                
                # Reset modules to avoid caching issues
                import importlib
                importlib.invalidate_caches()
                
                for k in list(sys.modules.keys()):
                    if 'gitcogni_flow' in k or 'cogni_agents' in k or 'legacy_logseq' in k:
                        del sys.modules[k]
                
                # Try again with project root in path
                spec = importlib.util.spec_from_file_location("gitcogni_flow", script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                results["import_with_root_added"] = "success"
            except Exception as e:
                results["import_with_root_added"] = f"failed: {{type(e).__name__}}: {{str(e)}}"
    
    except Exception as e:
        results["execution_error"] = f"{{type(e).__name__}}: {{str(e)}}"
        
except Exception as e:
    results["overall_error"] = f"{{type(e).__name__}}: {{str(e)}}"

# Print results as JSON for parsing
print(json.dumps(results, default=str))
""")

        try:
            # Run the script to simulate Prefect execution
            result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)

            # Print raw output for debugging
            print(f"Raw stdout: {result.stdout}")
            if result.stderr:
                print(f"Raw stderr: {result.stderr}")

            # Parse the JSON output
            output = json.loads(result.stdout.strip())

            # Display detailed results
            print(f"Prefect simulation results: {json.dumps(output, indent=2)}")

            # Verify that the simulation accurately represents the import error seen in Prefect logs
            self.assertIn(
                "import_result", output, "Test didn't properly run the module import simulation"
            )

            # Verify that the import now succeeds (since we fixed the issue)
            self.assertEqual(
                output.get("import_result"),
                "success",
                "Import should now succeed with the fixed git_cogni.py",
            )

        finally:
            # Clean up the temp file
            if os.path.exists(script_path):
                os.unlink(script_path)


if __name__ == "__main__":
    unittest.main()
