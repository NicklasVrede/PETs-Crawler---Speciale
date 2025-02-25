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

def check_organization_consistency(main_site: str, request_domain: str) -> bool:
    """Check if both domains belong to the same organization"""
    result_main = analyze_request(main_site)
    result_request = analyze_request(request_domain)
    
    # Extract organization names
    organization_main = result_main['matches'][0]['organization']['name'] if result_main.get('matches') else None
    organization_request = result_request['matches'][0]['organization']['name'] if result_request.get('matches') else None
    
    # Print organization names
    print(f"Organization for {main_site}: {organization_main}")
    print(f"Organization for {request_domain}: {organization_request}")
    
    # Check for consistency
    if organization_main and organization_request:
        return organization_main == organization_request
    return False

# Example usage
if __name__ == "__main__":
    main_site = "https://www.amazon.co.uk"
    request_domain = "https://images-eu.ssl-images-amazon.com"
    is_consistent = check_organization_consistency(main_site, request_domain)
    print(f"Organization Consistency: {is_consistent}")