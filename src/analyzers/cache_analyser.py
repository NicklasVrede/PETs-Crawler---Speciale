# Inspired by "Towards Understanding First-Party Cookie Tracking in the Field, demir et al 2022"

import re
import json
from typing import Dict, List, Any, Set
import base64
from collections import defaultdict

class CacheAnalyzer:
    """Analyzes web storage mechanisms (localStorage, sessionStorage, etc.) 
    to identify potential tracking identifiers."""
    
    def __init__(self):
        # Regular expressions for pattern matching
        self.uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.I)
        self.base64_pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
        self.hashes = {
            'md5': re.compile(r'^[0-9a-f]{32}$', re.I),
            'sha1': re.compile(r'^[0-9a-f]{40}$', re.I),
            'sha256': re.compile(r'^[0-9a-f]{64}$', re.I),
            'sha512': re.compile(r'^[0-9a-f]{128}$', re.I)
        }
        
        # Keywords suggesting tracking functionality
        self.tracking_keywords = [
            'id', 'user', 'visitor', 'client', 'device', 'machine', 'fingerprint', 'track',
            'analytics', 'session', 'token', 'uuid', 'guid', 'uid', 'fp', 'account',
            'profile', 'customer', 'tracking', 'identify', 'canvas', 'persist', 'unique'
        ]
        
        # Multi-word combinations that strongly indicate tracking
        self.tracking_combinations = [
            'user_id', 'visitor_id', 'device_id', 'tracking_id', 'client_id', 
            'session_id', 'machine_id', 'customer_id', 'analytics_id', 'ad_id',
            'uuid', 'guid', 'fingerprint', 'canvas_fp', 'browser_id', 'installation_id'
        ]
    
    def analyze_storage(self, storage_data: Dict) -> Dict:
        """Analyze web storage data to identify potential tracking identifiers."""
        if not storage_data or 'visits' not in storage_data:
            return {'error': 'No valid storage data provided'}
            
        # Results will store all our findings
        results = {
            'potential_identifiers': [],
            'persistence_analysis': {},
            'identifier_count': 0,
            'scoring': {
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0
            },
            'storage_type_breakdown': {
                'localStorage': 0,
                'sessionStorage': 0,
                'cookieStorage': 0,
                'indexedDB': 0
            }
        }
        
        # Step 1: Identify potential identifiers by their characteristics
        identifiers = self._identify_potential_identifiers(storage_data['visits'])
        results['potential_identifiers'] = identifiers
        results['identifier_count'] = len(identifiers)
        
        # Step 2: Analyze persistence across visits
        if len(storage_data['visits']) > 1:
            results['persistence_analysis'] = self._analyze_persistence(storage_data['visits'])
        
        # Count confidence levels and storage types
        for item in identifiers:
            if item['confidence'] >= 0.8:
                results['scoring']['high_confidence'] += 1
            elif item['confidence'] >= 0.5:
                results['scoring']['medium_confidence'] += 1
            else:
                results['scoring']['low_confidence'] += 1
            
            results['storage_type_breakdown'][item['storage_type']] += 1
            
        return results
    
    def _identify_potential_identifiers(self, visits_data: Dict) -> List[Dict]:
        """Identify potential tracking identifiers in storage data."""
        potential_identifiers = []
        
        # Process all storage types across all visits
        for visit_num, visit_data in visits_data.items():
            # Process localStorage
            for item in visit_data.get('local_storage', []):
                identifier = self._analyze_storage_item(item, 'localStorage', visit_num)
                if identifier:
                    potential_identifiers.append(identifier)
            
            # Process sessionStorage
            for item in visit_data.get('session_storage', []):
                identifier = self._analyze_storage_item(item, 'sessionStorage', visit_num)
                if identifier:
                    potential_identifiers.append(identifier)
                    
            # Process cache storage 
            for cache in visit_data.get('cache_storage', []):
                # Cache storage has a different structure
                cache_identifier = {
                    'storage_type': 'cacheStorage',
                    'key': cache.get('name', ''),
                    'value': f"Cache with {cache.get('entry_count', 0)} entries",
                    'domain': cache.get('domain', ''),
                    'visit': visit_num,
                    'confidence': 0.3,  # Base confidence
                    'reasons': []
                }
                
                # Check if cache name suggests tracking
                if self._key_suggests_tracking(cache.get('name', '')):
                    cache_identifier['confidence'] += 0.3
                    cache_identifier['reasons'].append('Tracking-related cache name')
                
                if cache_identifier['confidence'] > 0.3:
                    potential_identifiers.append(cache_identifier)
        
        return potential_identifiers
    
    def _analyze_storage_item(self, item: Dict, storage_type: str, visit: str) -> Dict:
        """Analyze a single storage item to determine if it's a potential identifier."""
        if not isinstance(item, dict) or 'key' not in item or 'value' not in item:
            return None
            
        key = item['key']
        value = str(item['value'])
        domain = item.get('domain', '')
        
        # Start with base identifier entry
        identifier = {
            'storage_type': storage_type,
            'key': key,
            'value': value[:50] + ('...' if len(value) > 50 else ''),
            'value_full_length': len(value),
            'domain': domain,
            'visit': visit,
            'confidence': 0.0,  # Will be updated based on analysis
            'reasons': []
        }
        
        # Check 1: Key name analysis
        if self._key_suggests_tracking(key):
            identifier['confidence'] += 0.4
            identifier['reasons'].append('Tracking-related key name')
        
        # Check 2: Value format analysis
        format_score, format_reason = self._analyze_value_format(value)
        identifier['confidence'] += format_score
        if format_reason:
            identifier['reasons'].append(format_reason)
        
        # Only include items with sufficient confidence
        if identifier['confidence'] >= 0.3:
            return identifier
        return None
    
    def _key_suggests_tracking(self, key: str) -> bool:
        """Check if the key name suggests it's used for tracking."""
        key_lower = key.lower()
        
        # Direct match with tracking combinations
        for combination in self.tracking_combinations:
            if combination in key_lower:
                return True
        
        # Check for keyword matches
        keyword_count = 0
        for keyword in self.tracking_keywords:
            if keyword in key_lower:
                keyword_count += 1
                
        # If multiple tracking keywords are found, it's likely a tracker
        return keyword_count >= 2
    
    def _analyze_value_format(self, value: str) -> tuple:
        """Analyze the format of a value to determine if it looks like an identifier."""
        # Skip if too short
        if len(value) < 16:
            return 0.0, None
            
        # Check if alphanumeric with both letters and numbers
        has_letters = bool(re.search(r'[a-zA-Z]', value))
        has_numbers = bool(re.search(r'[0-9]', value))
        
        if not (has_letters and has_numbers):
            return 0.0, None
        
        # Check for specific formats
        if self.uuid_pattern.match(value):
            return 0.5, 'UUID format'
            
        if self.base64_pattern.match(value):
            # Additional verification - try to decode and check if it's not garbage
            try:
                decoded = base64.b64decode(value + '=' * (4 - len(value) % 4))
                if not all(32 <= byte <= 126 for byte in decoded):
                    # If it contains a lot of control characters, it's likely binary data
                    pass
            except:
                pass
            return 0.4, 'Base64-encoded format'
        
        # Check hash formats
        for hash_type, pattern in self.hashes.items():
            if pattern.match(value):
                return 0.5, f'{hash_type.upper()} hash format'
        
        # Check for JWT token format
        if re.match(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$', value):
            return 0.5, 'JWT token format'
            
        # Long and complex string, could be an identifier
        if len(value) > 32:
            return 0.2, 'Long complex string'
            
        return 0.1, 'Potential identifier format'
    
    def _analyze_persistence(self, visits_data: Dict) -> Dict:
        """Analyze persistence of storage items across visits."""
        persistence_results = {
            'persistent_items': [],
            'persistence_rate': 0.0
        }
        
        if len(visits_data) < 2:
            return persistence_results
            
        # Get all visits as sorted keys
        visit_keys = sorted([int(k) for k in visits_data.keys()])
        
        # We need at least two visits to analyze persistence
        if len(visit_keys) < 2:
            return persistence_results
            
        # Compare the earliest visit with the latest
        first_visit = str(visit_keys[0])
        last_visit = str(visit_keys[-1])
        
        # Create hash maps of items in first and last visit
        first_items = {}
        
        # Index localStorage items from first visit
        for item in visits_data[first_visit].get('local_storage', []):
            if 'key' in item and 'value' in item:
                item_key = f"localStorage:{item['key']}"
                first_items[item_key] = item['value']
                
        # Index sessionStorage items from first visit
        for item in visits_data[first_visit].get('session_storage', []):
            if 'key' in item and 'value' in item:
                item_key = f"sessionStorage:{item['key']}"
                first_items[item_key] = item['value']
        
        # Compare with last visit to find persistent items
        persistent_count = 0
        total_first_items = len(first_items)
        
        # Check localStorage persistence
        for item in visits_data[last_visit].get('local_storage', []):
            if 'key' in item and 'value' in item:
                item_key = f"localStorage:{item['key']}"
                if item_key in first_items and first_items[item_key] == item['value']:
                    persistent_count += 1
                    persistence_results['persistent_items'].append({
                        'storage_type': 'localStorage',
                        'key': item['key'],
                        'value': item['value'][:50] + ('...' if len(item['value']) > 50 else ''),
                        'domain': item.get('domain', '')
                    })
        
        # Calculate persistence rate
        if total_first_items > 0:
            persistence_results['persistence_rate'] = persistent_count / total_first_items
            
        return persistence_results
    
    def analyze_site(self, site_data: Dict) -> Dict:
        """Analyze all storage mechanisms for a website."""
        if 'storage' not in site_data:
            return {'error': 'No storage data in site data'}
            
        storage_analysis = self.analyze_storage(site_data['storage'])
        
        # Cross-reference with network requests to find third-party sharing
        if 'network_data' in site_data and 'requests' in site_data['network_data']:
            storage_analysis['third_party_sharing'] = self._analyze_third_party_sharing(
                site_data['storage'], 
                site_data['network_data']['requests'],
                site_data.get('domain', '')
            )
            
        return storage_analysis
    
    def _analyze_third_party_sharing(self, storage_data: Dict, requests: List, main_domain: str) -> Dict:
        """Analyze if storage items are shared with third parties via network requests."""
        sharing_results = {
            'items_shared': [],
            'third_party_domains': set(),
            'sharing_count': 0,
            'sharing_by_category': {},  # New: sharing counts by category
            'sharing_by_organization': {},  # New: sharing counts by organization
            'domains_shared_with': {}  # New: details about which domains got what
        }
        
        if not storage_data or 'visits' not in storage_data or not requests:
            return sharing_results
            
        # Extract all storage values for comparison
        storage_values = set()
        for visit_data in storage_data['visits'].values():
            # Extract localStorage values
            for item in visit_data.get('local_storage', []) or []:
                if isinstance(item, dict) and 'value' in item:
                    storage_values.add(str(item['value']))
            
            # Extract sessionStorage values
            for item in visit_data.get('session_storage', []) or []:
                if isinstance(item, dict) and 'value' in item:
                    storage_values.add(str(item['value']))
        
        # Extract values with length >= 8 characters only
        storage_values = {v for v in storage_values if isinstance(v, str) and len(v) >= 8}
        
        # Get domain information if available
        domain_info = {}
        if hasattr(storage_data, 'get'):
            domain_analysis = storage_data.get('domain_analysis', {})
            if domain_analysis and 'domains' in domain_analysis:
                for domain_data in domain_analysis.get('domains', []):
                    domain_url = domain_data.get('domain', '')
                    if domain_url:
                        # Strip off https:// if present
                        if domain_url.startswith('https://'):
                            domain_url = domain_url[8:]
                        # Store domain information for later use
                        domain_info[domain_url] = {
                            'categories': domain_data.get('categories', []),
                            'organizations': domain_data.get('organizations', []),
                            'is_infrastructure': domain_data.get('infrastructure_type') is not None,
                        }
        
        # Check if these values appear in third-party requests
        for request in requests:
            request_domain = request.get('domain', '')
            
            # Skip first-party requests
            if not request_domain or main_domain in request_domain:
                continue
                
            request_url = request.get('url', '')
            request_data = request.get('post_data', '')
            
            # Fix: Make sure request_url and request_data are strings before checking
            request_url_str = str(request_url) if request_url is not None else ''
            request_data_str = str(request_data) if request_data is not None else ''
            
            # Get domain info if available
            domain_categories = []
            domain_organizations = []
            is_infrastructure = False
            
            if request_domain in domain_info:
                domain_categories = domain_info[request_domain].get('categories', [])
                domain_organizations = domain_info[request_domain].get('organizations', [])
                is_infrastructure = domain_info[request_domain].get('is_infrastructure', False)
            
            # Search for storage values in the request URL and data
            found_sharing = False
            for value in storage_values:
                # Skip very short values to reduce false positives
                if len(value) < 8:
                    continue
                    
                # Fixed: Use string versions to avoid 'NoneType' is not iterable error
                if value in request_url_str or value in request_data_str:
                    found_sharing = True
                    sharing_results['items_shared'].append({
                        'value': value[:50] + ('...' if len(value) > 50 else ''),
                        'third_party_domain': request_domain,
                        'request_type': request.get('type', 'unknown'),
                        'request_method': request.get('method', 'unknown'),
                        'categories': domain_categories,
                        'organizations': domain_organizations,
                        'is_infrastructure': is_infrastructure
                    })
                    sharing_results['third_party_domains'].add(request_domain)
                    sharing_results['sharing_count'] += 1
                    
                    # Update sharing by category
                    for category in domain_categories or ['Uncategorized']:
                        if category not in sharing_results['sharing_by_category']:
                            sharing_results['sharing_by_category'][category] = 0
                        sharing_results['sharing_by_category'][category] += 1
                    
                    # Update sharing by organization
                    for org in domain_organizations or ['Unknown']:
                        if org not in sharing_results['sharing_by_organization']:
                            sharing_results['sharing_by_organization'][org] = 0
                        sharing_results['sharing_by_organization'][org] += 1
                    
                    # Update domains shared with
                    if request_domain not in sharing_results['domains_shared_with']:
                        sharing_results['domains_shared_with'][request_domain] = {
                            'count': 0,
                            'categories': domain_categories,
                            'organizations': domain_organizations,
                            'is_infrastructure': is_infrastructure
                        }
                    sharing_results['domains_shared_with'][request_domain]['count'] += 1
        
        # Convert set to list for JSON serialization
        sharing_results['third_party_domains'] = list(sharing_results['third_party_domains'])
        
        return sharing_results
    
    def batch_analyze_sites(self, folder_path: str) -> Dict:
        """Batch analyze multiple site data files in a folder."""
        import os
        
        results = {
            'sites_analyzed': 0,
            'sites_with_identifiers': 0,
            'total_identifiers': 0,
            'high_confidence_identifiers': 0,
            'persistent_identifier_rate': 0.0,
            'third_party_sharing_rate': 0.0,
            'sites': {}
        }
        
        # Find all JSON files in the folder
        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
        
        for filename in json_files:
            file_path = os.path.join(folder_path, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    site_data = json.load(f)
                
                site_domain = site_data.get('domain', filename.replace('.json', ''))
                site_analysis = self.analyze_site(site_data)
                
                results['sites'][site_domain] = site_analysis
                results['sites_analyzed'] += 1
                
                if site_analysis.get('identifier_count', 0) > 0:
                    results['sites_with_identifiers'] += 1
                    results['total_identifiers'] += site_analysis['identifier_count']
                    results['high_confidence_identifiers'] += site_analysis['scoring'].get('high_confidence', 0)
                
                # Track persistence and sharing rates
                persistence = site_analysis.get('persistence_analysis', {}).get('persistence_rate', 0)
                if persistence > 0:
                    results['persistent_identifier_rate'] += 1
                    
                sharing = site_analysis.get('third_party_sharing', {}).get('sharing_count', 0)
                if sharing > 0:
                    results['third_party_sharing_rate'] += 1
                    
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
        
        # Calculate rates
        if results['sites_analyzed'] > 0:
            results['sites_with_identifiers_percent'] = (results['sites_with_identifiers'] / results['sites_analyzed']) * 100
            results['persistent_identifier_rate'] = (results['persistent_identifier_rate'] / results['sites_analyzed']) * 100
            results['third_party_sharing_rate'] = (results['third_party_sharing_rate'] / results['sites_analyzed']) * 100
            
        return results

