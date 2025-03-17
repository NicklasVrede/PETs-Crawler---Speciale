import os
import json
import csv
import tempfile
import shutil

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

def create_temp_profile_copy(original_profile_dir, verbose=False, domain=None):
    """
    Creates a temporary copy of a browser profile for parallel execution
    
    Args:
        original_profile_dir: Path to the original profile directory
        verbose: Whether to print status messages
        domain: Optional domain name to include in the temp directory name
        
    Returns:
        Path to the temporary profile directory
    """
    # Create a base directory for all temporary profiles
    temp_base_dir = os.path.join("data", "temp_profiles")
    os.makedirs(temp_base_dir, exist_ok=True)
    
    # Extract profile name from path for the temp directory prefix
    profile_name = os.path.basename(original_profile_dir)
    
    # Use domain in the directory name if provided
    domain_part = f"_{domain.replace('.', '_')}" if domain else ""
    temp_dir_name = f"temp_profile{domain_part}"
    
    # Create full path for the temporary directory
    temp_profile_dir = os.path.join(temp_base_dir, temp_dir_name)
    
    # Remove existing directory if it exists
    if os.path.exists(temp_profile_dir):
        if verbose:
            print(f"Removing existing temporary profile directory: {temp_profile_dir}")
        shutil.rmtree(temp_profile_dir, ignore_errors=True)
    
    if verbose:
        print(f"Creating temporary profile directory: {temp_profile_dir}")
    
    try:
        # Copy the original profile to the temporary directory if it exists
        if os.path.exists(original_profile_dir):
            # Only copy if the source directory has content
            if os.listdir(original_profile_dir):
                if verbose:
                    print(f"Copying profile from {original_profile_dir} to {temp_profile_dir}")
                shutil.copytree(original_profile_dir, temp_profile_dir, dirs_exist_ok=True)
            else:
                if verbose:
                    print(f"Source profile directory {original_profile_dir} is empty, creating empty temp directory")
                os.makedirs(temp_profile_dir, exist_ok=True)
        else:
            if verbose:
                print(f"Source profile directory {original_profile_dir} does not exist, creating empty temp directory")
            os.makedirs(temp_profile_dir, exist_ok=True)
        
        return temp_profile_dir
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_profile_dir):
            shutil.rmtree(temp_profile_dir, ignore_errors=True)
        raise Exception(f"Failed to create temporary profile copy: {str(e)}") 