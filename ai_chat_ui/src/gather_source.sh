#!/usr/bin/env python3
"""
Gather all source code files into a single src.txt file.
"""

import os
from pathlib import Path

# Define which files to include
SOURCE_EXTENSIONS = {'.py', '.toml', '.txt', '.md'}
EXCLUDE_DIRS = {'__pycache__', '.egg-info', 'ai_chat_ui.egg-info', '.git', 'venv', 'env'}
EXCLUDE_FILES = {'.pyc', '.pyo', '.pyd'}

def should_include_file(file_path):
    """Check if a file should be included in the output."""
    # Check file extension
    if file_path.suffix not in SOURCE_EXTENSIONS:
        return False
    
    # Check if it's in an excluded directory
    for parent in file_path.parents:
        if parent.name in EXCLUDE_DIRS:
            return False
    
    # Check excluded file patterns
    for pattern in EXCLUDE_FILES:
        if file_path.name.endswith(pattern):
            return False
    
    return True

def gather_source_code(root_dir='.', output_file='src.txt'):
    """Gather all source code files into a single output file."""
    root_path = Path(root_dir)
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("=" * 80 + "\n")
        out.write("SOURCE CODE COMPILATION\n")
        out.write("=" * 80 + "\n\n")
        
        # Collect all files first to sort them
        files_to_process = []
        for file_path in sorted(root_path.rglob('*')):
            if file_path.is_file() and should_include_file(file_path):
                files_to_process.append(file_path)
        
        # Process each file
        for file_path in files_to_process:
            relative_path = file_path.relative_to(root_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Write file header
                out.write("\n" + "=" * 80 + "\n")
                out.write(f"FILE: {relative_path}\n")
                out.write("=" * 80 + "\n")
                out.write(content)
                out.write("\n\n")
                
                print(f"✓ Added: {relative_path}")
                
            except Exception as e:
                print(f"✗ Error reading {relative_path}: {e}")
    
    print(f"\n✓ Source code compiled to: {output_file}")

if __name__ == "__main__":
    gather_source_code()
