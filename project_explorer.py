import os
import argparse
from collections import defaultdict

def explore_project(root_dir='.', ignore_dirs=None, ignore_extensions=None):
    """
    Explores and prints the structure of the project.
    
    Args:
        root_dir: The root directory to start exploration from
        ignore_dirs: List of directory names to ignore
        ignore_extensions: List of file extensions to ignore
    """
    if ignore_dirs is None:
        ignore_dirs = ['.git', '__pycache__', 'venv', 'env', '.venv', '.env', 'node_modules']
    
    if ignore_extensions is None:
        ignore_extensions = ['.pyc', '.pyo', '.pyd', '.so', '.dll']
    
    # Statistics
    file_types = defaultdict(int)
    dir_file_counts = defaultdict(int)
    
    print(f"\n📂 PROJECT STRUCTURE: {os.path.abspath(root_dir)}\n")
    
    # Walk through directory
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
        for file in sorted(files):
            # Skip ignored extensions
            if any(file.endswith(ext) for ext in ignore_extensions):
                continue
                
            # Count file by extension
            _, ext = os.path.splitext(file)
            file_types[ext if ext else '(no extension)'] += 1
            dir_file_counts[rel_path] += 1
            
            # Print file
            print(f"{indent}  📄 {file}")
    
    # Print statistics
    print("\n📊 PROJECT STATISTICS:")
    print(f"Total directories: {len(dir_file_counts)}")
    
    print("\nFile types:")
    for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ext}: {count}")
    
    print("\nFiles per directory:")
    for dir_path, count in sorted(dir_file_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        if dir_path == '.':
            dir_path = '(root)'
        print(f"  {dir_path}: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Explore project structure")
    parser.add_argument("--root", default=".", help="Root directory to start exploration")
    args = parser.parse_args()
    
    explore_project(root_dir=args.root) 