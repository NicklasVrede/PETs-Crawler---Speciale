import os
import json
import sys
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
    # Load domain categories
    categories = load_json(categories_file)
    if not categories:
        print(f"Error: Could not load categories from {categories_file}")
        return
    
    if verbose:
        tqdm.write(f"Loaded categories for {len(categories)} domains")
    
    # Find all JSON files in the directory (recursively)
    json_files = list(Path(data_directory).glob("**/*.json"))
    if verbose:
        tqdm.write(f"Found {len(json_files)} JSON files to process")
    
    # Process each file
    modified_count = 0
    for json_path in tqdm(json_files, desc="Processing files"):
        # Load the file
        data = load_json(json_path)
        if not data:
            continue
        
        # Skip files that don't have a domain field
        if "domain" not in data:
            continue
        
        domain = data["domain"]
        
        # Check if we have categories for this domain
        if domain in categories:
            # Create a new dictionary with domain and categories at the beginning
            new_data = {}
            for key in data:
                new_data[key] = data[key]
                # Insert categories right after domain
                if key == "domain":
                    new_data["categories"] = categories[domain]
            
            # Only save if we made changes and don't already have categories
            if "categories" not in data:
                # Save the modified file
                if save_json(new_data, json_path):
                    modified_count += 1
    
    #tqdm.write(f"Added domain categories to {modified_count} files")

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
    
    add_categories_to_files(data_directory, categories_file) 