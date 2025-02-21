import json
import subprocess
from typing import Dict
from urllib.parse import urlparse

class GhosteryManager:
    def analyze_request(self, url: str) -> Dict:
        """Analyze a request URL for tracking behavior using Ghostery CLI"""
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
                
                # If no matches found
                if not data.get('matches'):
                    return {
                        'is_tracker': False,
                        'category': None,
                        'organization': None,
                        'pattern_name': None,
                        'fingerprinting': False
                    }
                
                # Get the first match (most relevant)
                match = data['matches'][0]
                
                return {
                    'is_tracker': True,
                    'pattern_name': match['pattern']['name'],
                    'category': match['category']['name'],
                    'organization': match['organization']['name'],
                    'fingerprinting': match.get('fingerprinting', False),  # Add fingerprinting check
                    'details': {
                        'category_description': match['category']['description'],
                        'organization_description': match['organization']['description'],
                        'organization_privacy_contact': match['organization'].get('privacy_contact'),
                        'organization_privacy_policy': match['organization'].get('privacy_policy_url'),
                        'pattern_website': match['pattern'].get('website_url')
                    }
                }
            
            return {
                'is_tracker': False,
                'category': None,
                'organization': None,
                'pattern_name': None,
                'fingerprinting': False
            }
            
        except Exception as e:
            return {
                'is_tracker': False,
                'category': None,
                'organization': None,
                'pattern_name': None,
                'fingerprinting': False
            }

    def get_statistics(self) -> Dict:
        """Get statistics about tracked URLs"""
        stats = {
            'total_tracked': 0,
            'categories': {},
            'organizations': {}
        }
        
        # Statistics will be populated by NetworkMonitor
        return stats 