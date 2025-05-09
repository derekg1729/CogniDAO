#!/usr/bin/env python
"""
Script to ingest core project documents into the StructuredMemoryBank.

Assumes the target Dolt database has already been initialized and schemas created/registered.

This script reads predefined core documents (Charter, Manifesto, License, etc.),
and creates 'doc' type MemoryBlocks for them using the CreateDocMemoryBlockTool's logic.

Features:
- Parameterized Dolt DB and Chroma paths via CLI arguments.
- Dry-run mode to preview actions without writing to the database.
- No-commit mode: Writes to Dolt working set & indexes in LlamaIndex, but requires manual Dolt commit.
- Optional JSONL logging for traceability of ingested blocks.
- File existence validation before attempting ingestion.
"""

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
import uuid  # For generating IDs if MemoryBlock default doesn't suffice or for clarity

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool import (
    CreateDocMemoryBlockInput,
    create_doc_memory_block,  # The function, not the tool instance
)
from infra_core.memory_system.schemas.memory_block import (
    MemoryBlock,
)  # Import for manual instantiation
from infra_core.memory_system.dolt_writer import (
    write_memory_block_to_dolt,
)  # For working-set-only mode

# Assuming this script is in a 'scripts' directory at the root of the workspace.
# Adjust if the script is located elsewhere relative to the infra_core module.
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# Add infra_core to sys.path if not running as part of a package or if imports fail
# import sys
# sys.path.insert(0, str(WORKSPACE_ROOT))

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CORE_DOCUMENTS = [
    {
        "source_file_rel_path": "CHARTER.md",
        "title": "Cogni Project Charter",
        "doc_version": "1.0",
        "doc_format": "markdown",
        "tags": ["core-document", "charter", "governance", "foundational"],
        "audience": "all",
        "section": "foundational",
        "completed": True,
        "state": "published",
        "visibility": "internal",
    },
    {
        "source_file_rel_path": "MANIFESTO.md",
        "title": "Cogni Project Manifesto",
        "doc_version": "1.0",
        "doc_format": "markdown",
        "tags": ["core-document", "manifesto", "philosophy", "foundational"],
        "audience": "all",
        "section": "foundational",
        "completed": True,
        "state": "published",
        "visibility": "internal",
    },
    {
        "source_file_rel_path": "LICENSE.md",
        "title": "Project License",
        "doc_version": "N/A",  # Or specific license e.g. "MIT"
        "doc_format": "markdown",  # Assuming it's markdown, could be plain 'text'
        "tags": ["core-document", "license", "legal", "foundational"],
        "audience": "all",
        "section": "legal",
        "completed": True,
        "state": "published",
        "visibility": "public",  # Licenses are typically public
    },
    {
        "source_file_rel_path": "data/memory_banks/core/main/guide_cogni-core-spirit.md",
        "title": "Cogni Core Spirit Guide",
        "doc_version": "1.0",
        "doc_format": "markdown",
        "tags": ["core-document", "philosophy", "guidance", "foundational"],
        "audience": "all",
        "section": "philosophy",
        "completed": True,
        "state": "published",
        "visibility": "internal",
    },
]


