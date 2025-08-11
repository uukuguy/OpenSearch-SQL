#!/usr/bin/env python3
"""
Script to fix logger syntax errors caused by migration.
"""
import re
from pathlib import Path

def fix_file_syntax(file_path: Path):
    """Fix logger syntax errors in a single file."""
    content = file_path.read_text(encoding='utf-8')
    
    # Pattern: @decorator\nlogger = get_logger(__name__)\ndef function_name
    pattern = r'(@[^\n]+\n)logger = get_logger\(__name__\)\n(def\s+\w+)'
    
    if re.search(pattern, content):
        print(f"Fixing: {file_path}")
        # Move logger before decorator
        content = re.sub(
            pattern,
            r'logger = get_logger(__name__)\n\n\1\2',
            content
        )
        file_path.write_text(content, encoding='utf-8')
        return True
    return False

def main():
    """Main function."""
    src_dir = Path('src_optimized')
    fixed_count = 0
    
    # Find all Python files
    for py_file in src_dir.rglob('*.py'):
        if fix_file_syntax(py_file):
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} files.")

if __name__ == '__main__':
    main()