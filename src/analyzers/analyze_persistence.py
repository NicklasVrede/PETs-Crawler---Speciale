import json
import os
import datetime
from collections import Counter, defaultdict
import glob
import difflib  # For Ratcliff/Obershelp string comparison
from tqdm import tqdm
import sys


class StorageAnalyzer:
    """
    Analyzes web tracking mechanisms including:
    - Persistent storage
    - Cookies and their persistence
    - Potential tracking cookies and identifiers
    - Cookie sharing across domains
    """
    
    def __init__(self, testing=False, verbose=False):
        """
        Initialize the analyzer
        
        Args:
            testing: If True, save to new files with "_enhanced" suffix instead of overwriting
            verbose: If True, print detailed progress information
        """
        self.testing = testing
        self.verbose = verbose
        self.data_path = None
        self.data = None
        
    def _log(self, message):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            tqdm.write(message)
        
    def analyze_file(self, data_path):
        """Analyze a single file"""
        self.data_path = data_path
        self.data = None
        
        if not self._load_data():
            return False
            
        # Run all analysis functions
        self._mark_persistent_storage()
        self._mark_persistent_cookies()
        self._check_identical_cookies()
        self._identify_potential_tracking_cookies()
        self._analyze_cookie_sharing()
        self._analyze_storage_identifiers()
        
        # Save the enhanced data
        self._save_data()
        return True
    
    def analyze_directory(self, directory_path):
        """
        Analyze persistent storage and cookies in all JSON files in a directory.
        
        Args:
            directory_path: Path to the directory containing JSON files
        """
        json_files = glob.glob(os.path.join(directory_path, '*.json'))
        
        if not json_files:
            self._log(f"No JSON files found in {directory_path}")
            return
        
        self._log(f"Analyzing persistence for {len(json_files)} files...")
        
        # Use tqdm only if verbose is True
        files_iter = tqdm(json_files, desc="Analyzing web tracking", unit="file") if self.verbose else json_files
        for json_file in files_iter:
            self.analyze_file(json_file)
            
    def _load_data(self):
        """Load the data from the JSON file (private method)"""
        try:
            with open(self.data_path, 'r') as file:
                self.data = json.load(file)
            return True
        except FileNotFoundError:
            self._log(f"Error: File not found at {self.data_path}")
            return False
        except json.JSONDecodeError:
            self._log(f"Error: Invalid JSON at {self.data_path}")
            return False
    
    def _save_data(self):
        """Save the analyzed data based on testing mode (private method)"""
        if self.testing:
            # Create a new file with "_enhanced" suffix
            output_path = self.data_path.replace('.json', '_enhanced.json')
            with open(output_path, 'w') as file:
                json.dump(self.data, file, indent=2)
            self._log(f"Enhanced data saved to new file: {output_path}")
        else:
            # Save enhanced data back to the original file
            with open(self.data_path, 'w') as file:
                json.dump(self.data, file, indent=2)
            self._log(f"Enhanced data saved to original file: {self.data_path}")
    
    def _mark_persistent_storage(self):
        """Mark localStorage items as persistent (private method)"""
        if 'storage' not in self.data:
            self._log("No storage data found")
            return
        
        # Add verification print
        self._log("Processing persistent storage marking...")
        
        local_storage_count = 0
        session_storage_count = 0
        
        # Process each visit's storage data
        for visit_key, visit_data in self.data['storage'].items():
            if visit_key == '...':  # Skip the summary entry
                continue
            
            # Mark localStorage items as persistent (they typically persist between sessions)
            if 'local_storage' in visit_data:
                local_storage_count += len(visit_data['local_storage'])
                for item in visit_data['local_storage']:
                    item['persistent'] = True
            
            # SessionStorage items are not persistent by definition
            if 'session_storage' in visit_data:
                session_storage_count += len(visit_data['session_storage'])
                for item in visit_data['session_storage']:
                    item['persistent'] = False
        
        # Add verification print
        self._log(f"Marked {local_storage_count} localStorage items as persistent")
        self._log(f"Marked {session_storage_count} sessionStorage items as non-persistent")

    def _mark_persistent_cookies(self):
        """Mark cookies as persistent if they have a future expiration date (private method)"""
        if 'cookies' not in self.data:
            self._log("No cookie data found")
            return
        
        current_time = datetime.datetime.now().timestamp()
        
        # Count persistent and non-persistent cookies
        persistent_count = 0
        non_persistent_count = 0
        
        # Handle different cookie data structures
        if isinstance(self.data['cookies'], dict):
            # Format: {'visit1': [cookies], 'visit2': [cookies]}
            for visit_id, visit_cookies in self.data['cookies'].items():
                for cookie in visit_cookies:
                    if cookie.get('expires') and cookie['expires'] > current_time:
                        cookie['persistent'] = True
                        # Add days until expiry as a user-friendly metric
                        days_until_expiry = (cookie['expires'] - current_time) / (60 * 60 * 24)
                        cookie['days_until_expiry'] = round(days_until_expiry, 2)
                        persistent_count += 1
                    else:
                        cookie['persistent'] = False
                        non_persistent_count += 1
        
            # Get total cookie count across all visits
            total_cookies = sum(len(cookies) for cookies in self.data['cookies'].values())
        
        elif isinstance(self.data['cookies'], list):
            # Simple list format
            for cookie in self.data['cookies']:
                if cookie.get('expires') and cookie['expires'] > current_time:
                    cookie['persistent'] = True
                    # Add days until expiry as a user-friendly metric
                    days_until_expiry = (cookie['expires'] - current_time) / (60 * 60 * 24)
                    cookie['days_until_expiry'] = round(days_until_expiry, 2)
                    persistent_count += 1
                else:
                    cookie['persistent'] = False
                    non_persistent_count += 1
        
        # Update cookie_analysis with persistence statistics
        if 'cookie_analysis' in self.data:
            self.data['cookie_analysis']['persistent_count'] = persistent_count
            self.data['cookie_analysis']['non_persistent_count'] = non_persistent_count
            self.data['cookie_analysis']['persistence_ratio'] = round(persistent_count / total_cookies * 100, 2) if total_cookies else 0

    def _check_identical_cookies(self):
        """Check if cookies have identical values across visits (private method)"""
        if 'network_data' not in self.data:
            self._log("No network data found for cookie value comparison")
            return
        
        # Track cookie values across visits
        cookie_values = defaultdict(dict)
        identical_count = 0
        changing_count = 0
        
        # Collect cookie values from all visits
        visit_count = 0
        for visit_key, visit_data in self.data['network_data'].items():
            if visit_key == '...':  # Skip the summary entry
                continue
            
            visit_count += 1
            if 'requests' not in visit_data:
                continue
            
            for request in visit_data['requests']:
                if 'headers' in request and 'cookie' in request['headers']:
                    cookie_header = request['headers']['cookie']
                    cookies = cookie_header.split(';')
                    
                    for cookie in cookies:
                        if '=' in cookie:
                            name, value = cookie.strip().split('=', 1)
                            if name not in cookie_values:
                                cookie_values[name] = {}
                            cookie_values[name][visit_key] = value
        
        # Check if values are identical across visits
        for name, values in cookie_values.items():
            if len(values) > 1:  # Cookie appears in multiple visits
                values_list = list(values.values())
                is_identical = all(val == values_list[0] for val in values_list)
                if is_identical:
                    identical_count += 1
                else:
                    changing_count += 1
        
        # Add information to the cookie analysis
        if cookie_values and 'cookie_analysis' in self.data:
            total_multi_visit = identical_count + changing_count
            
            self.data['cookie_analysis']['value_consistency'] = {
                'cookies_in_multiple_visits': total_multi_visit,
                'identical_value_count': identical_count,
                'changing_value_count': changing_count,
                'identical_percentage': round(identical_count / total_multi_visit * 100, 1) if total_multi_visit > 0 else 0
            }

    def _identify_potential_tracking_cookies(self):
        """
        Identify cookies with characteristics that suggest they are being used for tracking:
        - Persistent cookies with long lifetimes
        - Cookies with sufficient entropy to uniquely identify users
        - Cookies that have consistent or similarly structured values across visits
        """
        if 'cookies' not in self.data:
            return
        
        # Dictionary to store potential tracking cookies by their names
        cookies_by_name = {}
        
        # Group cookies by name across visits
        for visit_key, visit_cookies in self.data['cookies'].items():
            for cookie in visit_cookies:
                cookie_name = cookie.get('name', '')
                if not cookie_name:
                    continue
                
                if cookie_name not in cookies_by_name:
                    cookies_by_name[cookie_name] = []
                cookies_by_name[cookie_name].append(cookie)
        
        potential_trackers_count = 0
        failed_checks = {
            'persistent': 0,
            'entropy': 0,
            'length': 0,
            'similarity': 0
        }
        
        # Analyze each cookie for tracking characteristics
        for cookie_name, cookies in cookies_by_name.items():
            # Skip if only one occurrence
            if len(cookies) <= 1:
                continue
            
            # Initialize tracking potential as False
            is_potential_tracker = False
            
            # Check 1: Long-lived persistent cookies
            persistent_long_lived = False
            for cookie in cookies:
                if cookie.get('persistent', False) and cookie.get('days_until_expiry', 0) > 90:
                    persistent_long_lived = True
                    break
            if not persistent_long_lived:
                failed_checks['persistent'] += 1
            
            # Check 2 & 4: Sufficient entropy and length difference
            values = [cookie.get('value', '') for cookie in cookies]
            lengths = [len(value) for value in values]
            min_length = min(lengths) if lengths else 0
            max_length = max(lengths) if lengths else 0
            
            # Only consider cookies with values of at least 8 bytes
            entropy_sufficient = min_length >= 8
            if not entropy_sufficient:
                failed_checks['entropy'] += 1
            
            # Check if length difference is within 25%
            length_consistency = True
            if min_length > 0:
                length_consistency = (max_length - min_length) / min_length <= 0.25
            if not length_consistency:
                failed_checks['length'] += 1
            
            # Check 3 & 5: Different but similar values (Ratcliff/Obershelp)
            values_similar = False
            if len(set(values)) > 1:  # If we have different values
                for i in range(len(values)):
                    for j in range(i+1, len(values)):
                        # Skip identical values
                        if values[i] == values[j]:
                            continue
                        
                        # Use difflib to calculate similarity ratio
                        similarity = difflib.SequenceMatcher(None, values[i], values[j]).ratio()
                        
                        # If values are similar but not identical (similarity ≥ 60%)
                        if similarity >= 0.6:
                            values_similar = True
                            break
                    if values_similar:
                        break
            if not values_similar:
                failed_checks['similarity'] += 1
            
            # A cookie is a tracker if ALL conditions are met
            is_potential_tracker = (
                persistent_long_lived and 
                entropy_sufficient and 
                length_consistency and 
                values_similar
            )
            
            if is_potential_tracker:
                potential_trackers_count += 1
            
            # Mark cookies as potential tracking identifiers
            for cookie in cookies:
                cookie['is_potential_identifier'] = is_potential_tracker
        
        self._log(f"Tracking cookies analysis results:")
        self._log(f"  Total potential trackers found: {potential_trackers_count}")
        self._log(f"  Failed persistence check: {failed_checks['persistent']}")
        self._log(f"  Failed entropy check: {failed_checks['entropy']}")
        self._log(f"  Failed length consistency check: {failed_checks['length']}")
        self._log(f"  Failed similarity check: {failed_checks['similarity']}")
        
        # Add summary statistics about potential tracking cookies
        self._add_potential_tracking_cookies_summary()

    def _add_potential_tracking_cookies_summary(self):
        """
        Add summary statistics about potential tracking cookies to the data.
        """
        if 'cookies' not in self.data:
            return
        
        # Count potential tracking cookies by category
        potential_trackers = {}
        potential_tracker_names = []
        
        for visit_key, visit_cookies in self.data['cookies'].items():
            for cookie in visit_cookies:
                if cookie.get('is_potential_identifier', False):
                    cookie_name = cookie.get('name', 'Unknown')
                    cookie_category = cookie.get('category', 'Unknown')
                    
                    if cookie_name not in potential_tracker_names:
                        potential_tracker_names.append(cookie_name)
                    
                    if cookie_category not in potential_trackers:
                        potential_trackers[cookie_category] = 0
                    potential_trackers[cookie_category] += 1
        
        # Add summary data
        self.data['cookie_analysis']['potential_tracking_cookies'] = {
            'total': len(potential_tracker_names),
            'by_category': potential_trackers,
            'cookie_names': potential_tracker_names
        }

    def _analyze_cookie_sharing(self):
        """
        Analyze which cookies are shared with which domains,
        with special focus on third-party sharing (private method).
        """
        if 'network_data' not in self.data or 'domain_analysis' not in self.data:
            self._log("Missing network_data or domain_analysis for cookie sharing analysis")
            return
        
        # Create lookup table for domain classification
        domain_classification = {}
        for domain_info in self.data['domain_analysis'].get('domains', []):
            domain_url = domain_info.get('domain', '')
            domain_classification[domain_url] = {
                'is_first_party': domain_info.get('is_first_party_domain', False),
                'is_infrastructure': domain_info.get('infrastructure_type') is not None,
                'categories': domain_info.get('categories', []),
                'organizations': domain_info.get('organizations', [])
            }
        
        # Analyze cookie sharing across domains
        cookie_sharing = defaultdict(lambda: {'all_domains': set(), 'third_party_domains': set()})
        
        for visit_key, visit_data in self.data['network_data'].items():
            if visit_key == '...' or 'requests' not in visit_data:  # Skip the summary entry
                continue
            
            for request in visit_data['requests']:
                if 'headers' not in request or 'cookie' not in request['headers']:
                    continue
                
                # Extract domain from request URL
                request_url = request.get('url', '')
                request_domain = request.get('domain', '')
                full_domain_url = f"https://{request_domain}" if request_domain else ''
                
                # Skip if we can't determine the domain
                if not full_domain_url:
                    continue
                
                # Get domain classification
                is_first_party = domain_classification.get(full_domain_url, {}).get('is_first_party', False)
                is_infrastructure = domain_classification.get(full_domain_url, {}).get('is_infrastructure', False)
                
                # Parse cookies from request headers
                cookie_header = request['headers']['cookie']
                cookies = cookie_header.split(';')
                
                for cookie in cookies:
                    if '=' in cookie:
                        name, value = cookie.strip().split('=', 1)
                        
                        # Record domain sharing information
                        cookie_sharing[name]['all_domains'].add(full_domain_url)
                        
                        # Record third-party sharing (not first party and not infrastructure)
                        if not is_first_party and not is_infrastructure:
                            cookie_sharing[name]['third_party_domains'].add(full_domain_url)
        
        # Prepare the analysis output
        third_party_domains = set()
        cookies_with_third_parties = set()  # Track unique cookies shared with third parties
        
        # Function to update cookie with sharing information
        def update_cookie_with_sharing(cookie):
            cookie_name = cookie.get('name')
            if cookie_name in cookie_sharing:
                sharing_info = cookie_sharing[cookie_name]
                
                # Add sharing information to the cookie entry
                cookie['shared_with'] = list(sharing_info['all_domains'])
                cookie['shared_with_third_parties'] = len(sharing_info['third_party_domains']) > 0
                
                if cookie['shared_with_third_parties']:
                    cookie['third_party_domains'] = list(sharing_info['third_party_domains'])
                    cookies_with_third_parties.add(cookie_name)  # Track unique cookie names
                    third_party_domains.update(sharing_info['third_party_domains'])
            else:
                cookie['shared_with'] = []
                cookie['shared_with_third_parties'] = False
        
        # Add sharing information based on the cookie structure
        if 'cookies' in self.data:
            if isinstance(self.data['cookies'], dict):
                # Format: {'visit1': [cookies], 'visit2': [cookies]}
                for visit_cookies in self.data['cookies'].values():
                    for cookie in visit_cookies:
                        update_cookie_with_sharing(cookie)
            elif isinstance(self.data['cookies'], list):
                # Simple list format
                for cookie in self.data['cookies']:
                    update_cookie_with_sharing(cookie)
        
        # Add summary to cookie_analysis section
        if 'cookie_analysis' in self.data:
            self.data['cookie_analysis']['cookie_sharing'] = {
                'total_cookies_shared': len(cookie_sharing),
                'cookies_shared_with_third_parties': len(cookies_with_third_parties),  # Count of unique cookies
                'third_party_domains_receiving_cookies': list(third_party_domains)
            }

    def _analyze_storage_identifiers(self):
        """
        Identify localStorage and sessionStorage items that may be used for tracking.
        """
        if 'storage' not in self.data:
            return
        
        # Add verification print
        self._log("Analyzing storage for potential tracking identifiers...")
        
        # Track storage items across visits
        storage_items = {
            'localStorage': defaultdict(list),  # Structure: {key: [values across visits]}
            'sessionStorage': defaultdict(list)
        }
        
        # First pass: collect all values across visits
        for _, visit_data in self.data['storage'].items():
            # Collect localStorage items
            if 'local_storage' in visit_data:
                for item in visit_data['local_storage']:
                    key = item.get('key', '')
                    value = item.get('value', '')
                    if key:
                        storage_items['localStorage'][key].append(value)
            
            # Collect sessionStorage items
            if 'session_storage' in visit_data:
                for item in visit_data['session_storage']:
                    key = item.get('key', '')
                    value = item.get('value', '')
                    if key:
                        storage_items['sessionStorage'][key].append(value)
        
        # Add verification print
        self._log(f"Found {len(storage_items['localStorage'])} unique localStorage keys")
        self._log(f"Found {len(storage_items['sessionStorage'])} unique sessionStorage keys")
        
        # Counters for potential identifiers
        potential_identifiers = {
            'localStorage': [],
            'sessionStorage': []
        }
        
        failed_checks = {
            'session': 0,      # For sessionStorage (always fails persistence)
            'entropy': 0,
            'length': 0,
            'similarity': 0
        }
        potential_trackers_count = 0
        
        # Second pass: analyze each item for tracking characteristics
        for storage_type in ['localStorage', 'sessionStorage']:
            for key, values in storage_items[storage_type].items():
                # Skip if only one occurrence
                if len(values) <= 1:
                    continue
                
                # Step 1: Check persistence - localStorage is always persistent, sessionStorage never is
                persistent = (storage_type == 'localStorage')
                if not persistent:
                    failed_checks['session'] += 1
                    continue  # Skip sessionStorage items as they fail the first condition
                
                # Step 2: Check entropy (length ≥ 8 bytes)
                lengths = [len(str(v)) for v in values]
                min_length = min(lengths) if lengths else 0
                max_length = max(lengths) if lengths else 0
                
                entropy_sufficient = min_length >= 8
                if not entropy_sufficient:
                    failed_checks['entropy'] += 1
                    continue
                
                # Step 3: Check length consistency (variation ≤ 25%)
                length_consistency = True
                if min_length > 0:
                    length_consistency = (max_length - min_length) / min_length <= 0.25
                if not length_consistency:
                    failed_checks['length'] += 1
                    continue
                
                # Step 4: Check for similar values (similarity ≥ 60%)
                values_similar = False
                if len(set(values)) > 1:  # If we have different values
                    for i in range(len(values)):
                        for j in range(i+1, len(values)):
                            # Skip identical values
                            if values[i] == values[j]:
                                continue
                            
                            # Use difflib to calculate similarity ratio
                            similarity = difflib.SequenceMatcher(None, str(values[i]), str(values[j])).ratio()
                            
                            # If values are similar but not identical (similarity ≥ 60%)
                            if similarity >= 0.6:
                                values_similar = True
                                break
                        if values_similar:
                            break
                if not values_similar:
                    failed_checks['similarity'] += 1
                    continue
                
                # If we reach here, all conditions are met
                potential_trackers_count += 1
                
                # Mark items in the original data
                for visit_key, visit_data in self.data['storage'].items():
                    storage_type_key = 'local_storage' if storage_type == 'localStorage' else 'session_storage'
                    if storage_type_key in visit_data:
                        for item in visit_data[storage_type_key]:
                            if item.get('key') == key:
                                item['is_potential_identifier'] = True
                
                # Add to summary list
                potential_identifiers[storage_type].append({
                    'key': key,
                    'visits': len(set(self.data['storage'].keys())),
                    'similar_values': True  # All items that reach here have similar values
                })
        
        # Add summary to data
        if 'storage_analysis' not in self.data:
            self.data['storage_analysis'] = {}
        
        # Extract the keys (names) of all potential identifiers
        local_storage_names = [item['key'] for item in potential_identifiers['localStorage']]
        session_storage_names = [item['key'] for item in potential_identifiers['sessionStorage']]
        
        self.data['storage_analysis']['potential_identifiers'] = {
            'total': len(potential_identifiers['localStorage']) + len(potential_identifiers['sessionStorage']),
            'localStorage': len(potential_identifiers['localStorage']),
            'sessionStorage': len(potential_identifiers['sessionStorage']),
            'items': potential_identifiers,
            'item_names': {
                'localStorage': local_storage_names,
                'sessionStorage': session_storage_names
            }
        }
        
        self._log(f"Storage tracking analysis results:")
        self._log(f"  Total potential trackers found: {potential_trackers_count}")
        self._log(f"  Failed session/persistence check: {failed_checks['session']}")
        self._log(f"  Failed entropy check: {failed_checks['entropy']}")
        self._log(f"  Failed length consistency check: {failed_checks['length']}")
        self._log(f"  Failed similarity check: {failed_checks['similarity']}")

if __name__ == "__main__":
    # Directory with test files
    data_directory = 'data/crawler_data non-kameleo/test'
    
    # Validate directory exists
    if not os.path.exists(data_directory):
        print(f"Error: Directory not found: {data_directory}")
        print("Please ensure the data directory exists before running the script.")
        sys.exit(1)
    
    print(f"Analyzing files in {data_directory}...")
    
    # Create analyzer with verbose output
    analyzer = StorageAnalyzer(testing=True, verbose=True)
    
    # Process all JSON files in the directory
    try:
        analyzer.analyze_directory(data_directory)
        print("\nAnalysis complete!")
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user.")
        sys.exit(0)