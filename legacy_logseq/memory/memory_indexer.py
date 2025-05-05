import argparse
import glob
import logging
import os
import sys
import uuid
import warnings
from typing import Any, Callable, Optional

import chromadb
from tqdm import tqdm  # For progress reporting

from legacy_logseq.memory.parser import LogseqParser

# Silence warnings from dependencies
warnings.filterwarnings("ignore", message=".*No ONNX providers provided.*")
warnings.filterwarnings("ignore", category=UserWarning, module="chromadb")
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=UserWarning, module="sentence_transformers")

# Configure logging - set default level to WARNING for most modules
logging.basicConfig(
    level=logging.WARNING,  # Default to WARNING to reduce noise
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Only show INFO logs for our code by default
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Silence third-party loggers by default
for module in ["chromadb", "urllib3", "sentence_transformers", "huggingface_hub", "transformers"]:
    logging.getLogger(module).setLevel(logging.WARNING)

# === CONFIG ===
LOGSEQ_DIR = "./logseq"  # Path to your .md files
TARGET_TAGS = {"#thought", "#broadcast", "#approved"}
VECTOR_DB_DIR = "legacy_logseq/memory/chroma"
# Default embedding model: BGE is an open-source model that performs well without API keys
# This can be configured via:
# 1. Command line argument (--embed-model)
# 2. Environment variable (COGNI_EMBED_MODEL)
# 3. Default value below
EMBED_MODEL = os.environ.get("COGNI_EMBED_MODEL", "bge")


def init_chroma_client(vector_db_dir: str = VECTOR_DB_DIR) -> chromadb.PersistentClient:
    """Initialize the ChromaDB client with the given directory.

    Args:
        vector_db_dir: Directory to store ChromaDB files

    Returns:
        ChromaDB PersistentClient instance

    Raises:
        Exception: If ChromaDB client initialization fails
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(vector_db_dir, exist_ok=True)
        logger.info("Initializing ChromaDB client with directory: %s", vector_db_dir)

        # Initialize without any default embedding function to avoid ONNX warnings
        return chromadb.PersistentClient(
            path=vector_db_dir,
            settings=chromadb.Settings(
                anonymized_telemetry=False,  # Disable telemetry for privacy
                allow_reset=True,  # Allow resetting collection if needed
                chroma_server_ssl_enabled=False,  # Disable SSL for local dev
            ),
        )
    except Exception as e:
        logger.error("Failed to initialize ChromaDB client: %s", e)
        raise


def init_embedding_function(embed_model: str = EMBED_MODEL) -> Callable:
    """Initialize the embedding function based on the model type.

    Embedding models have different characteristics:
    - bge: Open-source model, 384 dimensions, good performance, no API key needed
    - mock: For testing only - returns fixed vectors, useful for CI/CD or testing

    The choice of embedding model depends on the use case:
    - For production: Use a high-quality embedding model like "bge"
    - For testing: Use "mock" embeddings
    - For different languages: Consider language-specific models

    Args:
        embed_model: Type of embedding model to use - "bge" or "mock"

    Returns:
        Callable embedding function that converts text to vectors

    Raises:
        NotImplementedError: If unknown embedding model is specified
        Exception: If embedding function initialization fails

    """
    try:
        logger.info("Initializing embedding function with model: %s", embed_model)

        if embed_model == "bge":
            # Use BGE (BAAI) embeddings - open source, great performance, 384 dimensions
            try:
                from sentence_transformers import SentenceTransformer

                # Determine the best device to use (CPU/GPU/MPS)
                device = None  # Let the library choose the appropriate device

                # If torch is available, try to get optimal device
                try:
                    import torch

                    if torch.cuda.is_available():  # NVIDIA GPU
                        device = "cuda"
                        logger.info("Using CUDA device for embeddings")
                    elif (
                        hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                    ):  # Apple Silicon
                        device = "mps"
                        logger.info("Using MPS device for embeddings")
                    else:  # CPU
                        device = "cpu"
                        logger.info("Using CPU device for embeddings")
                except ImportError:
                    logger.info("Torch not available, using default device")

                # Initialize the model with appropriate device
                model = SentenceTransformer("BAAI/bge-small-en-v1.5", device=device)

                class BGEEmbedder:
                    def __call__(self, texts):
                        return model.encode(texts).tolist()

                logger.info(
                    "Using BGE embeddings (384 dimensions) on device: %s", device or "default"
                )
                return BGEEmbedder()
            except ImportError:
                logger.error(
                    "sentence-transformers package not installed. Run: pip install sentence-transformers"
                )
                raise
        elif embed_model == "mock":
            # Mock embedding function for testing - 1536 dimensions
            logger.info("Using mock embedding function (1536 dimensions)")

            class MockEmbeddingFunction:
                def __call__(self, texts):
                    return [[0.1] * 1536 for _ in texts]

            return MockEmbeddingFunction()
        else:
            logger.error("Embedding model %s not implemented yet", embed_model)
            raise NotImplementedError(f"Embedding model {embed_model} not implemented")

    except Exception as e:
        logger.error("Failed to initialize embedding function: %s", e)
        raise


def load_md_files(folder: str) -> list[str]:
    """Find all markdown files in a directory.

    Args:
        folder: Path to directory

    Returns:
        List of paths to markdown files

    """
    return glob.glob(os.path.join(folder, "**/*.md"), recursive=True)


def extract_blocks(file_path: str, target_tags: Optional[set[str]] = None) -> list[dict]:
    """Extract blocks from a markdown file that match target tags.

    This is a legacy function maintained for backward compatibility.
    New code should use the LogseqParser class instead.

    Args:
        file_path: Path to markdown file
        target_tags: Set of tags to filter for (default: TARGET_TAGS)

    Returns:
        List of dictionaries representing blocks

    """
    if target_tags is None:
        target_tags = TARGET_TAGS

    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        blocks = []
        for line in lines:
            # Extract tags and check if any match target tags
            tags = {tag for tag in line.split() if tag.startswith("#")}
            if tags & target_tags:
                block_id = str(uuid.uuid4())

                # Create block with metadata
                block = {
                    "id": block_id,
                    "text": line.strip(),
                    "tags": list(tags),
                    "source_file": os.path.basename(file_path),
                }

                blocks.append(block)
        return blocks
    except Exception:
        logger.exception("Error extracting blocks from %s", file_path)
        return []


def index_blocks(blocks: list[dict], collection: Any, embed_fn: Callable) -> None:
    """Index blocks using the provided collection and embedding function.

    Args:
        blocks: List of block dictionaries to index
        collection: ChromaDB collection to store blocks
        embed_fn: Embedding function to convert text to vectors

    Raises:
        Exception: If indexing fails

    """
    try:
        # Use tqdm with disable parameter to control progress bar display
        show_progress = logger.level <= logging.INFO
        for block in tqdm(blocks, desc="Embedding blocks", disable=not show_progress):
            embedding = embed_fn([block["text"]])[0]

            # Convert tags list to a string for ChromaDB metadata (which requires scalar values)
            tags_str = ", ".join(block["tags"])

            collection.add(
                ids=[block["id"]],
                embeddings=[embedding],
                documents=[block["text"]],
                metadatas=[
                    {
                        "tags": tags_str,  # Use string instead of list
                        "source": block["source_file"],
                        "source_uri": block.get("source_uri", ""),
                    }
                ],
            )
        logger.info("Successfully indexed %d blocks", len(blocks))
    except Exception as e:
        logger.exception("Error during block indexing: %s", e)
        raise


def run_indexing(
    logseq_dir: str = LOGSEQ_DIR,
    vector_db_dir: str = VECTOR_DB_DIR,
    embed_model: str = EMBED_MODEL,
    client: Optional[Any] = None,
    embed_fn: Optional[Callable] = None,
    target_tags: Optional[set[str]] = None,
    collection_name: str = "cogni-memory",
    verbose: bool = False,
) -> int:
    """Run the indexing process to extract, embed, and store blocks from Logseq files.

    Args:
        logseq_dir: Directory containing Logseq .md files
        vector_db_dir: Directory to store ChromaDB files
        embed_model: Type of embedding model to use
        client: Optional pre-initialized ChromaDB client
        embed_fn: Optional pre-initialized embedding function
        target_tags: Optional set of tags to filter for (default: TARGET_TAGS)
        collection_name: Name of the ChromaDB collection
        verbose: Whether to display verbose logging

    Returns:
        Number of blocks indexed (0 if none or error)

    """
    # Set logging level based on verbosity
    if verbose:
        # Enable DEBUG logs for our modules
        logger.setLevel(logging.DEBUG)
        logging.getLogger("legacy_logseq").setLevel(logging.DEBUG)
    else:
        # Keep default levels in non-verbose mode
        logger.setLevel(logging.INFO)
        logging.getLogger("legacy_logseq").setLevel(logging.INFO)

        # Explicitly silence all third-party logs in non-verbose mode
        for module in [
            "chromadb",
            "urllib3",
            "sentence_transformers",
            "huggingface_hub",
            "transformers",
            "tqdm",
        ]:
            logging.getLogger(module).setLevel(logging.WARNING)

    # Ensure directories exist
    os.makedirs(logseq_dir, exist_ok=True)
    os.makedirs(vector_db_dir, exist_ok=True)

    logger.info("Starting indexing process for Logseq directory: %s", logseq_dir)

    try:
        # Use default target tags if not provided
        if target_tags is None:
            target_tags = TARGET_TAGS

        # Initialize client and collection if not provided
        if client is None:
            client = init_chroma_client(vector_db_dir)

        # Get or create collection
        try:
            collection = client.get_collection(name=collection_name)
            logger.info("Using existing collection: %s", collection_name)
        except ValueError:
            collection = client.create_collection(name=collection_name)
            logger.info("Created new collection: %s", collection_name)

        # Initialize embedding function if not provided
        if embed_fn is None:
            embed_fn = init_embedding_function(embed_model)

        # Create parser and extract blocks
        parser = LogseqParser(logseq_dir, target_tags)
        blocks = parser.extract_all_blocks()

        if not blocks:
            logger.warning("No blocks found in %s with tags %s", logseq_dir, target_tags)
            return 0

        logger.info("Found %d blocks to index", len(blocks))

        # Index blocks
        index_blocks(blocks, collection, embed_fn)

        total_indexed = len(blocks)
        logger.info("✅ Successfully indexed %d blocks", total_indexed)
        return total_indexed

    except Exception as e:
        logger.exception("Error during indexing: %s", e)
        return 0


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments

    """
    parser = argparse.ArgumentParser(
        description="Index Logseq blocks to ChromaDB",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--logseq-dir",
        type=str,
        default=LOGSEQ_DIR,
        help="Directory containing Logseq .md files",
    )
    parser.add_argument(
        "--vector-db-dir",
        type=str,
        default=VECTOR_DB_DIR,
        help="Directory to store ChromaDB files",
    )
    parser.add_argument(
        "--embed-model",
        type=str,
        default=EMBED_MODEL,
        choices=["bge", "mock"],
        help="Type of embedding model to use",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="cogni-memory",
        help="Name of the ChromaDB collection",
    )
    parser.add_argument(
        "--tags",
        type=str,
        nargs="+",
        default=None,
        help="Tags to filter for (default: #thought #broadcast #approved)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display verbose logging",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Convert tags to set with hashtags
    target_tags = None
    if args.tags:
        target_tags = {f"#{tag.lstrip('#')}" for tag in args.tags}

    try:
        total_indexed = run_indexing(
            logseq_dir=args.logseq_dir,
            vector_db_dir=args.vector_db_dir,
            embed_model=args.embed_model,
            target_tags=target_tags,
            collection_name=args.collection,
            verbose=args.verbose,
        )

        if total_indexed > 0:
            logger.info("Indexing successful: %d blocks indexed", total_indexed)
            sys.exit(0)  # Success
        else:
            logger.warning("No blocks were indexed")
            sys.exit(1)  # No blocks indexed

    except Exception as e:
        logger.exception("Indexing failed: %s", e)
        sys.exit(2)  # Error
