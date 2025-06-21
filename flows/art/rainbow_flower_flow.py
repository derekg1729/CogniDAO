"""
🌈 RAINBOW FLOWER
A Prefect flow that creates a wide, breadth-first graph with rainbow-colored nodes.
The visual graph itself is the art piece - runtime behavior is secondary.
"""

import asyncio
from typing import List

from prefect import flow, task

# Rainbow color palette - 7 classic rainbow colors with vibrant hex codes
RAINBOW = [
    ("red", "#FF3B30"),
    ("orange", "#FF9500"),
    ("yellow", "#FFCC00"),
    ("green", "#34C759"),
    ("blue", "#0A84FF"),
    ("indigo", "#5856D6"),
    ("violet", "#AF52DE"),
]


@task
def rainbow_leaf(level: int, index: int) -> str:
    """
    A single colorful leaf task that returns a color name.

    Args:
        level: The depth level in the tree (0 = root level)
        index: Position index within the level (determines color)

    Returns:
        Color name string
    """
    # Pick color based on index, cycling through rainbow
    color_name, hex_code = RAINBOW[index % 7]

    # Return just the color name - simple and reliable
    return f"Level {level} - {color_name.upper()}"


def create_petal_level(level: int, width: int) -> List[str]:
    """
    Creates one level of rainbow tasks (a petal ring).

    Args:
        level: Current depth level (0-based)
        width: Number of tasks to spawn at this level

    Returns:
        List of task results from this level
    """
    # Call tasks directly (no concurrency for now, just get it working)
    results = []
    for i in range(width):
        result = rainbow_leaf(level, i)  # Direct call, not .submit()
        results.append(result)

    print(f"✅ Level {level} completed: {results}")
    return results


@flow
async def rainbow_flower(depth: int = 2, width: int = 5) -> None:
    """
    🌈 Rainbow Flower - A wide breadth-first rainbow visualization

    Creates a tiered rainbow pyramid where:
    - Each level spans horizontally with 'width' colorful nodes
    - Colors cycle through the 7-color rainbow spectrum
    - Breadth-first execution creates clear visual tiers

    Args:
        depth: Number of levels in the pyramid (2-6 recommended)
        width: Number of nodes per level (25+ for dramatic width)
    """
    print(f"🌈 Blooming rainbow flower: {depth} levels × {width} nodes each")
    print("🎨 Colors will cycle: " + " → ".join([name.title() for name, _ in RAINBOW]))

    # Create each level of the flower sequentially
    for level in range(depth):
        print(f"🌸 Creating petal level {level + 1}/{depth}")
        level_results = create_petal_level(level, width)
        print(f"🌈 Level {level} results: {len(level_results)} tasks completed")

    print("🌈✨ Rainbow flower bloomed! Check the Prefect UI for your colorful graph.")


# Main export for the deployment
__all__ = ["rainbow_flower"]


if __name__ == "__main__":
    # Quick test run
    asyncio.run(rainbow_flower(depth=3, width=15))
