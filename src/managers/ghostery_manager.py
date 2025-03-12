import json
import subprocess
import os
import pickle
from typing import Dict
from urllib.parse import urlparse
import time
from tqdm import tqdm

# Define cache file path
GHOSTERY_CACHE_FILE = 'data/ghostery_cache.pickle'
ghostery_cache = {}

def load_ghostery_cache():
    """Load Ghostery results cache from file"""
    global ghostery_cache
    try:
        if os.path.exists(GHOSTERY_CACHE_FILE):
            with open(GHOSTERY_CACHE_FILE, 'rb') as f:
                ghostery_cache.update(pickle.load(f))
                tqdm.write(f"Loaded {len(ghostery_cache)} Ghostery cache entries")
    except Exception as e:
        tqdm.write(f"Error loading Ghostery cache: {e}")

def save_ghostery_cache():
    """Save Ghostery results cache to file"""
    try:
        if ghostery_cache:
            os.makedirs(os.path.dirname(GHOSTERY_CACHE_FILE), exist_ok=True)
            with open(GHOSTERY_CACHE_FILE, 'wb') as f:
                pickle.dump(ghostery_cache, f)
            tqdm.write(f"Saved {len(ghostery_cache)} Ghostery cache entries")
    except Exception as e:
        tqdm.write(f"Error saving Ghostery cache: {e}")

def analyze_request(url: str) -> Dict:
    """Return the full output from the Ghostery database for a given URL"""
    try:
        # Extract just the scheme and hostname
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Check cache first
        if base_url in ghostery_cache:
            return ghostery_cache[base_url]
        
        result = subprocess.run(
            ['npx', '@ghostery/trackerdb', base_url],
            capture_output=True,
            text=True,
            check=False,
            shell=True
        )
        
        # Parse the JSON output
        if result.stdout and '{' in result.stdout:
            json_start = result.stdout.find('{')
            json_end = result.stdout.rfind('}') + 1
            json_str = result.stdout[json_start:json_end]
            
            data = json.loads(json_str)
            
            # Cache the result
            ghostery_cache[base_url] = data
            
            # Return the full data
            return data
        
        # Cache empty results too to avoid re-checking
        ghostery_cache[base_url] = {}
        return {}
        
    except Exception as e:
        print(f"Error analyzing {url}: {e}")
        return {}

# Load cache at module import
load_ghostery_cache()

# Register save function for exit
import atexit
atexit.register(save_ghostery_cache)

# Example usage
if __name__ == "__main__":
    test_urls = [
        "https://dnklry.plushbeds.com",
        "https://dnsdelegation.io",
        "https://gum.criteo.com",
        "https://gum.fr3.vip.prod.criteo.com"
    ]
    
    for url in test_urls:
        print(f"\nAnalyzing: {url}")
        print("-" * 50)
        result = analyze_request(url)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("No tracking information found")
        print("-" * 50)
    