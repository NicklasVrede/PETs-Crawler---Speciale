import json
import subprocess
from typing import Dict
from urllib.parse import urlparse

def analyze_request(url: str) -> Dict:
    """Return the full output from the Ghostery database for a given URL"""
    try:
        # Extract just the scheme and hostname
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
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
            
            # Return the full data
            return data
        
        return {}
        
    except Exception as e:
        print(f"Error analyzing {url}: {e}")
        return {}


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
    