import json
import os
import requests
from typing import Dict, Optional, Set
from urllib.parse import urlparse
import fnmatch

class GhosteryManager:
    def __init__(self):
        self.db_dir = os.path.join('data', 'databases', 'ghostery')
        self.patterns = {}
        self.categories = {}
        self.organizations = {}
        self._ensure_database()
        self._load_database()

    def _ensure_database(self):
        """Download and ensure Ghostery database files exist"""
        os.makedirs(self.db_dir, exist_ok=True)
        
        # Correct file mappings from Ghostery's GitHub repo
        files = {
            'patterns.json': 'patterns/patterns.json',
            'categories.json': 'categories.json',
            'organizations.json': 'organizations.json'
        }
        
        base_url = "https://raw.githubusercontent.com/ghostery/trackerdb/main/db"
        
        for local_file, remote_path in files.items():
            local_path = os.path.join(self.db_dir, local_file)
            if not os.path.exists(local_path):
                print(f"Downloading {local_file}...")
                try:
                    response = requests.get(f"{base_url}/{remote_path}")
                    response.raise_for_status()  # Raise an error for bad status codes
                    
                    # For patterns, we need to combine all pattern files
                    if local_file == 'patterns.json':
                        # Get the directory listing first
                        patterns = []
                        pattern_files = [
                            'advertising.eno',
                            'audio_video_player.eno',
                            'comments.eno',
                            'consent.eno',
                            'customer_interaction.eno',
                            'essential.eno',
                            'pornvertising.eno',
                            'site_analytics.eno',
                            'social_media.eno',
                            'misc.eno'
                        ]
                        
                        for pattern_file in pattern_files:
                            pattern_url = f"{base_url}/patterns/{pattern_file}"
                            try:
                                pattern_response = requests.get(pattern_url)
                                pattern_response.raise_for_status()
                                patterns.extend(self._parse_eno(pattern_response.text))
                            except Exception as e:
                                print(f"Error downloading pattern file {pattern_file}: {str(e)}")
                        
                        # Save combined patterns
                        with open(local_path, 'w', encoding='utf-8') as f:
                            json.dump(patterns, f, indent=2)
                    else:
                        with open(local_path, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                    print(f"Downloaded {local_file}")
                except Exception as e:
                    print(f"Failed to download {local_file}: {str(e)}")

    def _parse_eno(self, content: str) -> list:
        """Parse .eno file format into JSON-like structure"""
        patterns = []
        current_pattern = {}
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if not line.startswith(' '):  # New pattern
                if current_pattern:
                    patterns.append(current_pattern)
                current_pattern = {'name': line}
            else:  # Pattern attribute
                try:
                    key, value = line.strip().split(':', 1)
                    current_pattern[key.strip()] = value.strip()
                except ValueError:
                    continue
        
        if current_pattern:
            patterns.append(current_pattern)
            
        return patterns

    def _load_database(self):
        """Load Ghostery database files"""
        try:
            # Load patterns
            with open(os.path.join(self.db_dir, 'patterns.json'), 'r', encoding='utf-8') as f:
                self.patterns = json.load(f)
            
            # Load categories
            with open(os.path.join(self.db_dir, 'categories.json'), 'r', encoding='utf-8') as f:
                self.categories = json.load(f)
            
            # Load organizations
            with open(os.path.join(self.db_dir, 'organizations.json'), 'r', encoding='utf-8') as f:
                self.organizations = json.load(f)
                
            print(f"Loaded {len(self.patterns)} patterns, {len(self.categories)} categories, "
                  f"and {len(self.organizations)} organizations")
                
        except Exception as e:
            print(f"Error loading Ghostery database: {str(e)}")

    def _match_pattern(self, url: str, pattern: Dict) -> bool:
        """Match URL against a pattern's filters"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Check domains first
            if 'domains' in pattern:
                if not any(domain.endswith(d) for d in pattern['domains']):
                    return False
            
            # Check filters if they exist
            if 'filters' in pattern:
                for filter_rule in pattern['filters']:
                    # Basic filter matching (can be expanded for more complex rules)
                    if filter_rule.startswith('||'):
                        if domain.endswith(filter_rule[2:].split('^')[0]):
                            return True
                    elif filter_rule.startswith('|'):
                        if url.startswith(filter_rule[1:]):
                            return True
                    else:
                        if fnmatch.fnmatch(url, filter_rule):
                            return True
            
            return False
            
        except Exception as e:
            print(f"Error matching pattern: {str(e)}")
            return False

    def analyze_request(self, url: str) -> Dict:
        """Analyze a request URL for tracking behavior"""
        try:
            tracking_info = {
                'is_tracker': False,
                'category': None,
                'organization': None,
                'pattern_name': None
            }
            
            # Check each pattern
            for pattern in self.patterns:
                if self._match_pattern(url, pattern):
                    tracking_info.update({
                        'is_tracker': True,
                        'pattern_name': pattern.get('name'),
                        'category': self.categories.get(pattern.get('category', ''), {}).get('name'),
                        'organization': self.organizations.get(pattern.get('organization', ''), {}).get('name')
                    })
                    break
            
            return tracking_info
            
        except Exception as e:
            print(f"Error analyzing URL {url}: {str(e)}")
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