def main():
    parser = argparse.ArgumentParser(description="Ingest core project documents into memory.")
    parser.add_argument(
        "--dolt-db-path", required=True, help="Path to the Dolt database directory."
    )
    parser.add_argument(
        "--chroma-path",
        required=True,
        help="Path for ChromaDB (e.g., ':memory:' or a directory path).",
    )
    parser.add_argument(
        "--chroma-collection", default="core_documents_collection", help="ChromaDB collection name."
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run", action="store_true", help="Simulate ingestion without writing to DB."
    )
    mode_group.add_argument(
        "--no-commit",
        action="store_true",
        help="Write to Dolt working set and LlamaIndex, but do not commit Dolt changes.",
    )

    parser.add_argument(
        "--log-file", type=str, help="Optional JSONL file to log successful ingestions."
    )
    parser.add_argument(
        "--created-by",
        default="ingestion_script:core_docs",
        help="Identifier for the creator of these blocks.",
    )

    args = parser.parse_args()

    logger.info(f"Starting core document ingestion script with args: {args}")
    logger.info(
        f"Assuming Dolt DB at '{args.dolt_db_path}' is initialized and schemas are registered."
    )

    # Instantiate StructuredMemoryBank - still needed for schema version lookup in working-set-only mode
    # and for the normal run mode.
    memory_bank = None
    # Instantiate unless in dry-run mode (not needed for simulation)
    if not args.dry_run:
        try:
            memory_bank = StructuredMemoryBank(
                dolt_db_path=args.dolt_db_path,
                chroma_path=args.chroma_path,  # Still needed for SMB instantiation
                chroma_collection=args.chroma_collection,
            )
            logger.info("StructuredMemoryBank instantiated.")
        except Exception as e:
            # If SMB fails to init (e.g., DB path invalid), we can't proceed in non-dry-run modes.
            logger.error(
                f"Failed to instantiate StructuredMemoryBank targeting Dolt DB '{args.dolt_db_path}'. Aborting. Error: {e}"
            )
            return

    ingested_count = 0
    indexed_count = 0
    skipped_count = 0
    dolt_write_failures = 0
    index_failures = 0

    for doc_details in CORE_DOCUMENTS:
        source_file_abs_path = WORKSPACE_ROOT / doc_details["source_file_rel_path"]
        logger.info(f"Processing document: {source_file_abs_path}")

        if not source_file_abs_path.exists() or not source_file_abs_path.is_file():
            logger.error(f"Source file not found or not a file: {source_file_abs_path}. Skipping.")
            skipped_count += 1
            continue

        try:
            content = source_file_abs_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read file {source_file_abs_path}: {e}. Skipping.")
            skipped_count += 1
            continue

        # Common metadata preparation
        doc_metadata_payload = {
            "title": doc_details["title"],
            "audience": doc_details.get("audience"),
            "section": doc_details.get("section"),
            "version": doc_details.get("doc_version"),
            "last_reviewed": doc_details.get("last_reviewed"),
            "format": doc_details.get("doc_format"),
            "completed": doc_details.get("completed", False),
            "x_tool_id": "ingestion_script:core_docs",  # Identify script as creator in metadata
        }
        # Filter out None values from metadata for cleaner storage if desired by `create_doc_memory_block`
        # For direct MemoryBlock instantiation, all fields will be present or have defaults.

        if args.dry_run:
            # Simulate CreateDocMemoryBlockInput for logging consistency
            # simulated_input = CreateDocMemoryBlockInput(
            #     title=doc_details["title"],
            #     content=content,
            #     audience=doc_details.get("audience"),
            #     section=doc_details.get("section"),
            #     doc_version=doc_details.get("doc_version"),
            #     last_reviewed=doc_details.get("last_reviewed"),
            #     doc_format=doc_details.get("doc_format"),
            #     completed=doc_details.get("completed", False),
            #     source_file=str(source_file_abs_path),
            #     tags=doc_details.get("tags", []),
            #     state=doc_details.get("state", "draft"),
            #     visibility=doc_details.get("visibility", "internal"),
            #     created_by=args.created_by,
            # )
            # logger.info(
            #     f"[Dry Run] Would create memory block for '{doc_details['title']}' with input like: {{simulated_input.model_dump_json(indent=2)}}"
            # )
            logger.info(
                f"[Dry Run] Would simulate creating memory block for '{doc_details['title']}'."
            )  # Simplified log for F841
            ingested_count += 1
            indexed_count += 1
            continue
        elif args.no_commit:
            logger.info(f"[No Commit Mode] Processing: {doc_details['title']}")
            if not memory_bank or not memory_bank.llama_memory:
                logger.error("MemoryBank or LlamaMemory not initialized correctly. Skipping.")
                skipped_count += 1
                continue
            try:
                schema_ver = 2  # Directly use the known schema version from registry.py
                logger.info(
                    f"[No Commit Mode] Using hardcoded schema_version: {schema_ver} for type 'doc'"
                )

                block_to_process = MemoryBlock(
                    id=str(uuid.uuid4()),
                    type="doc",
                    text=content,
                    schema_version=schema_ver,
                    metadata=doc_metadata_payload,
                    tags=doc_details.get("tags", []),
                    state=doc_details.get("state", "draft"),
                    visibility=doc_details.get("visibility", "internal"),
                    source_file=str(source_file_abs_path),
                    created_by=args.created_by,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

                # Step 1: Write to Dolt working set
                write_success, _ = write_memory_block_to_dolt(
                    block=block_to_process, db_path=args.dolt_db_path, auto_commit=False
                )
                if write_success:
                    logger.info(
                        f"[No Commit Mode] Successfully wrote '{doc_details['title']}' (ID: {block_to_process.id}) to Dolt working set."
                    )
                    # Step 2: Index in LlamaIndex
                    try:
                        memory_bank.llama_memory.add_block(block_to_process)
                        index_success = True
                        logger.info(
                            f"[No Commit Mode] Successfully indexed '{doc_details['title']}' in LlamaIndex."
                        )
                    except Exception as index_e:
                        logger.error(
                            f"[No Commit Mode] Failed to index '{doc_details['title']}' in LlamaIndex: {index_e}",
                            exc_info=True,
                        )
                        index_failures += 1
                        # Continue even if indexing fails in this mode, as user wants Dolt write preserved
                else:
                    logger.error(
                        f"[No Commit Mode] Failed to write '{doc_details['title']}' to Dolt working set."
                    )
                    dolt_write_failures += 1
            except Exception as e:
                logger.error(
                    f"[No Commit Mode] General exception for '{doc_details['title']}': {e}",
                    exc_info=True,
                )
            # Update counts based on success
            if write_success:
                ingested_count += 1  # Counts Dolt write success
            if index_success:
                indexed_count += 1  # Counts LlamaIndex success
            elif write_success:  # If write succeeded but index failed
                pass  # Already accounted for index_failures
            else:  # If write failed, definitely skipped
                if block_to_process:  # Avoid counting general exceptions twice
                    skipped_count += 1
            continue

        # Normal run (full ingestion with commit and LlamaIndex)
        try:
            input_data = CreateDocMemoryBlockInput(
                title=doc_details["title"],
                content=content,
                audience=doc_details.get("audience"),
                section=doc_details.get("section"),
                doc_version=doc_details.get("doc_version"),
                last_reviewed=doc_details.get("last_reviewed"),
                doc_format=doc_details.get("doc_format"),
                completed=doc_details.get("completed", False),
                source_file=str(source_file_abs_path),
                tags=doc_details.get("tags", []),
                state=doc_details.get("state", "draft"),
                visibility=doc_details.get("visibility", "internal"),
                created_by=args.created_by,
            )
            logger.info(f"Attempting to create memory block (full mode): {input_data.title}")
            if not memory_bank:
                logger.error("MemoryBank not initialized for normal run. Aborting.")
                return

            result = create_doc_memory_block(input_data, memory_bank)

            if result.success and result.id:
                logger.info(
                    f"Successfully created and indexed memory block for '{doc_details['title']}'. ID: {result.id}"
                )
                ingested_count += 1
                indexed_count += 1  # Assume success implies indexing in normal mode
                if args.log_file:
                    log_entry = {
                        "block_id": result.id,
                        "source_file": str(source_file_abs_path),
                        "title": doc_details["title"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "success",
                    }
                    try:
                        with open(args.log_file, "a", encoding="utf-8") as lf:
                            lf.write(json.dumps(log_entry) + "\n")
                    except Exception as e:
                        logger.error(f"Failed to write to log file {args.log_file}: {e}")
            else:
                logger.error(
                    f"Failed to create memory block (full mode) for '{doc_details['title']}'. Error: {result.error}"
                )
                # Determine if it was a write or index failure if possible from error, otherwise count as skipped
                skipped_count += 1
                dolt_write_failures += 1  # Assume failure includes Dolt write issue
                index_failures += 1  # Assume failure includes index issue
        except Exception as e:
            logger.error(
                f"Exception during memory block creation (full mode) for '{doc_details['title']}': {e}",
                exc_info=True,
            )
            skipped_count += 1
            dolt_write_failures += 1
            index_failures += 1

    logger.info("--- Ingestion Summary ---")
    logger.info(
        f"Mode: {'Dry Run' if args.dry_run else ('No Commit' if args.no_commit else 'Normal')}"
    )
    logger.info(f"Attempted to process: {len(CORE_DOCUMENTS)} documents")
    if args.dry_run:
        logger.info(
            f"Simulated processing (counts as success for summary): {ingested_count} documents"
        )
    else:
        logger.info(f"Successfully wrote to Dolt: {ingested_count} documents")
        logger.info(f"Successfully indexed in LlamaIndex: {indexed_count} documents")
        logger.info(f"Dolt write failures: {dolt_write_failures}")
        logger.info(f"LlamaIndex failures: {index_failures}")
    logger.info(f"Skipped due to file errors or general exceptions: {skipped_count} documents")
    if args.no_commit:
        logger.info(
            "Data written to Dolt working set and LlamaIndex updated. Please inspect and commit Dolt changes manually if satisfied."
        )
    elif not args.dry_run:
        logger.info("Normal run complete. Dolt changes were committed.")
    logger.info("Core document ingestion script finished.")


if __name__ == "__main__":
    main()
