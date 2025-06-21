"""
🌈 RAINBOW FLOWER
A Prefect flow that creates a wide, breadth-first graph with rainbow-colored nodes.
The visual graph itself is the art piece - runtime behavior is secondary.
"""

import asyncio
import time
import random
from typing import List, Dict, Any

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
def rainbow_source(index: int) -> Dict[str, Any]:
    """
    A source task that generates initial data for the web.
    Runs for 5-8 seconds to be visible in the graph.

    Args:
        index: Task index for color selection

    Returns:
        Dict with color data and processing info
    """
    # Pick color based on index, cycling through rainbow
    color_name, hex_code = RAINBOW[index % 7]

    # Simulate work for 5-8 seconds
    work_time = random.uniform(5, 8)
    print(f"🌱 {color_name.upper()} source starting {work_time:.1f}s of work...")
    time.sleep(work_time)

    result = {
        "color": color_name,
        "hex": hex_code,
        "source_index": index,
        "work_time": work_time,
        "data_size": random.randint(100, 1000),
    }

    print(f"✅ {color_name.upper()} source completed!")
    return result


@task
def rainbow_processor(upstream_data: Dict[str, Any], processor_id: str) -> Dict[str, Any]:
    """
    A processing task that takes data from source tasks and enriches it.
    Runs for 3-6 seconds.

    Args:
        upstream_data: Data from upstream source task
        processor_id: Unique identifier for this processor

    Returns:
        Enriched data dictionary
    """
    color = upstream_data["color"]

    # Simulate processing work for 3-6 seconds
    work_time = random.uniform(3, 6)
    print(f"⚙️  {color.upper()} processor {processor_id} starting {work_time:.1f}s of work...")
    time.sleep(work_time)

    result = {
        **upstream_data,  # Include all upstream data
        "processor_id": processor_id,
        "processed_at": time.time(),
        "processing_time": work_time,
        "enriched_data": f"processed_{color}_{processor_id}",
    }

    print(f"✅ {color.upper()} processor {processor_id} completed!")
    return result


@task
def rainbow_aggregator(processed_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    An aggregator task that combines data from multiple processors.
    Runs for 4-7 seconds.

    Args:
        processed_data_list: List of processed data from upstream processors

    Returns:
        Aggregated result dictionary
    """
    colors = [data["color"] for data in processed_data_list]
    color_combo = "+".join(colors)

    # Simulate aggregation work for 4-7 seconds
    work_time = random.uniform(4, 7)
    print(f"🔗 Aggregating {color_combo} for {work_time:.1f}s...")
    time.sleep(work_time)

    result = {
        "colors": colors,
        "total_items": len(processed_data_list),
        "total_data_size": sum(data["data_size"] for data in processed_data_list),
        "aggregation_time": work_time,
        "combined_result": f"aggregated_{color_combo}",
    }

    print(f"✅ Aggregation of {color_combo} completed!")
    return result


@flow
async def rainbow_flower(source_count: int = 4, processors_per_source: int = 2) -> None:
    """
    🌈 Rainbow Flower - A connected web of rainbow-colored data processing tasks

    Creates a complex task dependency web where:
    - Source tasks generate initial rainbow data (5-8s each)
    - Processor tasks enrich data from sources (3-6s each)
    - Aggregator tasks combine multiple processed streams (4-7s each)
    - Tasks pass real data between each other creating dependencies

    Args:
        source_count: Number of source tasks to create (4-7 recommended)
        processors_per_source: Number of processors per source (2-3 recommended)
    """
    print(
        f"🌈 Growing rainbow web: {source_count} sources × {processors_per_source} processors each"
    )
    print("🎨 Colors will cycle: " + " → ".join([name.title() for name, _ in RAINBOW]))

    # STAGE 1: Create source tasks - these run concurrently
    print("🌱 Stage 1: Creating source tasks...")
    source_futures = []
    for i in range(source_count):
        future = rainbow_source.submit(i)
        source_futures.append(future)

    # Wait for all sources to complete and get their data
    source_results = []
    for future in source_futures:
        result = future.result()  # Don't await - .result() is sync when called from async flow
        source_results.append(result)

    # STAGE 2: Create processor tasks - each source feeds multiple processors
    print("⚙️  Stage 2: Creating processor tasks...")
    processor_futures = []

    for source_idx, source_data in enumerate(source_results):
        for proc_idx in range(processors_per_source):
            processor_id = f"P{source_idx}-{proc_idx}"
            future = rainbow_processor.submit(source_data, processor_id)
            processor_futures.append(future)

    # Wait for all processors to complete
    processor_results = []
    for future in processor_futures:
        result = future.result()  # Don't await - .result() is sync when called from async flow
        processor_results.append(result)

    # STAGE 3: Create aggregator tasks - combine processors in different ways
    print("🔗 Stage 3: Creating aggregator tasks...")

    # Create 3 different aggregations to show the web structure:
    # Aggregator 1: First half of processors
    mid_point = len(processor_results) // 2
    agg1_data = processor_results[:mid_point]

    # Aggregator 2: Second half of processors
    agg2_data = processor_results[mid_point:]

    # Aggregator 3: Mix of processors from different sources
    agg3_data = [processor_results[i] for i in range(0, len(processor_results), 2)]

    # Run aggregators concurrently
    agg_futures = [
        rainbow_aggregator.submit(agg1_data),
        rainbow_aggregator.submit(agg2_data),
        rainbow_aggregator.submit(agg3_data),
    ]

    # Wait for aggregators to complete
    final_results = []
    for future in agg_futures:
        result = future.result()  # Don't await - .result() is sync when called from async flow
        final_results.append(result)

    print(f"🌈✨ Rainbow web complete! {len(final_results)} final aggregations completed.")
    print(
        f"📊 Total tasks executed: {source_count} sources + {len(processor_results)} processors + {len(final_results)} aggregators"
    )


# Main export for the deployment
__all__ = ["rainbow_flower"]


if __name__ == "__main__":
    # Quick test run - smaller scale for testing
    asyncio.run(rainbow_flower(source_count=3, processors_per_source=2))
