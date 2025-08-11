#!/usr/bin/env python3
"""
Script to migrate from standard logging to loguru in src_optimized directory.
"""
import os
import re
from pathlib import Path

def migrate_file_to_loguru(file_path: Path):
    """Migrate a single Python file to use loguru."""
    if not file_path.suffix == '.py':
        return False
    
    # Skip if already contains loguru imports
    content = file_path.read_text(encoding='utf-8')
    if 'loguru' in content:
        return False
    
    # Skip if no logging usage
    if 'import logging' not in content and 'logging.' not in content:
        return False
    
    print(f"Migrating: {file_path}")
    
    # Replace imports
    content = re.sub(
        r'import logging\n',
        'from ..utils.loguru_config import get_logger\n',
        content
    )
    
    content = re.sub(
        r'from typing import (.+)\nimport logging\n',
        r'from typing import \1\nfrom ..utils.loguru_config import get_logger\n',
        content
    )
    
    # Replace logger initialization patterns
    content = re.sub(
        r'logger = logging\.getLogger\(__name__\)',
        'logger = get_logger(__name__)',
        content
    )
    
    content = re.sub(
        r'logging\.getLogger\(__name__\)',
        'get_logger(__name__)',
        content
    )
    
    content = re.sub(
        r'self\.logger = logging\.getLogger\(__name__\)',
        'self.logger = get_logger(__name__)',
        content
    )
    
    # Replace logging.basicConfig calls
    content = re.sub(
        r'logging\.basicConfig\([^)]*\)',
        '# Logging configured via loguru',
        content
    )
    
    # Replace direct logging calls
    content = re.sub(r'logging\.info\(', 'logger.info(', content)
    content = re.sub(r'logging\.error\(', 'logger.error(', content) 
    content = re.sub(r'logging\.warning\(', 'logger.warning(', content)
    content = re.sub(r'logging\.debug\(', 'logger.debug(', content)
    content = re.sub(r'logging\.critical\(', 'logger.critical(', content)
    
    # Replace logging level constants
    content = re.sub(r'logging\.INFO', '"INFO"', content)
    content = re.sub(r'logging\.ERROR', '"ERROR"', content)
    content = re.sub(r'logging\.WARNING', '"WARNING"', content)
    content = re.sub(r'logging\.DEBUG', '"DEBUG"', content)
    
    # If we need a logger and don't have one defined, add it
    if 'logger.' in content and 'logger = get_logger' not in content:
        # Find the first class or function definition and add logger before it
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('class ') or line.strip().startswith('def '):
                lines.insert(i, 'logger = get_logger(__name__)')
                break
        content = '\n'.join(lines)
    
    # Write back the modified content
    file_path.write_text(content, encoding='utf-8')
    return True

def main():
    """Main migration function."""
    src_dir = Path('src_optimized')
    if not src_dir.exists():
        print("src_optimized directory not found")
        return
    
    migrated_count = 0
    
    # Find all Python files
    for py_file in src_dir.rglob('*.py'):
        if py_file.name in ['__init__.py', 'loguru_config.py']:
            continue  # Skip these files
            
        if migrate_file_to_loguru(py_file):
            migrated_count += 1
    
    print(f"\nMigration complete! Migrated {migrated_count} files to loguru.")

if __name__ == '__main__':
    main()