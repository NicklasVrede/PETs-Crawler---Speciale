import json
import subprocess
from typing import Dict
import urllib.parse

class GhosteryManager:
    def analyze_request(self, url: str) -> Dict:
        """Analyze a request URL for tracking behavior using Ghostery CLI"""
        try:
            # Clean the URL to avoid command line parsing issues
            cleaned_url = urllib.parse.quote(url, safe=':/?=&')
            
            result = subprocess.run(
                ['npx', '@ghostery/trackerdb', cleaned_url],
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
                shell=True    # This helps find npx in the environment
            )
            
            # Parse the JSON output if available
            if result.stdout and '{' in result.stdout:
                # Extract the JSON part from the output
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
                        'pattern_name': None
                    }
                
                # Get the first match (most relevant)
                match = data['matches'][0]
                
                return {
                    'is_tracker': True,
                    'pattern_name': match['pattern']['name'],
                    'category': match['category']['name'],
                    'organization': match['organization']['name'],
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
                'pattern_name': None
            }
            
        except Exception:
            # Silently handle any errors and return not a tracker
            return {
                'is_tracker': False,
                'category': None,
                'organization': None,
                'pattern_name': None
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