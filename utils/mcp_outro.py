import json
import logging
from typing import Dict

from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Use standard Python logger as fallback, but prefer Prefect logger when available
logger = logging.getLogger(__name__)

try:
    from prefect.logging import get_run_logger

    # If we're in a Prefect context, use Prefect logger
    def get_logger():
        try:
            return get_run_logger()
        except Exception:
            return logger
except ImportError:
    # Fallback to standard logger if not in Prefect context
    def get_logger():
        return logger


async def automated_dolt_outro(session, flow_context: str = "") -> Dict[str, str]:
    """Gets status+diff, asks GPT-4o for a commit message, then pushes."""

    # Get the appropriate logger
    log = get_logger()
    log.info("🚀 Starting automated Dolt outro routine...")
    log.info(f"   Flow context: {flow_context}")

    try:
        # Get current Dolt status and staged diff
        log.info("📊 Getting Dolt status...")
        status_result = await session.call_tool("DoltStatus", {"input": "{}"})
        log.info(f"   Status result type: {type(status_result)}")
        log.info(
            f"   Status result content: {status_result.content if hasattr(status_result, 'content') else 'No content attr'}"
        )

        log.info("📋 Getting Dolt diff...")
        diff_result = await session.call_tool("DoltDiff", {"input": json.dumps({"mode": "staged"})})
        log.info(f"   Diff result type: {type(diff_result)}")
        log.info(
            f"   Diff result content: {diff_result.content if hasattr(diff_result, 'content') else 'No content attr'}"
        )

        # Extract content from MCP results (they return list of TextContent objects)
        if status_result.content and len(status_result.content) > 0:
            status_content = status_result.content[0].text
            status_data = json.loads(status_content)
            log.info(f"   Parsed status data: {status_data}")
        else:
            status_data = {"current_branch": "unknown"}
            log.warning("   No status content available")

        if diff_result.content and len(diff_result.content) > 0:
            diff_content = diff_result.content[0].text
            log.info(f"   Diff content length: {len(diff_content)} chars")
        else:
            diff_content = "No diff available"
            log.warning("   No diff content available")

        # Create prompt for GPT-4o-mini to generate commit message
        prompt = f"""Based on the following Dolt data, write a concise commit message (≤2 sentences).

## Branch
`{status_data.get("current_branch", "unknown")}`

## Status
{status_data}

## Diff (staged)
{diff_content}

Context: {flow_context}"""

        log.info("🤖 Generating AI commit message...")
        log.info(f"   Prompt length: {len(prompt)} chars")

        # Use AutoGen OpenAI client to generate commit message
        llm = OpenAIChatCompletionClient(model="gpt-4o-mini")

        try:
            response = await llm.create([UserMessage(content=prompt, source="user")])
            commit_msg = response.content.strip()
            log.info(f"✅ Generated commit message: {commit_msg}")
        except Exception as e:
            log.error(f"❌ AI generation failed: {e}")
            commit_msg = f"data: {flow_context} - automated commit (AI failed)"
        finally:
            await llm.close()

        # Check if there are any changes to commit first
        if status_data.get("is_clean", True) and status_data.get("total_changes", 0) == 0:
            log.info("📝 Working tree is clean - no changes to commit")
            log.info("🎉 Automated Dolt outro completed (no changes to commit)")
            return {
                "commit_message": commit_msg,
                "push_result": "No changes to commit - working tree clean",
                "status": "clean",
            }

        log.info(f"🔨 Auto-committing: {commit_msg}")

        # Auto-commit and push using the provided session
        log.info("🚀 Proceeding with auto-commit and push...")
        push_result = await session.call_tool(
            "DoltAutoCommitAndPush",
            {"input": json.dumps({"commit_message": commit_msg, "author": "automated-outro"})},
        )

        log.info(f"   Push result type: {type(push_result)}")
        log.info(
            f"   Push result content: {push_result.content if hasattr(push_result, 'content') else 'No content attr'}"
        )

        # Extract push result content
        if push_result.content and len(push_result.content) > 0:
            push_content = push_result.content[0].text
            log.info(f"✅ Push completed: {push_content[:200]}...")
        else:
            push_content = "Push result not available"
            log.warning("   No push result content available")

        log.info("🎉 Automated Dolt outro completed successfully!")

        return {"commit_message": commit_msg, "push_result": push_content, "status": "committed"}

    except Exception as e:
        log.error(f"❌ Automated Dolt outro failed: {type(e).__name__}: {e}")
        import traceback

        log.error(f"   Full traceback: {traceback.format_exc()}")
        # Return error info instead of raising to avoid breaking the flow
        return {"commit_message": f"ERROR: {str(e)}", "push_result": f"Failed: {str(e)}"}
