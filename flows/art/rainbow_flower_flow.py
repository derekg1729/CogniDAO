"""
🌈 RAINBOW FLOWER
A Prefect flow that creates a wide, breadth-first graph with rainbow-colored nodes.
The visual graph itself is the art piece - runtime behavior is secondary.
"""

import asyncio
import random
from typing import List

import anyio
from prefect import flow, task
from prefect.states import State, StateType

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
async def rainbow_leaf(level: int, index: int) -> State:
    """
    A single colorful leaf task that returns a custom colored state.

    Args:
        level: The depth level in the tree (0 = root level)
        index: Position index within the level (determines color)

    Returns:
        Custom State with rainbow color
    """
    # Pick color based on index, cycling through rainbow
    color_name, hex_code = RAINBOW[index % 7]

    # Add subtle timing jitter for organic "brush stroke" feel
    await anyio.sleep(random.random() * 0.3)

    # Return custom colored completed state
    return State(type=StateType.COMPLETED, name=color_name.upper(), color=hex_code)


async def create_petal_level(level: int, width: int, wait=None) -> List:
    """
    Creates one level of rainbow tasks (a petal ring).

    Args:
        level: Current depth level (0-based)
        width: Number of tasks to spawn at this level
        wait: Parent tasks to wait for (enables breadth-first ordering)

    Returns:
        List of completed task futures from this level
    """
    # Generate all leaf tasks for this level simultaneously
    # Using .submit() ensures they all spawn as siblings at the same depth
    leaves = []
    for i in range(width):
        leaf_future = rainbow_leaf.submit(level, i, wait_for=wait)
        leaves.append(leaf_future)

    # In Prefect, just return the futures - the framework handles the execution
    # The wait_for parameter in the next level will handle sequencing
    return leaves


@flow
async def rainbow_flower(depth: int = 4, width: int = 25) -> None:
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

    # Create each level of the flower, waiting for the previous level to complete
    previous_level_tasks = None

    for level in range(depth):
        print(f"🌸 Creating petal level {level + 1}/{depth}")
        level_tasks = await create_petal_level(level, width, wait=previous_level_tasks)
        previous_level_tasks = level_tasks

    print("🌈✨ Rainbow flower bloomed! Check the Prefect UI for your colorful graph.")


# Main export for the deployment
__all__ = ["rainbow_flower"]


if __name__ == "__main__":
    # Quick test run
    asyncio.run(rainbow_flower(depth=3, width=15))
