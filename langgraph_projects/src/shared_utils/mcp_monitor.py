"""
MCP Connection Monitoring Utilities.

Provides utilities for monitoring and debugging MCP client connections,
particularly useful for deployment health checks and troubleshooting.
"""

import asyncio
import json
from typing import Any, Dict

from .mcp_client import get_mcp_connection_info, get_cogni_mcp_manager, get_playwright_mcp_manager
from .logging_utils import get_logger, log_mcp_health_check

logger = get_logger(__name__)


async def check_mcp_health(server_type: str = "cogni") -> Dict[str, Any]:
    """
    Check the health of an MCP server connection.

    Args:
        server_type: Either "cogni" or "playwright"

    Returns:
        Dictionary with health check results
    """
    try:
        connection_info = get_mcp_connection_info(server_type)
        log_mcp_health_check(server_type, connection_info)

        # Add timestamp and status
        health_result = {
            "server_type": server_type,
            "timestamp": asyncio.get_event_loop().time(),
            "healthy": connection_info.get("is_connected", False),
            **connection_info,
        }

        return health_result

    except Exception as e:
        logger.error(f"Error checking MCP health for {server_type}: {e}")
        return {
            "server_type": server_type,
            "timestamp": asyncio.get_event_loop().time(),
            "healthy": False,
            "error": str(e),
            "state": "error",
        }


async def check_all_mcp_health() -> Dict[str, Any]:
    """
    Check the health of all configured MCP servers.

    Returns:
        Dictionary with health check results for all servers
    """
    results = {}

    # Check Cogni MCP
    try:
        results["cogni"] = await check_mcp_health("cogni")
    except Exception as e:
        results["cogni"] = {"server_type": "cogni", "healthy": False, "error": str(e)}

    # Check Playwright MCP
    try:
        results["playwright"] = await check_mcp_health("playwright")
    except Exception as e:
        results["playwright"] = {"server_type": "playwright", "healthy": False, "error": str(e)}

    # Overall health summary
    all_healthy = all(result.get("healthy", False) for result in results.values())
    healthy_count = sum(1 for result in results.values() if result.get("healthy", False))
    total_count = len(results)

    results["summary"] = {
        "all_healthy": all_healthy,
        "healthy_count": healthy_count,
        "total_count": total_count,
        "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0,
    }

    return results


async def force_mcp_reconnection(server_type: str = "cogni") -> Dict[str, Any]:
    """
    Force a reconnection attempt for an MCP server.

    Args:
        server_type: Either "cogni" or "playwright"

    Returns:
        Dictionary with reconnection results
    """
    try:
        logger.info(f"🔄 Forcing reconnection for {server_type} MCP server...")

        # Get the manager and clear its cache
        if server_type == "cogni":
            manager = get_cogni_mcp_manager()
        elif server_type == "playwright":
            manager = get_playwright_mcp_manager()
        else:
            raise ValueError(f"Unknown server type: {server_type}")

        # Clear cache to force reconnection
        manager.clear_cache()

        # Attempt to get tools (will trigger reconnection)
        tools = await manager.get_tools()

        # Get updated connection info
        connection_info = manager.get_connection_info()

        result = {
            "server_type": server_type,
            "success": True,
            "tools_count": len(tools),
            "connection_info": connection_info,
        }

        logger.info(f"✅ Forced reconnection successful for {server_type}: {len(tools)} tools")
        return result

    except Exception as e:
        logger.error(f"❌ Forced reconnection failed for {server_type}: {e}")
        return {"server_type": server_type, "success": False, "error": str(e)}


def print_mcp_status(results: Dict[str, Any]) -> None:
    """
    Print MCP status in a human-readable format.

    Args:
        results: Results from check_all_mcp_health()
    """
    print("=" * 50)
    print("MCP CONNECTION STATUS")
    print("=" * 50)

    summary = results.get("summary", {})
    print(f"Overall Health: {'✅ HEALTHY' if summary.get('all_healthy') else '❌ UNHEALTHY'}")
    print(f"Healthy Servers: {summary.get('healthy_count', 0)}/{summary.get('total_count', 0)}")
    print()

    for server_type, info in results.items():
        if server_type == "summary":
            continue

        print(f"📡 {server_type.upper()} MCP Server:")

        if info.get("healthy"):
            print("  Status: ✅ Connected")
            print(f"  State: {info.get('state', 'unknown')}")
            print(f"  Tools: {info.get('tools_count', 0)}")
        else:
            print("  Status: ❌ Disconnected")
            print(f"  State: {info.get('state', 'unknown')}")
            if info.get("error"):
                print(f"  Error: {info.get('error')}")

        print()


async def mcp_health_monitor_loop(interval: float = 60.0, verbose: bool = False) -> None:
    """
    Run a continuous health monitoring loop.

    Args:
        interval: Check interval in seconds
        verbose: Whether to print detailed status on each check
    """
    logger.info(f"🔍 Starting MCP health monitor (interval: {interval}s)")

    while True:
        try:
            results = await check_all_mcp_health()

            if verbose:
                print_mcp_status(results)

            # Log summary
            summary = results.get("summary", {})
            if summary.get("all_healthy"):
                logger.info(
                    f"✅ All MCP servers healthy ({summary.get('healthy_count')}/{summary.get('total_count')})"
                )
            else:
                logger.warning(
                    f"⚠️ MCP health issues detected ({summary.get('healthy_count')}/{summary.get('total_count')} healthy)"
                )

            await asyncio.sleep(interval)

        except KeyboardInterrupt:
            logger.info("🛑 Health monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in health monitor loop: {e}")
            await asyncio.sleep(interval)


if __name__ == "__main__":
    import sys

    async def main():
        if len(sys.argv) > 1:
            command = sys.argv[1]

            if command == "health":
                results = await check_all_mcp_health()
                print_mcp_status(results)

            elif command == "reconnect":
                server_type = sys.argv[2] if len(sys.argv) > 2 else "cogni"
                result = await force_mcp_reconnection(server_type)
                print(json.dumps(result, indent=2))

            elif command == "monitor":
                interval = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
                await mcp_health_monitor_loop(interval, verbose=True)

            else:
                print(
                    "Usage: python mcp_monitor.py [health|reconnect [server_type]|monitor [interval]]"
                )
        else:
            # Default: show health status
            results = await check_all_mcp_health()
            print_mcp_status(results)

    asyncio.run(main())
