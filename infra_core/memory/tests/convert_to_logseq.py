"""
Convert regular markdown files to Logseq format for testing.

This script takes standard markdown files and converts them
to Logseq-compatible format by adding bullet points to each line.
"""

import os
import argparse
from pathlib import Path


def convert_to_logseq(input_file, output_file=None, add_tag=None):
    """
    Convert regular markdown to Logseq format with bullet points.
    
    Args:
        input_file: Path to input markdown file
        output_file: Path to output file (default: input_file with _logseq suffix)
        add_tag: Optional tag to add to each line for testing
        
    Returns:
        Path to the output file
    """
    # Determine output file if not specified
    if not output_file:
        input_path = Path(input_file)
        output_file = str(input_path.with_stem(f"{input_path.stem}_logseq"))
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Convert to Logseq format by adding bullet points to each line
    lines = content.split('\n')
    converted_lines = []
    
    for line in lines:
        if not line.strip():
            # Keep empty lines as is
            converted_lines.append(line)
            continue
        
        if line.strip().startswith('#'):
            # For headings, keep the heading level
            if add_tag:
                converted_lines.append(f"- {line.strip()} {add_tag}")
            else:
                converted_lines.append(f"- {line.strip()}")
        else:
            # For regular text
            if add_tag:
                converted_lines.append(f"- {line.strip()} {add_tag}")
            else:
                converted_lines.append(f"- {line.strip()}")
    
    # Write converted content to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(converted_lines))
    
    print(f"Converted {input_file} to Logseq format at {output_file}")
    return output_file


def convert_directory(input_dir, output_dir=None, add_tag=None):
    """
    Convert all markdown files in a directory to Logseq format.
    
    Args:
        input_dir: Path to input directory
        output_dir: Path to output directory (default: input_dir/logseq_format)
        add_tag: Optional tag to add to each line for testing
        
    Returns:
        Path to the output directory
    """
    # Determine output directory if not specified
    if not output_dir:
        output_dir = os.path.join(input_dir, "logseq_format")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all markdown files in input directory
    md_files = list(Path(input_dir).glob("**/*.md"))
    
    for md_file in md_files:
        # Skip files in the output directory
        if os.path.commonpath([output_dir]) in os.path.commonpath([str(md_file)]):
            continue
        
        # Determine relative path to preserve directory structure
        rel_path = os.path.relpath(str(md_file), input_dir)
        output_file = os.path.join(output_dir, rel_path)
        
        # Create parent directories if needed
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Convert file
        convert_to_logseq(str(md_file), output_file, add_tag)
    
    print(f"Converted {len(md_files)} files to Logseq format in {output_dir}")
    return output_dir


def main():
    """Parse command line arguments and convert files."""
    parser = argparse.ArgumentParser(description='Convert markdown to Logseq format')
    parser.add_argument('--input', '-i', required=True, help='Input file or directory')
    parser.add_argument('--output', '-o', help='Output file or directory')
    parser.add_argument('--tag', '-t', help='Optional tag to add to each line')
    parser.add_argument('--recursive', '-r', action='store_true', help='Process directory recursively')
    
    args = parser.parse_args()
    
    if os.path.isdir(args.input):
        if args.recursive:
            convert_directory(args.input, args.output, args.tag)
        else:
            print("Use --recursive flag to process directories")
    else:
        convert_to_logseq(args.input, args.output, args.tag)


if __name__ == "__main__":
    main() 