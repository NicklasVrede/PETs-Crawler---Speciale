import os
import json
import csv
import tempfile
import shutil
import time

def load_config(config_file):
    """Load configuration from a JSON file."""
    with open(config_file, 'r') as f:
        return json.load(f)

def get_profile_config(config, setup):
    """Extract profile configuration."""
    profiles = config.get('profiles', {})
    return profiles.get(setup, {})

def construct_paths(config, setup):
    """Construct user data and extension paths from config."""
    profile_config = get_profile_config(config, setup)
    
    base_path = config.get('base_path', '')
    profile_path = profile_config.get('profile_path', '')
    extension_path = profile_config.get('extension_path', '')
    
    user_data_dir = os.path.join(base_path, profile_path)
    full_extension_path = os.path.join(user_data_dir, extension_path)
    
    return user_data_dir, full_extension_path

def extract_javascript(json_file_path):
    """Extract JavaScript from responses and add to dedicated scripts section."""
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    if 'scripts' not in data:
        data['scripts'] = []
    
    for page_data in data['pages'].values():
        for request in page_data.get('requests', []):
            if (request.get('resource_type') == 'script' and 
                'response' in request and 
                'body' in request['response'] and
                'content-type' in request['response']['headers'] and
                'javascript' in request['response']['headers']['content-type'].lower()):
                
                script_data = {
                    'url': request['url'],
                    'page_url': request.get('page_url', 'unknown'),
                    'timestamp': request.get('timestamp', 'unknown'),
                    'content': request['response']['body']
                }
                
                data['scripts'].append(script_data)
    
    with open(json_file_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nExtracted {len(data['scripts'])} JavaScript files")

def get_all_sites(csv_path='data/study-sites.csv'):
    """Get all sites from the CSV file as a list of (rank, domain) tuples"""
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        return list(reader)


def create_temp_profile_copy(original_profile_dir, extension_path, domain=None):
    """
    Creates a minimal copy of a browser profile with just extension data
    
    Args:
        original_profile_dir: Path to the original profile directory
        extension_path: Path to the extension
        domain: Optional domain name for naming
        
    Returns:
        Path to the temporary profile directory
    """
    # Use a static directory for all temporary profiles
    temp_base_dir = os.path.join("data", "temp_profiles")
    os.makedirs(temp_base_dir, exist_ok=True)
    
    # Create a unique name for this profile
    domain_part = f"_{domain.replace('.', '_')}" if domain else ""
    timestamp = int(time.time())
    temp_dir_name = f"profile{domain_part}_{timestamp}"
    
    # Full path to the new temp profile
    temp_profile_dir = os.path.join(temp_base_dir, temp_dir_name)
    
    # Create the directory structure
    os.makedirs(temp_profile_dir, exist_ok=True)
    
    # Create extensions directory
    ext_dir = os.path.join(temp_profile_dir, "Extensions")
    os.makedirs(ext_dir, exist_ok=True)
    
    # Copy the extension if specified
    if extension_path and os.path.exists(extension_path):
        extension_name = os.path.basename(extension_path)
        target_ext_path = os.path.join(ext_dir, extension_name)
        
        # Copy extension files
        if os.path.isdir(extension_path):
            shutil.copytree(extension_path, target_ext_path)
        else:
            shutil.copy2(extension_path, target_ext_path)
    
    return temp_profile_dir 