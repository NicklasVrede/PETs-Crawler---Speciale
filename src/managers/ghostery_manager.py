import json
import subprocess
from typing import Dict

class GhosteryManager:
    def analyze_request(self, url: str) -> Dict:
        """Analyze a request URL for tracking behavior using Ghostery CLI"""
        try:
            result = subprocess.run(
                ['npx', '@ghostery/trackerdb', url],
                capture_output=True,
                text=True,
                check=True,
                shell=True  # This helps find npx in the environment
            )
            
            # Parse the JSON output
            data = json.loads(result.stdout)
            
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
            
        except subprocess.CalledProcessError as e:
            print(f"Error running npx command: {str(e)}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
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