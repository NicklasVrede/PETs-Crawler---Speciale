import requests
import os
from datetime import datetime, timedelta
import logging

def update_public_suffix_list(force_update=False):
    """Download or update the Public Suffix List.
    
    Args:
        force_update (bool): If True, download new list regardless of cache age
        
    Returns:
        set: Set of public suffixes
    """
    cache_file = "data/public_suffix_list.dat"
    cache_max_age = timedelta(days=7)  # Update weekly
    
    try:
        # Check if we have a recent cached version
        if not force_update and os.path.exists(cache_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - mtime < cache_max_age:
                #print("Using cached Public Suffix List")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return set(line.strip() for line in f 
                             if line.strip() and not line.startswith('//'))
        
        # Download fresh copy
        print("Downloading fresh Public Suffix List...")
        url = "https://publicsuffix.org/list/public_suffix_list.dat"
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = 'utf-8'  # Ensure response is treated as UTF-8
        
        # Parse and cache the list
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        suffixes = set()
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            for line in response.text.splitlines():
                f.write(line + '\n')
                if line.strip() and not line.startswith('//'):
                    suffixes.add(line.strip())
        
        print(f"Downloaded {len(suffixes)} public suffixes")
        return suffixes
        
    except requests.RequestException as e:
        print(f"Error downloading Public Suffix List: {e}")
        # If we have a cached version, use it as fallback
        if os.path.exists(cache_file):
            print("Using cached version as fallback")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f 
                         if line.strip() and not line.startswith('//'))
        raise
    except Exception as e:
        print(f"Unexpected error managing Public Suffix List: {e}")
        raise

if __name__ == "__main__":
    # Can be run directly to update the list
    print("Updating Public Suffix List...")
    suffixes = update_public_suffix_list(force_update=True)
    print(f"Public Suffix List updated with {len(suffixes)} entries") 