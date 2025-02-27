import requests
import os
from datetime import datetime

def update_cname_trackers():
    """
    Downloads the latest CNAME trackers list from AdGuard's GitHub repository
    for testing purposes.
    """
    URL = "https://raw.githubusercontent.com/AdguardTeam/cname-trackers/master/data/combined_disguised_trackers.txt"
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_data")
    
    try:
        # Create test_data directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Download the file
        response = requests.get(URL)
        response.raise_for_status()
        
        # Save as test data
        filepath = os.path.join(OUTPUT_DIR, "cname_trackers.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(response.text)
            
        print(f"Successfully downloaded trackers list to {filepath}")
        return True
        
    except requests.RequestException as e:
        print(f"Error downloading trackers list: {e}")
        return False
    except IOError as e:
        print(f"Error saving trackers list: {e}")
        return False

if __name__ == "__main__":
    update_cname_trackers() 