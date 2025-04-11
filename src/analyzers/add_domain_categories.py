import os
import json
import sys
import re
from pathlib import Path
from tqdm import tqdm

def load_json(file_path):
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def save_json(data, file_path):
    """Save JSON file with error handling"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
        return False

def add_categories_to_files(data_directory, categories_file="data/db+ref/domain_categories.json", verbose=False):
    """Add domain categories to JSON files in the specified directory"""
    # Time the operation if verbose
    start_time = 0
    if verbose:
        import time
        start_time = time.time()
    
    # Load domain categories
    try:
        with open(categories_file, 'r', encoding='utf-8') as f:
            categories = json.load(f)
    except Exception as e:
        print(f"Error loading categories from {categories_file}: {e}")
        return
    
    if verbose:
        print(f"Loaded categories for {len(categories)} domains")
    
    # Find all JSON files in the directory (recursively)
    json_files = list(Path(data_directory).glob("**/*.json"))
    if verbose:
        print(f"Found {len(json_files)} JSON files to process")
    
    # Regex to extract domain from the first few lines
    domain_pattern = re.compile(r'"domain"\s*:\s*"([^"]+)"')
    
    # Process each file
    modified_count = 0
    for json_path in tqdm(json_files, desc="Adding domain categories"):
        # Quick check - read just the first few lines to check if processing is needed
        domain = None
        needs_processing = False
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                # Read first 10 lines or until we find both domain and categories
                header = ""
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    header += line
                    
                # Check if it already has categories (skip if it does)
                if '"categories":' in header:
                    continue
                    
                # Check if it has domain field
                domain_match = domain_pattern.search(header)
                if domain_match:
                    domain = domain_match.group(1)
                    # Only process if we have categories for this domain
                    if domain in categories:
                        needs_processing = True
        except Exception as e:
            if verbose:
                print(f"Error checking {json_path}: {e}")
            continue
                
        # Skip if no domain or we don't need to process
        if not domain or not needs_processing:
            continue
            
        # Now we know we need to process this file, load and modify it
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Insert categories right after domain
            modified = content.replace(
                f'"domain": "{domain}"', 
                f'"domain": "{domain}",\n  "categories": {json.dumps(categories[domain])}'
            )
            
            # Save modified content
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write(modified)
                
            modified_count += 1
        except Exception as e:
            if verbose:
                print(f"Error processing {json_path}: {e}")
    
    if verbose:
        end_time = time.time()
        print(f"Added domain categories to {modified_count} files in {end_time-start_time:.2f} seconds")

if __name__ == "__main__":
    # Check if data directory is provided as an argument
    if len(sys.argv) > 1:
        data_directory = sys.argv[1]
    else:
        data_directory = "data/crawler_data/consent_o_matic_opt_in"
    
    # Validate directory exists
    if not os.path.exists(data_directory):
        print(f"Error: Directory not found: {data_directory}")
        print("Please ensure the data directory exists before running the script.")
        sys.exit(1)
    
    # Load custom categories file if provided
    if len(sys.argv) > 2:
        categories_file = sys.argv[2]
    else:
        categories_file = "data/domain_categories.json"
    
    add_categories_to_files(data_directory, categories_file, verbose=True) 