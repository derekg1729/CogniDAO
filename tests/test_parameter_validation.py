import inspect
import json

# Import the flow to test
from legacy_logseq.flows.rituals.ritual_of_presence import ritual_of_presence_flow


def test_ritual_of_presence_parameter_validation():
    """
    Test that validates that None is now accepted for custom_prompt.

    This test verifies that with the proper Optional[str] type annotation:
    - custom_prompt can be None
    - Prefect's validation accepts None as a valid value
    """
    # Now that we've fixed the type annotation, None should be accepted
    # This should no longer raise an exception
    result = ritual_of_presence_flow.validate_parameters({"custom_prompt": None})
    assert result == {"custom_prompt": None}

    # Empty string should also be accepted
    result = ritual_of_presence_flow.validate_parameters({"custom_prompt": ""})
    assert result == {"custom_prompt": ""}

    # Regular string should be accepted too
    result = ritual_of_presence_flow.validate_parameters({"custom_prompt": "Test prompt"})
    assert result == {"custom_prompt": "Test prompt"}

    # No parameters should default to None
    result = ritual_of_presence_flow.validate_parameters({})
    assert result == {}


def test_prefect_parameter_handling_behavior():
    """
    Test to understand how Prefect handles parameter defaults and validation.

    This explores what happens during parameter validation with various scenarios:
    1. What happens when we provide no parameters?
    2. What values are being actually validated?
    3. How are defaults applied?
    """
    print("\n\n==== PREFECT PARAMETER BEHAVIOR INVESTIGATION ====")

    # Print the flow's parameter signature to understand what Prefect sees
    sig = inspect.signature(ritual_of_presence_flow.fn)
    print(f"\nFlow parameter signature: {sig}")
    print(
        f"Function parameter annotations: {getattr(ritual_of_presence_flow.fn, '__annotations__', {})}"
    )

    # Try validating with empty parameters
    print("\n--- Testing Empty Parameters ---")
    try:
        result = ritual_of_presence_flow.validate_parameters({})
        print(f"PASSED: Validated empty params result: {result}")
    except Exception as e:
        print(f"FAILED: Validation error with empty params: {repr(e)}")

    # Examine the flow parameter schema
    print("\n--- Flow Parameter Definitions ---")
    flow_params = ritual_of_presence_flow.parameters
    print(f"Parameter schema type: {type(flow_params)}")

    # Access properties attribute for Pydantic schema
    if hasattr(flow_params, "properties"):
        print("\nParameter properties:")
        for name, details in flow_params.properties.items():
            print(f"Parameter '{name}':")
            for k, v in details.items():
                print(f"  {k}: {v}")
    else:
        print("No 'properties' attribute found in parameter schema")

    # Try to access the schema dict
    print("\nParameter schema model dump:")
    try:
        # Try various ways to get the schema data
        if hasattr(flow_params, "model_dump"):
            schema_dict = flow_params.model_dump()
            print(json.dumps(schema_dict, indent=2))
        elif hasattr(flow_params, "dict"):
            schema_dict = flow_params.dict()
            print(json.dumps(schema_dict, indent=2))
        else:
            print("Could not find a method to dump the schema to dict")
    except Exception as e:
        print(f"Error dumping schema: {e}")

    # Check what happens when we provide an empty string instead of None
    print("\n--- Testing Empty String ---")
    try:
        result = ritual_of_presence_flow.validate_parameters({"custom_prompt": ""})
        print(f"PASSED: Empty string validation result: {result}")
    except Exception as e:
        print(f"FAILED: Validation error with empty string: {repr(e)}")

    # Look at how the flow is initialized and how it sets up parameter validation
    print("\n--- Prefect Flow Initialization ---")
    print(f"Flow object: {ritual_of_presence_flow}")
    print(f"Flow name: {ritual_of_presence_flow.name}")
    # Check actual validation implementation
    try:
        # Get the actual internal method Prefect uses
        print("\n--- Testing Parameter Validation Internals ---")
        # Run with None explicitly
        try:
            result = ritual_of_presence_flow._validate_parameters_and_update_defaults(
                {"custom_prompt": None}
            )
            print(f"PASSED: Internal validation with None: {result}")
        except Exception as e:
            print(f"FAILED: Internal validation with None: {repr(e)}")

        # Run with missing parameter (relying on default)
        try:
            result = ritual_of_presence_flow._validate_parameters_and_update_defaults({})
            print(f"PASSED: Internal validation with missing param: {result}")
        except Exception as e:
            print(f"FAILED: Internal validation with missing param: {repr(e)}")

    except Exception as e:
        print(f"Error testing internal validation: {e}")

    print("\n==== END OF INVESTIGATION ====\n")

    # This is an exploratory test, not assertion-based


def test_production_scenario_parameter_validation():
    """
    Test that simulates the production scenario after fixing the type annotation.

    This test verifies that with the proper Optional[str] type annotation:
    - The production scenario no longer fails
    - Parameters are validated correctly
    - Default values work as expected
    """

    # This is a simplified simulation of what happens in Prefect's FlowEngine.run_flow
    def simulate_flow_engine_run(flow, params=None):
        """Simulate what Prefect does internally when running a flow."""
        # In production, if no params are passed to a deployment run,
        # Prefect will pass an empty dict to validate_parameters
        validated_params = flow.validate_parameters(params or {})
        return validated_params

    # 1. Test with explicit None - should now pass
    result = simulate_flow_engine_run(ritual_of_presence_flow, {"custom_prompt": None})
    assert result == {"custom_prompt": None}

    # 2. Test with empty string - should pass
    result = simulate_flow_engine_run(ritual_of_presence_flow, {"custom_prompt": ""})
    assert result == {"custom_prompt": ""}

    # 3. Test with a valid string - should pass
    result = simulate_flow_engine_run(ritual_of_presence_flow, {"custom_prompt": "Some prompt"})
    assert result == {"custom_prompt": "Some prompt"}

    # 4. Production scenario - no parameters provided
    # This is the case that previously failed in production
    # With the fixed type annotation, this should now succeed
    result = simulate_flow_engine_run(ritual_of_presence_flow)
    assert result == {}
