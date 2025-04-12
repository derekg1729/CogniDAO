"""
Parser module for extracting blocks from Logseq markdown files.

This module provides functionality to:
1. Scan directories for Logseq markdown files
2. Extract blocks with specified tags
3. Parse block metadata
4. Create structured data for memory storage
"""

import os
import re
import glob
import uuid
import logging
from typing import List, Dict, Set, Optional
from pathlib import Path
from datetime import datetime
import frontmatter  # For parsing YAML frontmatter in markdown

from infra_core.memory.schema import MemoryBlock


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LogseqParser:
    """
    Parser for Logseq markdown files to extract tagged blocks.
    
    This class handles finding markdown files in a directory,
    extracting blocks with specific tags, and parsing metadata.
    """
    
    def __init__(self, logseq_dir: str, target_tags: Optional[Set[str]] = None):
        """
        Initialize the parser with a Logseq directory.
        
        Args:
            logseq_dir: Path to directory containing Logseq markdown files
            target_tags: Set of tags to filter for (default: {"#thought", "#broadcast", "#approved"})
        """
        self.logseq_dir = Path(logseq_dir)
        self.target_tags = target_tags or {"#thought", "#broadcast", "#approved"}
        
        # Validate directory exists
        if not self.logseq_dir.exists():
            raise FileNotFoundError(f"Logseq directory not found: {self.logseq_dir}")
        
        logger.info(f"Initialized LogseqParser for directory: {self.logseq_dir}")
        logger.info(f"Target tags: {self.target_tags}")
    
    def get_markdown_files(self) -> List[str]:
        """
        Find all markdown files in the Logseq directory.
        
        Returns:
            List of paths to markdown files
        """
        pattern = os.path.join(self.logseq_dir, "**/*.md")
        md_files = glob.glob(pattern, recursive=True)
        logger.info(f"Found {len(md_files)} markdown files in {self.logseq_dir}")
        return md_files
    
    def _extract_frontmatter(self, content: str) -> Dict:
        """
        Extract YAML frontmatter from markdown content.
        
        Args:
            content: Markdown content
            
        Returns:
            Dictionary of frontmatter metadata
        """
        try:
            post = frontmatter.loads(content)
            return post.metadata
        except Exception as e:
            logger.warning(f"Error extracting frontmatter: {e}")
            return {}
    
    def _extract_file_date(self, file_path: str) -> Optional[datetime]:
        """
        Extract date from Logseq journal filename (YYYY_MM_DD.md).
        
        Args:
            file_path: Path to markdown file
            
        Returns:
            Datetime object or None if not a journal file
        """
        filename = os.path.basename(file_path)
        # Match Logseq journal filename pattern
        match = re.match(r"(\d{4})_(\d{2})_(\d{2})\.md", filename)
        if match:
            year, month, day = map(int, match.groups())
            try:
                return datetime(year, month, day)
            except ValueError:
                return None
        return None
    
    def _extract_block_tags(self, text: str) -> Set[str]:
        """
        Extract tags from block text.
        
        Args:
            text: Block text
            
        Returns:
            Set of tags found in the text
        """
        # Match hashtags but ignore URLs with #fragments
        tags = {tag for tag in text.split() if tag.startswith("#") and not tag.startswith("http")}
        return tags
    
    def _parse_block_references(self, text: str) -> List[str]:
        """
        Extract Logseq block references from text.
        
        Args:
            text: Block text
            
        Returns:
            List of block references
        """
        # Match Logseq block reference pattern ((block-id))
        refs = re.findall(r"\(\(([\w\d-]+)\)\)", text)
        return refs
    
    def _generate_block_id(self, text: str, file_path: str) -> str:
        """
        Generate a unique ID for a block.
        
        Args:
            text: Block text
            file_path: Source file path
            
        Returns:
            Unique ID for the block
        """
        # Create a deterministic ID if possible
        content_hash = hash(text + os.path.basename(file_path))
        return f"block-{abs(content_hash)}"
    
    def extract_blocks_from_file(self, file_path: str) -> List[Dict]:
        """
        Extract blocks from a single markdown file.
        
        Args:
            file_path: Path to markdown file
            
        Returns:
            List of dictionaries representing blocks
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Extract metadata from frontmatter if available
            frontmatter_metadata = self._extract_frontmatter(content)
            
            # Extract date from filename
            file_date = self._extract_file_date(file_path)
            
            # Process file line by line to extract blocks
            lines = content.split("\n")
            blocks = []
            
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Check if line is a Logseq block (starts with - or *)
                if not (line.strip().startswith("-") or line.strip().startswith("*")):
                    continue
                
                # Extract the actual content (remove the bullet)
                text = line.strip()
                if text.startswith("- "):
                    text = text[2:]
                elif text.startswith("* "):
                    text = text[2:]
                
                # Extract tags
                tags = self._extract_block_tags(text)
                
                # Check if block has any of the target tags
                if not (tags & self.target_tags):
                    continue
                
                # Extract block references
                refs = self._parse_block_references(text)
                
                # Generate block ID
                block_id = self._generate_block_id(text, file_path)
                
                # Create source URI
                source_uri = None
                if file_date:
                    source_uri = f"logseq://{file_date.isoformat()}#{block_id}"
                
                # Create block with metadata
                block = {
                    "id": block_id,
                    "text": text,
                    "tags": list(tags),
                    "source_file": os.path.basename(file_path),
                    "source_uri": source_uri,
                    "references": refs,
                    "created_at": file_date.isoformat() if file_date else datetime.now().isoformat(),
                    "metadata": {
                        "frontmatter": frontmatter_metadata,
                        "file_date": file_date.isoformat() if file_date else None
                    }
                }
                
                blocks.append(block)
            
            logger.debug(f"Extracted {len(blocks)} blocks from {file_path}")
            return blocks
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return []
    
    def extract_all_blocks(self) -> List[Dict]:
        """
        Extract all blocks from all markdown files.
        
        Returns:
            List of dictionaries representing blocks
        """
        all_blocks = []
        md_files = self.get_markdown_files()
        
        for file_path in md_files:
            blocks = self.extract_blocks_from_file(file_path)
            all_blocks.extend(blocks)
        
        logger.info(f"Extracted {len(all_blocks)} total blocks from {len(md_files)} files")
        return all_blocks
    
    def create_memory_blocks(self) -> List[MemoryBlock]:
        """
        Create MemoryBlock objects from extracted blocks.
        
        Returns:
            List of MemoryBlock objects
        """
        blocks_data = self.extract_all_blocks()
        memory_blocks = []
        
        for block_data in blocks_data:
            try:
                # Convert to MemoryBlock, handling potential missing fields
                memory_block = MemoryBlock(
                    id=block_data["id"],
                    text=block_data["text"],
                    tags=block_data["tags"],
                    source_file=block_data["source_file"],
                    source_uri=block_data.get("source_uri"),
                    metadata=block_data.get("metadata", {})
                )
                memory_blocks.append(memory_block)
            except Exception as e:
                logger.error(f"Error creating MemoryBlock: {e}, data: {block_data}")
        
        return memory_blocks


def load_md_files(folder: str) -> List[str]:
    """
    Find all markdown files in a directory.
    
    Args:
        folder: Path to directory
        
    Returns:
        List of paths to markdown files
    """
    return glob.glob(os.path.join(folder, "**/*.md"), recursive=True)


def extract_blocks(file_path: str, target_tags: Set[str] = None) -> List[Dict]:
    """
    Extract blocks from a markdown file that match target tags.
    
    This is a standalone function that provides similar functionality
    to the LogseqParser class but for a single file. It's maintained
    for backward compatibility with the existing codebase.
    
    Args:
        file_path: Path to markdown file
        target_tags: Set of tags to filter for (default: {"#thought", "#broadcast", "#approved"})
        
    Returns:
        List of dictionaries representing blocks
    """
    if target_tags is None:
        target_tags = {"#thought", "#broadcast", "#approved"}
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        blocks = []
        for line in lines:
            # Extract tags and check if any match target tags
            tags = {tag for tag in line.split() if tag.startswith("#")}
            if tags & target_tags:
                block_id = str(uuid.uuid4())  # Use UUID for compatibility with existing code
                
                # Create block with metadata
                block = {
                    "id": block_id,
                    "text": line.strip(),
                    "tags": list(tags),
                    "source_file": os.path.basename(file_path)
                }
                
                blocks.append(block)
                
        return blocks
    except Exception as e:
        logger.error(f"Error extracting blocks from {file_path}: {e}")
        return [] 