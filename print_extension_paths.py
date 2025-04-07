import json

def print_full_extension_paths():
    # Load the config file
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Get the base path
    base_path = config.get('base_path', '')
    
    # Iterate through profiles and print full extension paths
    for profile_name, profile_data in config['profiles'].items():
        ext_path = profile_data.get('extension_path', '')
        
        if ext_path:
            # Construct full path
            full_path = f"{base_path}\\{profile_data['profile_path']}\\{ext_path}"
            print(f"{profile_name}: {full_path}")
            print(f"{'='*50}")
        else:
            print(f"{profile_name}: No extension")

if __name__ == "__main__":
    print_full_extension_paths() 