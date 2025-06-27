"""
Test Script for Image Generation Control Flow

Tests the Cogni-Image-Generators Control Flow system with various creative briefs
and validates the two-agent collaboration workflow.

Usage:
    python flows/examples/test_image_generation_control_flow.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from flows.examples.image_generation_control_flow import image_generation_control_flow # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_basic_image_generation():
    """Test basic image generation with default creative brief"""
    logger.info("🧪 Testing basic image generation...")

    result = await image_generation_control_flow()

    print("\n📊 Basic Test Results:")
    print(f"Success: {result.get('success', False)}")
    print(f"Architecture: {result.get('architecture', 'Unknown')}")
    print(f"Luma Tools: {result.get('luma_tools_count', 0)}")

    return result.get("success", False)


async def test_custom_creative_brief():
    """Test with custom creative brief"""
    logger.info("🧪 Testing custom creative brief...")

    custom_brief = """A cyberpunk cityscape at night featuring:
- Neon-lit skyscrapers with holographic advertisements
- Flying cars with light trails
- Rain-soaked streets reflecting colorful lights
- Moody atmospheric lighting with purple and blue tones
- High detail, cinematic composition
- Blade Runner aesthetic"""

    result = await image_generation_control_flow(custom_brief)

    print("\n📊 Custom Brief Test Results:")
    print(f"Success: {result.get('success', False)}")
    print(f"Creative Brief: {custom_brief[:100]}...")
    print(f"Team Result Available: {'team_result' in result}")

    return result.get("success", False)


async def test_artistic_styles():
    """Test different artistic styles"""
    logger.info("🧪 Testing artistic style variations...")

    test_briefs = [
        "A minimalist geometric abstract composition with bold primary colors",
        "A photorealistic portrait of an elderly wise woman with intricate facial details",
        "An impressionist landscape painting of a field of sunflowers at golden hour",
        "A surreal dreamscape with floating islands and impossible architecture",
    ]

    results = []
    for i, brief in enumerate(test_briefs, 1):
        logger.info(f"🎨 Testing style {i}/4: {brief[:50]}...")

        try:
            result = await image_generation_control_flow(brief)
            results.append(result.get("success", False))
            print(f"   Style {i} Result: {'✅ Success' if result.get('success') else '❌ Failed'}")

        except Exception as e:
            logger.error(f"   Style {i} Error: {e}")
            results.append(False)

    success_rate = sum(results) / len(results) * 100
    print("\n📊 Artistic Styles Test Results:")
    print(f"Success Rate: {success_rate:.1f}% ({sum(results)}/{len(results)})")

    return success_rate > 50  # Consider successful if >50% pass


async def test_workflow_phases():
    """Test that workflow phases execute correctly"""
    logger.info("🧪 Testing workflow phases...")

    brief = "A peaceful mountain lake with morning reflections, realistic style"
    result = await image_generation_control_flow(brief)

    workflow_result = result.get("team_result", {}).get("workflow_result", {})

    phases_completed = [
        "phase_1_creation" in workflow_result,
        "phase_2_planning" in workflow_result,
        "phase_3_enhancement" in workflow_result,
    ]

    print("\n📊 Workflow Phases Test Results:")
    print(f"Phase 1 (Creation): {'✅' if phases_completed[0] else '❌'}")
    print(f"Phase 2 (Planning): {'✅' if phases_completed[1] else '❌'}")
    print(f"Phase 3 (Enhancement): {'✅' if phases_completed[2] else '❌'}")
    print(f"All Phases Completed: {'✅' if all(phases_completed) else '❌'}")

    return all(phases_completed)


async def run_comprehensive_tests():
    """Run all test scenarios"""
    logger.info("🚀 Starting comprehensive Image Generation Control Flow tests...")

    test_results = []
    test_names = []

    # Test 1: Basic functionality
    try:
        result1 = await test_basic_image_generation()
        test_results.append(result1)
        test_names.append("Basic Image Generation")
    except Exception as e:
        logger.error(f"Basic test failed: {e}")
        test_results.append(False)
        test_names.append("Basic Image Generation")

    # Test 2: Custom creative brief
    try:
        result2 = await test_custom_creative_brief()
        test_results.append(result2)
        test_names.append("Custom Creative Brief")
    except Exception as e:
        logger.error(f"Custom brief test failed: {e}")
        test_results.append(False)
        test_names.append("Custom Creative Brief")

    # Test 3: Artistic styles
    try:
        result3 = await test_artistic_styles()
        test_results.append(result3)
        test_names.append("Artistic Styles")
    except Exception as e:
        logger.error(f"Artistic styles test failed: {e}")
        test_results.append(False)
        test_names.append("Artistic Styles")

    # Test 4: Workflow phases
    try:
        result4 = await test_workflow_phases()
        test_results.append(result4)
        test_names.append("Workflow Phases")
    except Exception as e:
        logger.error(f"Workflow phases test failed: {e}")
        test_results.append(False)
        test_names.append("Workflow Phases")

    # Summary
    print("\n" + "=" * 60)
    print("🎉 COMPREHENSIVE TEST RESULTS SUMMARY")
    print("=" * 60)

    for i, (name, result) in enumerate(zip(test_names, test_results), 1):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i}. {name}: {status}")

    overall_success_rate = sum(test_results) / len(test_results) * 100
    print(
        f"\nOverall Success Rate: {overall_success_rate:.1f}% ({sum(test_results)}/{len(test_results)})"
    )

    if overall_success_rate >= 75:
        print("🎉 Image Generation Control Flow is performing well!")
    elif overall_success_rate >= 50:
        print("⚠️ Image Generation Control Flow has some issues but is functional")
    else:
        print("❌ Image Generation Control Flow needs attention")

    return overall_success_rate >= 50


if __name__ == "__main__":
    print("🎨 Image Generation Control Flow Test Suite")
    print("=" * 50)

    # Run tests
    success = asyncio.run(run_comprehensive_tests())

    # Exit with appropriate code
    sys.exit(0 if success else 1)
