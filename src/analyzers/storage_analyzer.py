import json
import os
import datetime
import time  # Add this import
from collections import Counter, defaultdict
import glob
import difflib  # For Ratcliff/Obershelp string comparison
from tqdm import tqdm
import sys

SIMPLIFIED_COMPARISON_THRESHOLD = 20_000 
# String length threshold above which simplified prefix/suffix comparison is used
# Instead of full Ratcliff/Obershelp comparison, to prevent excessive CPU usage


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
        start_time = time.time()
        self._log(f"Starting analysis of {os.path.basename(data_path)}")
        
        self.data = None
        
        if not self._load_data():
            return False
        
        # Add explicit check for self.data
        if self.data is None:
            self._log(f"Error: No data loaded from {data_path}")
            return False
            
        load_time = time.time() - start_time
        self._log(f"Data loading completed in {load_time:.2f} seconds")
            
        # Initialize empty structures if they don't exist
        self.data = self.data if isinstance(self.data, dict) else {}
        self.data['storage'] = self.data.get('storage', {})
        self.data['cookies'] = self.data.get('cookies', {})
        self.data['cookie_analysis'] = self.data.get('cookie_analysis', {})
        self.data['storage_analysis'] = self.data.get('storage_analysis', {})
        
        # Run analyses
        t0 = time.time()
        self._mark_persistent_storage()
        analysis_times = {'persistent_storage': time.time() - t0}
        
        t0 = time.time()
        self._mark_persistent_cookies()
        analysis_times['persistent_cookies'] = time.time() - t0
        
        t0 = time.time()
        self._check_identical_cookies()
        analysis_times['identical_cookies'] = time.time() - t0
        
        t0 = time.time()
        self._identify_potential_tracking_cookies()
        analysis_times['tracking_cookies'] = time.time() - t0
        
        t0 = time.time()
        self._analyze_cookie_sharing()
        analysis_times['cookie_sharing'] = time.time() - t0
        
        t0 = time.time()
        self._analyze_storage_identifiers()
        analysis_times['storage_identifiers'] = time.time() - t0
        
        # Save the enhanced data
        t0 = time.time()
        self._save_data()
        save_time = time.time() - t0
        
        total_time = time.time() - start_time + 1e-10  # Add epsilon to avoid division by zero
        
        # Log timing information
        self._log(f"\nPerformance summary for {os.path.basename(data_path)}:")
        self._log(f"  Total analysis time: {total_time:.2f} seconds")
        self._log(f"  Data loading: {load_time:.2f} seconds")
        for analysis, duration in analysis_times.items():
            self._log(f"  {analysis.replace('_', ' ').title()}: {duration:.2f} seconds ({duration/total_time*100:.1f}%)")
        self._log(f"  Data saving: {save_time:.2f} seconds")
        
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
        """Mark cookies as persistent if they have a future expiration date and identify first/third party status"""
        if 'cookies' not in self.data:
            self._log("No cookie data found")
            return
        
        current_time = datetime.datetime.now().timestamp()
        
        # Count statistics
        persistent_count = 0
        non_persistent_count = 0
        
        # Track unique cookies by name+domain to prevent double counting
        unique_cookies = {}  # key: (name, domain) -> cookie data
        
        # Get first-party domains from domain_analysis if available
        first_party_domains = set()
        if 'domain_analysis' in self.data:
            for domain in self.data['domain_analysis'].get('domains', []):
                if domain.get('is_first_party_domain', False):
                    domain_url = domain.get('domain', '')
                    if domain_url:
                        # Extract domain without protocol
                        domain_name = domain_url.replace('https://', '').replace('http://', '')
                        first_party_domains.add(domain_name)
        
        def is_first_party_cookie(cookie_domain, first_party_domains):
            """Helper function to determine if a cookie is first-party"""
            if not cookie_domain:
                return False
            
            # Remove leading dot if present
            if cookie_domain.startswith('.'):
                cookie_domain = cookie_domain[1:]
                
            # Check if cookie domain matches or is subdomain of any first-party domain
            return any(
                cookie_domain == domain or 
                cookie_domain.endswith('.' + domain)
                for domain in first_party_domains
            )
        
        # Process cookies and track unique ones
        if isinstance(self.data['cookies'], dict):
            for visit_id, visit_cookies in self.data['cookies'].items():
                for cookie in visit_cookies:
                    cookie_key = (cookie.get('name', ''), cookie.get('domain', ''))
                    
                    # Store unique cookie
                    if cookie_key not in unique_cookies:
                        unique_cookies[cookie_key] = cookie
                    
                    # Mark persistence
                    if cookie.get('expires') and cookie['expires'] > current_time:
                        cookie['persistent'] = True
                        days_until_expiry = (cookie['expires'] - current_time) / (60 * 60 * 24)
                        cookie['days_until_expiry'] = round(days_until_expiry, 2)
                    else:
                        cookie['persistent'] = False
                    
                    # Mark first/third party status
                    cookie_domain = cookie.get('domain', '')
                    is_first_party = is_first_party_cookie(cookie_domain, first_party_domains)
                    cookie['is_first_party'] = is_first_party
        
        # Count unique first/third party cookies
        first_party_count = sum(1 for cookie in unique_cookies.values() if cookie.get('is_first_party', False))
        third_party_count = sum(1 for cookie in unique_cookies.values() if not cookie.get('is_first_party', False))
        
        # Count persistent/non-persistent from unique cookies
        persistent_count = sum(1 for cookie in unique_cookies.values() if cookie.get('persistent', False))
        non_persistent_count = sum(1 for cookie in unique_cookies.values() if not cookie.get('persistent', False))
        
        # Update cookie_analysis with statistics in the desired order
        if 'cookie_analysis' in self.data:
            total_cookies = len(unique_cookies)
            self.data['cookie_analysis'] = {
                'unique_cookies': total_cookies,
                'overlapping_cookies': self.data['cookie_analysis'].get('overlapping_cookies', 0),
                'identified_cookies': self.data['cookie_analysis'].get('identified_cookies', 0),
                'unidentified_cookies': self.data['cookie_analysis'].get('unidentified_cookies', 0),
                'first_party_cookies': first_party_count,
                'third_party_cookies': third_party_count,
                # Preserve all other existing keys
                **{k: v for k, v in self.data['cookie_analysis'].items() 
                   if k not in ['unique_cookies', 'overlapping_cookies', 'identified_cookies', 
                              'unidentified_cookies', 'first_party_cookies', 'third_party_cookies']}
            }

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
        Identify cookies with characteristics that suggest they are being used for tracking.
        """
        if 'cookies' not in self.data:
            return
        
        start_time = time.time()
        self._log("Starting potential tracking cookies analysis...")
        
        # Dictionary to store potential tracking cookies by their names
        cookies_by_name = {}
        
        # Group cookies by name across visits
        t0 = time.time()
        for visit_key, visit_cookies in self.data['cookies'].items():
            for cookie in visit_cookies:
                cookie_name = cookie.get('name', '')
                if not cookie_name:
                    continue
                
                if cookie_name not in cookies_by_name:
                    cookies_by_name[cookie_name] = []
                cookies_by_name[cookie_name].append(cookie)
        collection_time = time.time() - t0
        
        potential_trackers_count = 0
        failed_checks = {
            'persistent': 0,
            'entropy': 0,
            'length': 0,
            'similarity': 0
        }
        
        # Time the analysis of each cookie separately
        persistence_check_time = 0
        entropy_check_time = 0
        similarity_check_time = 0
        
        # Analyze each cookie for tracking characteristics
        cookies_analyzed = 0
        similarity_pairs_checked = 0
        for cookie_name, cookies in cookies_by_name.items():
            cookies_analyzed += 1
            
            # Skip if only one occurrence
            if len(cookies) <= 1:
                continue
            
            # Initialize tracking potential as False
            is_potential_tracker = False
            
            # Check 1: Long-lived persistent cookies
            t0 = time.time()
            persistent_long_lived = False
            for cookie in cookies:
                if cookie.get('persistent', False) and cookie.get('days_until_expiry', 0) > 90:
                    persistent_long_lived = True
                    break
            if not persistent_long_lived:
                failed_checks['persistent'] += 1
            persistence_check_time += time.time() - t0
            
            # Check 2 & 4: Sufficient entropy and length difference
            t0 = time.time()
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
            entropy_check_time += time.time() - t0
            
            # Check 3 & 5: Different but similar values (Ratcliff/Obershelp)
            t0 = time.time()
            values_similar = False
            if len(set(values)) > 1:  # If we have different values
                # Count similarity checks for analysis
                pairs_in_this_cookie = 0
                for i in range(len(values)):
                    for j in range(i+1, len(values)):
                        pairs_in_this_cookie += 1
                        similarity_pairs_checked += 1
                        
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
            similarity_check_time += time.time() - t0
            
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
        
        # Add summary statistics about potential tracking cookies
        t0 = time.time()
        self._add_potential_tracking_cookies_summary()
        summary_time = time.time() - t0
        
        total_time = time.time() - start_time
        
        self._log(f"Tracking cookies analysis performance:")
        self._log(f"  Total cookies analyzed: {cookies_analyzed}")
        self._log(f"  Total similarity pairs checked: {similarity_pairs_checked}")
        
        total_time = time.time() - start_time + 1e-10  # Add epsilon to avoid division by zero
        
        self._log(f"  Data collection: {collection_time:.2f}s ({collection_time/total_time*100:.1f}%)")
        self._log(f"  Persistence checks: {persistence_check_time:.2f}s ({persistence_check_time/total_time*100:.1f}%)")
        self._log(f"  Entropy/length checks: {entropy_check_time:.2f}s ({entropy_check_time/total_time*100:.1f}%)")
        self._log(f"  Similarity checks: {similarity_check_time:.2f}s ({similarity_check_time/total_time*100:.1f}%)")
        self._log(f"  Summary generation: {summary_time:.2f}s ({summary_time/total_time*100:.1f}%)")
        
        self._log(f"  Total tracking analysis time: {total_time:.2f}s")
        
        # Results summary
        self._log(f"Tracking cookies analysis results:")
        self._log(f"  Total potential trackers found: {potential_trackers_count}")
        self._log(f"  Failed persistence check: {failed_checks['persistent']}")
        self._log(f"  Failed entropy check: {failed_checks['entropy']}")
        self._log(f"  Failed length consistency check: {failed_checks['length']}")
        self._log(f"  Failed similarity check: {failed_checks['similarity']}")

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
        
        # Count cookies that are both shared AND potential identifiers
        shared_identifiers = 0
        shared_identifier_names = []

        if 'cookies' in self.data:
            for visit_cookies in self.data['cookies'].values():
                for cookie in visit_cookies:
                    if (cookie.get('is_potential_identifier', False) and 
                        cookie.get('shared_with_third_parties', False)):
                        shared_identifiers += 1
                        if cookie['name'] not in shared_identifier_names:
                            shared_identifier_names.append(cookie['name'])

        # Update the cookie_analysis summary
        if 'cookie_analysis' in self.data:
            self.data['cookie_analysis']['cookie_sharing'] = {
                'total_cookies_shared': len(cookie_sharing),
                'cookies_shared_with_third_parties': len(cookies_with_third_parties),
                'third_party_domains_receiving_cookies': list(third_party_domains),
                'shared_identifiers': {
                    'count': len(shared_identifier_names),
                    'names': shared_identifier_names
                }
            }

        # Log the findings
        self._log(f"\nFound {len(shared_identifier_names)} cookies that are both potential identifiers and shared with third parties:")
        for name in shared_identifier_names:
            self._log(f"  - {name}")

    def _analyze_storage_identifiers(self):
        """
        Identify localStorage and sessionStorage items that may be used for tracking.
        """
        if 'storage' not in self.data:
            return
        
        start_time = time.time()
        self._log("Analyzing storage for potential tracking identifiers...")
        
        # Track storage items across visits
        t0 = time.time()
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
        collection_time = time.time() - t0
        
        # Add verification print
        self._log(f"Found {len(storage_items['localStorage'])} unique localStorage keys")
        self._log(f"Found {len(storage_items['sessionStorage'])} unique sessionStorage keys")
        
        # Add detailed statistics to help troubleshoot
        for storage_type in ['localStorage', 'sessionStorage']:
            for key, values in storage_items[storage_type].items():
                if len(values) > 1:  # Only log keys with multiple values
                    max_value_length = max(len(str(v)) for v in values)
                    self._log(f"  {storage_type} key: '{key}' has {len(values)} values, max length: {max_value_length}")
                    if max_value_length > 1000:  # Log a warning for very long values
                        self._log(f"  WARNING: Very long value detected for {key}: {max_value_length} chars")
        
        # If no storage items found, return early
        if len(storage_items['localStorage']) == 0 and len(storage_items['sessionStorage']) == 0:
            self._log("No storage items to analyze, skipping storage analysis.")
            return
        
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
        
        # Timing for each type of check
        persistence_check_time = 0
        entropy_check_time = 0
        similarity_check_time = 0
        potential_trackers_count = 0
        
        # Tracking for performance monitoring
        total_items_analyzed = 0
        similarity_pairs_checked = 0
        simplified_comparisons = 0
        simplified_by_key = {}
        
        # Second pass: analyze each item for tracking characteristics
        self._log("Starting detailed storage analysis...")

        for storage_type in ['localStorage', 'sessionStorage']:
            self._log(f"Analyzing {storage_type} items...")
            keys_to_analyze = list(storage_items[storage_type].keys())
            
            for key_idx, key in enumerate(keys_to_analyze):
                values = storage_items[storage_type][key]
                total_items_analyzed += 1
                simplified_by_key[key] = 0  # Initialize counter for this key
                
                # Log progress periodically
                if key_idx % 5 == 0 or key_idx == len(keys_to_analyze) - 1:
                    self._log(f"  Processing {storage_type} key {key_idx+1}/{len(keys_to_analyze)}: '{key}'")
                
                # Skip if only one occurrence
                if len(values) <= 1:
                    continue
                
                # Step 1: Check persistence - localStorage is always persistent, sessionStorage never is
                t0 = time.time()
                persistent = (storage_type == 'localStorage')
                if not persistent:
                    failed_checks['session'] += 1
                    continue  # Skip sessionStorage items as they fail the first condition
                persistence_check_time += time.time() - t0
                
                # Step 2: Check entropy (length ≥ 8 bytes)
                t0 = time.time()
                try:
                    # Convert values to strings and get lengths
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
                except Exception as e:
                    self._log(f"Error in entropy check for key '{key}': {str(e)}")
                    continue
                entropy_check_time += time.time() - t0
                
                # Step 4: Check for similar values (similarity ≥ 60%)
                self._log(f"  Running similarity check for '{key}' with {len(values)} values...")
                t0 = time.time()
                values_similar = False
                if len(set(values)) > 1:  # If we have different values
                    # Calculate number of pairs to check
                    num_pairs = (len(values) * (len(values) - 1)) // 2
                    self._log(f"  Need to check {num_pairs} pairs for '{key}'")
                    

                    # Count similarity checks for analysis
                    pairs_checked = 0
                    local_simplified = 0  # Track simplified comparisons for this key
                    for i in range(len(values)):
                        for j in range(i+1, len(values)):
                            pairs_checked += 1
                            
                            if pairs_checked % 1000 == 0:
                                self._log(f"  Checked {pairs_checked}/{num_pairs} pairs for '{key}' (simplified: {local_simplified})")
                            
                            # Skip identical values
                            if values[i] == values[j]:
                                continue
                            
                            # Check if the strings are too long for reasonable comparison
                            len_i = len(str(values[i]))
                            len_j = len(str(values[j]))
                            if len_i > SIMPLIFIED_COMPARISON_THRESHOLD or len_j > SIMPLIFIED_COMPARISON_THRESHOLD:
                                tqdm.write(f"  Performing simplified comparison for long values ({len_i}, {len_j}) for '{key}'")
                                
                                # Simplified comparison: check prefix and suffix similarity
                                prefix_size = 100  # Compare first 100 chars
                                suffix_size = 100  # Compare last 100 chars
                                
                                str_i = str(values[i])
                                str_j = str(values[j])
                                
                                # Get prefix and suffix of each string
                                prefix_i = str_i[:prefix_size]
                                prefix_j = str_j[:prefix_size]
                                suffix_i = str_i[-suffix_size:] if len(str_i) >= suffix_size else str_i
                                suffix_j = str_j[-suffix_size:] if len(str_j) >= suffix_size else str_j
                                
                                # Calculate similarity of prefixes and suffixes
                                prefix_similarity = difflib.SequenceMatcher(None, prefix_i, prefix_j).ratio()
                                suffix_similarity = difflib.SequenceMatcher(None, suffix_i, suffix_j).ratio()
                                
                                # Consider similar if either prefix or suffix is similar
                                if prefix_similarity >= 0.6 or suffix_similarity >= 0.6:
                                    values_similar = True
                                    break
                                
                                # Count as simplified comparison for reporting purposes
                                simplified_comparisons += 1
                                local_simplified += 1
                                simplified_by_key[key] += 1
                                continue
                            
                            # Use difflib to calculate similarity ratio
                            try:
                                similarity_pairs_checked += 1
                                similarity = difflib.SequenceMatcher(None, str(values[i]), str(values[j])).ratio()
                                
                                # If values are similar but not identical (similarity ≥ 60%)
                                if similarity >= 0.6:
                                    values_similar = True
                                    break
                            except Exception as e:
                                self._log(f"  Error comparing values for '{key}': {str(e)}")
                                continue
                        if values_similar:
                            break
                    
                    self._log(f"  For key '{key}': checked {pairs_checked} pairs, used simplified comparison for {local_simplified} long values")
                
                self._log(f"  Completed similarity check for '{key}': {'similar' if values_similar else 'not similar'}")
                if not values_similar:
                    failed_checks['similarity'] += 1
                    continue
                similarity_check_time += time.time() - t0
                
                # If we reach here, all conditions are met
                potential_trackers_count += 1
                self._log(f"  Found potential tracking identifier: '{key}'")
                
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
        t0 = time.time()
        if 'storage_analysis' not in self.data:
            self.data['storage_analysis'] = {}
        
        # Extract the keys (names) of all potential identifiers
        local_storage_names = [item['key'] for item in potential_identifiers['localStorage']]
        session_storage_names = [item['key'] for item in potential_identifiers['sessionStorage']]
        
        # Add simplified comparisons to the storage analysis
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
        
        # Add performance data to the output
        self.data['storage_analysis']['performance'] = {
            'items_analyzed': total_items_analyzed,
            'similarity_pairs_checked': similarity_pairs_checked,
            'simplified_comparisons': simplified_comparisons,
            'simplified_by_key': {k: v for k, v in simplified_by_key.items() if v > 0}  # Only include keys with simplified comparisons
        }
        
        summary_time = time.time() - t0
        
        total_time = time.time() - start_time
        
        self._log(f"Storage analysis performance:")
        self._log(f"  Total items analyzed: {total_items_analyzed}")
        self._log(f"  Total similarity pairs checked: {similarity_pairs_checked}")
        self._log(f"  Total comparisons using simplified method: {simplified_comparisons}")
        
        # Show all keys where simplified comparisons were used
        for key, count in simplified_by_key.items():
            if count > 0:
                self._log(f"  - Used simplified comparison for {count} value pairs with key '{key}'")
        
        total_time = time.time() - start_time + 1e-10  # Add epsilon to avoid division by zero
        
        self._log(f"  Data collection: {collection_time:.2f}s ({collection_time/total_time*100:.1f}%)")
        self._log(f"  Persistence checks: {persistence_check_time:.2f}s ({persistence_check_time/total_time*100:.1f}%)")
        self._log(f"  Entropy/length checks: {entropy_check_time:.2f}s ({entropy_check_time/total_time*100:.1f}%)")
        self._log(f"  Similarity checks: {similarity_check_time:.2f}s ({similarity_check_time/total_time*100:.1f}%)")
        self._log(f"  Summary generation: {summary_time:.2f}s ({summary_time/total_time*100:.1f}%)")
        
        self._log(f"  Total storage analysis time: {total_time:.2f}s")
        
        self._log(f"Storage tracking analysis results:")
        self._log(f"  Total potential trackers found: {potential_trackers_count}")
        self._log(f"  Failed session/persistence check: {failed_checks['session']}")
        self._log(f"  Failed entropy check: {failed_checks['entropy']}")
        self._log(f"  Failed length consistency check: {failed_checks['length']}")
        self._log(f"  Failed similarity check: {failed_checks['similarity']}")

if __name__ == "__main__":
    # Directory with test files
    data_directory = 'data/Varies runs/test'
    
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