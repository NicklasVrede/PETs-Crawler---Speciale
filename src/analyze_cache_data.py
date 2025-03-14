import os
import json
import re

class StorageCoordinator:
    """
    Coordinates the overall process of analyzing browser storage for tracking.
    
    This class:
    - Manages the analysis workflow
    - Processes site data files
    - Coordinates domain and sharing analysis
    - Collects and compiles results
    - Generates reports
    
    Acts as the orchestrator that brings together all parts of the analysis.
    """

    def __init__(self):
        from analyzers.cache_analyser import CacheAnalyzer
        self.identifier_analyzer = CacheAnalyzer()
        self.domain_info = {}
        self.sharing_info = {'values': {}, 'keys': {}}
        self.site_data = None
        self.analysis = None
        self.tracking_keywords = [
            'id', 'user', 'visitor', 'client', 'device', 'machine', 'fingerprint', 'track',
            'analytics', 'session', 'token', 'uuid', 'guid', 'uid', 'fp', 'account',
            'profile', 'customer', 'tracking', 'identify', 'canvas', 'persist', 'unique'
        ]

    def process_file(self, file_path):
        """Main method to process a site file."""
        self.load_site_data(file_path)
        self.run_analysis()
        self.build_domain_info()
        self.build_sharing_info()
        self.analyze_storage()
        self.update_statistics()
        self.save_results(file_path)
        self.report_summary(file_path)

    def load_site_data(self, file_path):
        """Load JSON data from file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            self.site_data = json.load(f)

    def run_analysis(self):
        """Run the analyzer and prepare results."""
        self.analysis = self.identifier_analyzer.analyze_site(self.site_data)
        if not self.analysis:
            print(f"Warning: Analyzer returned no results")
            self.analysis = {'potential_identifiers': []}

    def build_domain_info(self):
        """Build lookup of domain information."""
        if 'domain_analysis' in self.site_data and 'domains' in self.site_data['domain_analysis']:
            for domain_data in self.site_data['domain_analysis']['domains']:
                domain_url = domain_data.get('domain', '')
                if domain_url:
                    clean_domain = domain_url.replace('https://', '')
                    self.domain_info[clean_domain] = {
                        'categories': domain_data.get('categories', []),
                        'organizations': domain_data.get('organizations', []),
                        'is_infrastructure': domain_data.get('infrastructure_type') is not None
                    }

    def build_sharing_info(self):
        """Build information about value and key sharing."""
        self._collect_storage_keys()
        self._analyze_request_sharing()
        self._process_third_party_sharing()

    def _collect_storage_keys(self):
        """Collect all storage keys that might be used for tracking."""
        # Store unique keys
        all_keys = set()
        
        # Get all site visits from storage
        storage_visits = self.site_data.get('storage', {}).get('visits', {})
        for visit_data in storage_visits.values():
            # Check both storage types
            for storage_type in ['local_storage', 'session_storage']:
                storage_items = visit_data.get(storage_type, []) or []
                for item in storage_items:
                    if isinstance(item, dict):
                        key = item.get('key', '')
                        # Only collect keys of a certain length
                        if key and len(key) >= 8:
                            all_keys.add(key)
        
        return all_keys

    def _analyze_request_sharing(self):
        """Analyze requests for key sharing patterns."""
        all_keys = self._collect_storage_keys()
        
        for request in self.site_data.get('requests', []):
            domain = request.get('domain', '')
            if not domain:
                continue

            domain_info = self.domain_info.get(domain, {})
            request_url = str(request.get('url', '') or '')
            request_data = str(request.get('post_data', '') or '')

            self._check_key_sharing(all_keys, domain, domain_info, request_url, request_data)

    def _check_key_sharing(self, all_keys, domain, domain_info, request_url, request_data):
        """Check if keys are shared in request URL or data."""
        for key in all_keys:
            if key in request_url or key in request_data:
                self._update_key_sharing(key, domain, domain_info)

    def _update_key_sharing(self, key, domain, domain_info):
        """Update sharing information for a key."""
        if key not in self.sharing_info['keys']:
            self.sharing_info['keys'][key] = {
                'domains': set(),
                'categories': set(),
                'organizations': set(),
                'is_infrastructure_only': True
            }
        
        sharing = self.sharing_info['keys'][key]
        sharing['domains'].add(domain)
        sharing['categories'].update(domain_info.get('categories', []))
        sharing['organizations'].update(domain_info.get('organizations', []))
        if not domain_info.get('is_infrastructure', False):
            sharing['is_infrastructure_only'] = False

    def _process_third_party_sharing(self):
        """Process third-party sharing information."""
        third_party_items = self.analysis.get('third_party_sharing', {}).get('items_shared', [])
        
        for shared_item in third_party_items:
            value = shared_item.get('value', '')
            if not value:
                continue

            clean_value = value[:-3] if value.endswith('...') else value
            domain = shared_item.get('third_party_domain', '')
            domain_info = self.domain_info.get(domain, {})
            
            self._update_value_sharing(clean_value, domain, domain_info)

    def _update_value_sharing(self, value, domain, domain_info):
        """Update sharing information for a value."""
        if value not in self.sharing_info['values']:
            self.sharing_info['values'][value] = {
                'domains': set(),
                'categories': set(),
                'organizations': set(),
                'is_infrastructure_only': True
            }

        sharing = self.sharing_info['values'][value]
        sharing['domains'].add(domain)
        sharing['categories'].update(domain_info.get('categories', []))
        sharing['organizations'].update(domain_info.get('organizations', []))
        if not domain_info.get('is_infrastructure', False):
            sharing['is_infrastructure_only'] = False

    def analyze_storage(self):
        """Analyze all storage data."""
        if 'storage' in self.site_data and 'visits' in self.site_data['storage']:
            for visit_num, visit_data in self.site_data['storage']['visits'].items():
                self.analyze_visit(visit_num, visit_data)

    def analyze_visit(self, visit_num, visit_data):
        """Analyze storage data for a single visit."""
        for storage_type in ['local_storage', 'session_storage', 'cache_storage']:
            if storage_type in visit_data:
                for item in visit_data[storage_type]:
                    self.analyze_storage_item(item, storage_type, visit_num)

    def analyze_storage_item(self, item, storage_type, visit_num):
        """Analyze a single storage item."""
        key = item.get('key', '')
        value = str(item.get('value', ''))
        name = item.get('name', '')  # For cache storage
        
        lookup_key = f"{storage_type}:{visit_num}:{key or name}"
        item['analysis'] = {}

        # Check if already identified by analyzer
        potential_identifiers = self.analysis.get('potential_identifiers', [])
        for identifier in potential_identifiers:
            if (identifier.get('storage_type') == storage_type and
                identifier.get('visit') == visit_num and
                identifier.get('key') == (key or name)):
                item['analysis'].update({
                    'is_potential_identifier': True,
                    'confidence': identifier.get('confidence', 0),
                    'reasons': identifier.get('reasons', [])
                })
                break
        
        if 'is_potential_identifier' not in item['analysis']:
            # Direct detection
            reasons = []
            confidence = 0

            if storage_type != 'cache_storage':
                # Analyze value patterns
                if len(value) >= 16:
                    reasons.append("Long value (≥16 chars)")
                    confidence += 0.1
                    if re.search(r'[a-zA-Z]', value) and re.search(r'[0-9]', value):
                        reasons.append("Contains both letters and numbers")
                        confidence += 0.1

                # Check for specific patterns
                patterns = {
                    'uuid': (r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', 0.4),
                    'base64': (r'^[A-Za-z0-9+/]+={0,2}$', 0.3),
                    'md5': (r'^[0-9a-f]{32}$', 0.4),
                    'sha1': (r'^[0-9a-f]{40}$', 0.4),
                    'sha256': (r'^[0-9a-f]{64}$', 0.4),
                    'sha512': (r'^[0-9a-f]{128}$', 0.4)
                }

                for pattern_name, (pattern, conf) in patterns.items():
                    if re.match(pattern, value, re.I):
                        reasons.append(f"Matches {pattern_name.upper()} format")
                        confidence += conf
                        break

            # Check key/name for tracking terms
            check_value = key.lower() if storage_type != 'cache_storage' else name.lower()
            for keyword in self.tracking_keywords:
                if keyword in check_value:
                    reasons.append(f"Contains tracking-related term: '{keyword}'")
                    confidence += 0.3
                    break

            if confidence > 0:
                item['analysis'].update({
                    'is_potential_identifier': True,
                    'confidence': min(confidence, 1.0),
                    'reasons': reasons
                })
            else:
                item['analysis']['is_potential_identifier'] = False

        # Add sharing information
        if storage_type != 'cache_storage':
            if value in self.sharing_info['values'] or key in self.sharing_info['keys']:
                item['analysis']['is_shared'] = True
                item['analysis']['shared_with'] = {
                    'domains': [],
                    'categories': [],
                    'organizations': [],
                    'is_infrastructure_only': True,
                    'shared_by': []
                }

                # Add value sharing info
                if value in self.sharing_info['values']:
                    sharing = self.sharing_info['values'][value]
                    self._update_sharing_info(item['analysis']['shared_with'], sharing, 'value')

                # Add key sharing info
                if key in self.sharing_info['keys']:
                    sharing = self.sharing_info['keys'][key]
                    self._update_sharing_info(item['analysis']['shared_with'], sharing, 'key')

                # Update confidence if shared with non-infrastructure parties
                if (not item['analysis']['shared_with']['is_infrastructure_only'] and 
                    item['analysis'].get('confidence', 0) > 0):
                    item['analysis']['confidence'] = min(item['analysis']['confidence'] + 0.2, 1.0)
                    shared_by = 'key' in item['analysis']['shared_with']['shared_by']
                    item['analysis']['reasons'].append(
                        f"{'Key' if shared_by else 'Value'} shared with non-infrastructure third parties"
                    )
            else:
                item['analysis']['is_shared'] = False
        else:
            item['analysis']['is_shared'] = False

    def _update_sharing_info(self, target, source, shared_type):
        """Helper method to update sharing information."""
        target['domains'].extend(list(source['domains']))
        target['categories'].extend(list(source['categories']))
        target['organizations'].extend(list(source['organizations']))
        target['is_infrastructure_only'] &= source['is_infrastructure_only']
        target['shared_by'].append(shared_type)
        
        # Remove duplicates
        target['domains'] = list(set(target['domains']))
        target['categories'] = list(set(target['categories']))
        target['organizations'] = list(set(target['organizations']))

    def update_statistics(self):
        """Update site statistics with analysis results."""
        stats = {
            'total_potential_identifiers': 0,
            'high_confidence_identifiers': 0,
            'medium_confidence_identifiers': 0,
            'low_confidence_identifiers': 0,
            'shared_identifiers': 0
        }

        if 'storage' in self.site_data and 'visits' in self.site_data['storage']:
            for visit_data in self.site_data['storage']['visits'].values():
                for storage_type in ['local_storage', 'session_storage', 'cache_storage']:
                    if storage_type in visit_data:
                        for item in visit_data[storage_type]:
                            analysis_data = item.get('analysis', {})
                            if analysis_data.get('is_potential_identifier', False):
                                stats['total_potential_identifiers'] += 1
                                confidence = analysis_data.get('confidence', 0)
                                
                                if confidence >= 0.8:
                                    stats['high_confidence_identifiers'] += 1
                                elif confidence >= 0.5:
                                    stats['medium_confidence_identifiers'] += 1
                                else:
                                    stats['low_confidence_identifiers'] += 1
                                
                                if analysis_data.get('is_shared', False):
                                    stats['shared_identifiers'] += 1

        # Add persistence and sharing from original analysis
        stats['persistent_identifiers'] = len(self.analysis.get('persistence_analysis', {}).get('persistent_items', []) or [])
        stats['third_party_sharing'] = self.analysis.get('third_party_sharing', {}).get('sharing_count', 0)

        # Update site statistics
        if 'statistics' not in self.site_data:
            self.site_data['statistics'] = {}
        self.site_data['statistics']['identifier_analysis'] = stats

        # Add enhanced sharing data if available
        if 'third_party_sharing' in self.analysis:
            if 'sharing_by_category' in self.analysis['third_party_sharing']:
                stats['sharing_by_category'] = self.analysis['third_party_sharing']['sharing_by_category']
            if 'sharing_by_organization' in self.analysis['third_party_sharing']:
                stats['sharing_by_organization'] = self.analysis['third_party_sharing']['sharing_by_organization']

    def save_results(self, file_path):
        """Save updated site data back to file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.site_data, f, indent=2, default=str)

    def report_summary(self, file_path):
        """Print analysis summary."""
        stats = self.site_data.get('statistics', {}).get('identifier_analysis', {})
        print_summary(
            os.path.basename(file_path),
            stats.get('total_potential_identifiers', 0),
            stats.get('high_confidence_identifiers', 0),
            stats.get('shared_identifiers', 0)
        )


def print_summary(filename, identifiers, high_conf, shared=None):
    """Print a very brief summary of what was found."""
    if identifiers > 0:
        if shared is not None:
            print(f"{filename}: Found {identifiers} potential identifiers ({high_conf} high confidence, {shared} shared with third parties)")
        else:
            print(f"{filename}: Found {identifiers} potential identifiers ({high_conf} high confidence)")
    else:
        print(f"{filename}: No potential identifiers found")


if __name__ == "__main__":
    data_dir = 'data/crawler_data/i_dont_care_about_cookies'
    coordinator = StorageCoordinator()
    
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    print(f"Found {len(json_files)} JSON files in {data_dir}")
    
    for filename in json_files:
        try:
            coordinator.process_file(os.path.join(data_dir, filename))
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    
    print(f"\nCompleted analysis of {len(json_files)} files") 