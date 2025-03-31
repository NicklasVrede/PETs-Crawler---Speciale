import os
import argparse
from collections import defaultdict
import re

def explore_project(root_dir='.', ignore_dirs=None, ignore_extensions=None, max_files_per_dir=5):
    """
    Explores and prints the structure of the project with focus on Python files.
    
    Args:
        root_dir: The root directory to start exploration from
        ignore_dirs: List of directory names to ignore
        ignore_extensions: List of file extensions to ignore
        max_files_per_dir: Maximum number of non-Python files to show per directory
    """
    if ignore_dirs is None:
        ignore_dirs = ['.git', '__pycache__', 'venv', 'env', '.venv', '.env', 'node_modules']
    
    if ignore_extensions is None:
        ignore_extensions = ['.pyc', '.pyo', '.pyd', '.so', '.dll']
    
    # Statistics
    file_types = defaultdict(int)
    dir_file_counts = defaultdict(int)
    python_files = []
    all_dirs = []
    
    print(f"\n📂 PROJECT STRUCTURE: {os.path.abspath(root_dir)}\n")
    
    # First walk to gather all Python files
    for root, dirs, files in os.walk(root_dir):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        rel_path = os.path.relpath(root, root_dir)
        if rel_path != '.':
            all_dirs.append(rel_path)
        
        for file in files:
            if file.endswith('.py'):
                full_path = os.path.join(rel_path, file)
                python_files.append(full_path)
                
            # Count file by extension
            _, ext = os.path.splitext(file)
            if not any(file.endswith(ext) for ext in ignore_extensions):
                file_types[ext if ext else '(no extension)'] += 1
                dir_file_counts[rel_path] += 1
    
    # Display directory structure
    for root, dirs, files in os.walk(root_dir):
        # Skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        # Calculate relative path depth for indentation
        rel_path = os.path.relpath(root, root_dir)
        depth = 0 if rel_path == '.' else rel_path.count(os.sep) + 1
        indent = '  ' * depth
        
        # Print directory name
        if depth > 0:  # Skip the root directory name
            dir_name = os.path.basename(root)
            print(f"{indent}📂 {dir_name}/")
        
        # Process files
        py_files = [f for f in files if f.endswith('.py')]
        other_files = [f for f in files if not f.endswith('.py') and 
                      not any(f.endswith(ext) for ext in ignore_extensions)]
        
        # Always show all Python files
        for file in sorted(py_files):
            print(f"{indent}  🐍 {file}")
            
        # Show limited other files
        for file in sorted(other_files)[:max_files_per_dir]:
            print(f"{indent}  📄 {file}")
            
        # Show ellipsis if other files were hidden
        if len(other_files) > max_files_per_dir:
            print(f"{indent}  ... ({len(other_files) - max_files_per_dir} more non-Python files)")
    
    # Print statistics
    print("\n📊 PROJECT STATISTICS:")
    print(f"Total directories: {len(all_dirs)}")
    print(f"Total Python files: {len(python_files)}")
    
    print("\nPython files by directory:")
    dir_py_counts = defaultdict(int)
    for py_file in python_files:
        dir_path = os.path.dirname(py_file)
        dir_py_counts[dir_path] += 1
    
    for dir_path, count in sorted(dir_py_counts.items(), key=lambda x: x[1], reverse=True):
        if dir_path == '':
            dir_path = '(root)'
        print(f"  {dir_path}: {count} Python files")
    
    print("\nFile types:")
    for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {ext}: {count}")
    
    print("\nAll Python Files (alphabetical):")
    for py_file in sorted(python_files):
        print(f"  {py_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Explore project structure with focus on Python files")
    parser.add_argument("--root", default=".", help="Root directory to start exploration")
    parser.add_argument("--include-all", action="store_true", help="Include all directories in output")
    parser.add_argument("--max-files", type=int, default=3, help="Maximum non-Python files to display per directory")
    args = parser.parse_args()
    
    ignore_dirs = ['.git', '__pycache__', 'venv', 'env', '.venv', '.env', 'node_modules']
    if not args.include_all:
        # Add common data directories to ignore list
        ignore_dirs.extend(['data', 'results', 'logs', 'output'])
    
    explore_project(root_dir=args.root, ignore_dirs=ignore_dirs, max_files_per_dir=args.max_files) 