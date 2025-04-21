## https://github.com/ghostery/trackerdb

import os
import json
import dns.resolver
from datetime import datetime
import sys
from tqdm import tqdm
from urllib.parse import urlparse
from collections import Counter
import pickle
sys.path.append('.')
from src.managers.ghostery_manager import GhosteryManager
from src.analyzers.filter_manager import FilterManager
from src.utils.domain_parser import get_base_domain, are_domains_related
from src.utils.public_suffix_updater import update_public_suffix_list
from src.managers.dns_resolver import DNSResolver

class SourceIdentifier:
    def __init__(self, verbose=False, use_cache=True):
        """Initialize the SourceIdentifier with all required dependencies."""
        self.filter_manager = FilterManager()
        self.ghostery = GhosteryManager()
        self.dns_resolver = DNSResolver()
        self.verbose = verbose
        self.use_cache = use_cache
        
        # Initialize the subdomain analysis cache
        self.subdomain_analysis_cache = {}
        self.subdomain_cache_file = 'data/subdomain_analysis_cache.pickle'
        self._load_analysis_cache()
        
        # Register cleanup on exit
        import atexit
        atexit.register(self._save_analysis_cache)

    def _log(self, message):
        """Log a message if verbose is True."""
        if self.verbose:
            tqdm.write(message)
           
           
    def _load_json(self, file_path):
        """Load JSON data from file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_json(self, data, file_path):
        """Save data to JSON file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)

    def _get_base_url(self, url: str) -> str:
        """Extract the base URL from a full URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _check_tracking_cname(self, cname: str, tracking_list: list) -> bool:
        """Check if the CNAME resolution matches a known tracking domain."""
        if cname:
            for tracker in tracking_list:
                if tracker in cname:
                    return True
        return False

    def _load_analysis_cache(self):
        """Load subdomain analysis cache from file."""
        try:
            if os.path.exists(self.subdomain_cache_file):
                with open(self.subdomain_cache_file, 'rb') as f:
                    self.subdomain_analysis_cache = pickle.load(f)
                self._log(f"Loaded {len(self.subdomain_analysis_cache)} subdomain analysis entries from cache")
        except Exception as e:
            self._log(f"Error loading subdomain analysis cache: {e}")
            self.subdomain_analysis_cache = {}

    def _save_analysis_cache(self):
        """Save subdomain analysis cache to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.subdomain_cache_file), exist_ok=True)
            
            with open(self.subdomain_cache_file, 'wb') as f:
                pickle.dump(self.subdomain_analysis_cache, f)
            
            self._log(f"Saved {len(self.subdomain_analysis_cache)} subdomain analysis entries to cache")
        except Exception as e:
            tqdm.write(f"Error saving subdomain analysis cache: {e}")

    def _get_cache_key(self, main_site, domain):
        """Generate a cache key for subdomain analysis."""
        # Normalize both domains to ensure consistent caching
        main_site = main_site.lower().strip()
        domain = domain.lower().strip()
        return f"{main_site}:{domain}"

    def _analyze_subdomain(self, main_site, base_url, request_count):
        """Analyze a single subdomain."""
        # Always generate the cache key, even if skipping cache read
        cache_key = self._get_cache_key(main_site, base_url)
        skip_cache = True
        
        if not skip_cache and self.use_cache and cache_key in self.subdomain_analysis_cache:
            cached_result = self.subdomain_analysis_cache[cache_key].copy()
            # Update the request count which can change
            cached_result['request_count'] = request_count
            self._log(f"Cache hit for {base_url} (main site: {main_site})")
            return cached_result
            
        # Perform full analysis if not cached
        parsed_url = urlparse(base_url).netloc
        
        self._log(f"\n==== Domain Analysis Debug: {parsed_url} ====")
        
        analysis_result = {
            'domain': base_url,
            'request_count': request_count,
            'is_first_party_domain': False,
            'filter_match': False,
            'is_tracker': False,
            'tracking_method': None,
            'cname_cloaking': False,
            'analysis_notes': [],
            'categories': [],
            'organizations': [],
            'cname_chain': []
        }
        
        # Check if URL matches filter rules
        self._log(f"Checking if domain matches filter rules...")
        filter_name, rule = self.filter_manager.is_domain_in_filters(base_url)
        if filter_name:
            analysis_result['filter_match'] = True
            analysis_result['is_tracker'] = True
            analysis_result['tracking_method'] = 'filter_list'
            analysis_result['analysis_notes'].append(f"Domain found in {filter_name}: {rule}")
        else:
            self._log(f"No filter match for {parsed_url}")
        
        # Get categorization info
        domain_info = self._get_tracker_categorization(parsed_url)
        if domain_info:
            if 'categories' in domain_info and domain_info['categories']:
                analysis_result['categories'] = domain_info['categories']
                self._log(f"Categories: {domain_info['categories']}")
                
                # Consider certain categories as tracking by nature
                tracking_categories = ['Advertising', 'Analytics', 'Social Network']
                if any(cat in tracking_categories for cat in domain_info['categories']):
                    self._log(f">>> GHOSTERY CATEGORY MATCH: {parsed_url} is categorized as {', '.join(domain_info['categories'])}")
                    analysis_result['is_tracker'] = True
                    # Only update tracking_method if not already set by filter list
                    if not analysis_result['tracking_method']:
                        analysis_result['tracking_method'] = 'categorized_tracker'
                    analysis_result['analysis_notes'].append(f"Domain categorized as {', '.join(domain_info['categories'])} by Ghostery")
            
            if 'organizations' in domain_info and domain_info['organizations']:
                analysis_result['organizations'] = domain_info['organizations']
                self._log(f"Organizations: {domain_info['organizations']}")
        
        # First determine if this is a first-party domain using domain structure
        main_domain = main_site if '://' not in main_site else urlparse(main_site).netloc
        
        self._log(f"\n==== FIRST-PARTY CHECK FOR {parsed_url} ====")
        self._log(f"Main domain: {main_domain}")

        try:
            # Ensure public suffixes are loaded - only update if empty
            if not self.filter_manager.public_suffixes:
                self.filter_manager.public_suffixes = update_public_suffix_list()
            
            # Call are_domains_related with proper parameters
            domain_related = are_domains_related(
                main_domain, 
                parsed_url, 
                self.filter_manager.public_suffixes
            )
            
            if domain_related:
                analysis_result['is_first_party_domain'] = True
                analysis_result['analysis_notes'].append(f"FIRST-PARTY: Domain related by name structure")
            else:
                # Check for organizational match if not related by domain structure
                # Get main site organizations
                main_site_info = self._get_tracker_categorization(main_domain)
                main_site_orgs = main_site_info.get('organizations', []) if main_site_info else []
                
                # Get domain organizations
                domain_orgs = domain_info.get('organizations', []) if domain_info else []
                
                # Compare organizations
                if main_site_orgs and domain_orgs:
                    # Check if any organization matches
                    org_match = any(org in main_site_orgs for org in domain_orgs)
                    
                    if org_match:
                        analysis_result['is_first_party_domain'] = True
                        match_org = next((org for org in domain_orgs if org in main_site_orgs), None)
                        analysis_result['analysis_notes'].append(
                            f"Domain belongs to same organization ({match_org}) as main site"
                        )
        except Exception as e:
            self._log(f"Error checking first-party status: {str(e)}")
        
        # Check CNAME chain (with debugging)
        is_browser_extension = base_url.startswith(('chrome-extension://', 'chrome://', 'edge://', 'brave://', 'about:'))
        
        if not is_browser_extension:
            try:
                self._log(f"Checking CNAME chain for {parsed_url}...")
                cname_chain = self.dns_resolver.get_cname_chain(parsed_url)
                if cname_chain:
                    self._log(f"CNAME chain found: {cname_chain}")
                    analysis_result['cname_chain'] = cname_chain
                    analysis_result['cname_cloaking'] = bool(cname_chain)
                    
                    # Track whether we've found cloaking
                    cname_cloaking_detected = False
                    
                    # For each CNAME in the chain
                    for cname in cname_chain:
                        # Check filter lists
                        filter_name, rule = self.filter_manager.is_domain_in_filters(cname)
                        if filter_name:
                            # Found in filter list
                            analysis_result['analysis_notes'].append(f"CNAME chain member {cname} found in {filter_name}: {rule}")
                            
                            # If this is a first-party domain, this is cloaking
                            if analysis_result['is_first_party_domain']:
                                cname_cloaking_detected = True
                                analysis_result['analysis_notes'].append(f"CNAME CLOAKING DETECTED: First-party domain using tracker in CNAME chain")
                        
                        # Check for organizational difference
                        cname_info = self._get_tracker_categorization(cname)
                        if cname_info and 'organizations' in cname_info:
                            cname_orgs = cname_info.get('organizations', [])
                            main_site_info = self._get_tracker_categorization(main_domain)
                            main_site_orgs = main_site_info.get('organizations', []) if main_site_info else []
                            
                            # Different organization in CNAME chain
                            if cname_orgs and not any(org in main_site_orgs for org in cname_orgs):
                                analysis_result['analysis_notes'].append(
                                    f"CNAME chain member {cname} belongs to different organization ({', '.join(cname_orgs)})"
                                )
                                
                                # Check if it's a tracking category
                                tracking_categories = ['Advertising', 'Analytics', 'Social Network']
                                cname_categories = cname_info.get('categories', [])
                                
                                is_tracking_category = any(cat in tracking_categories for cat in cname_categories)
                                
                                # If first-party domain + different org + tracking category = cloaking
                                if analysis_result['is_first_party_domain'] and is_tracking_category:
                                    cname_cloaking_detected = True
                                    analysis_result['analysis_notes'].append(
                                        f"CNAME CLOAKING DETECTED: First-party domain using {', '.join([cat for cat in cname_categories if cat in tracking_categories])} service in CNAME chain"
                                    )
            
                    # Set the cloaking flag if detected
                    analysis_result['cname_cloaking'] = cname_cloaking_detected
            except Exception as e:
                self._log(f"Error checking CNAME chain: {e}")
        
        self._log(f"Final analysis for {parsed_url}:")
        self._log(f"  - First-party: {analysis_result['is_first_party_domain']}")
        self._log(f"  - Filter match: {analysis_result['filter_match']}")
        self._log(f"  - CNAME match: {bool(analysis_result['cname_chain'])}")
        self._log(f"  - Tracking evidence: {analysis_result['analysis_notes']}")
        self._log("==== End Domain Analysis ====\n")
        
        # Store in cache for future use
        if self.use_cache:
            self.subdomain_analysis_cache[cache_key] = analysis_result.copy()
        
        return analysis_result

    def _initialize_site_analysis(self, file_path):
        """Initialize analysis for a site by loading data and counting requests."""
        # Load existing data
        site_data = self._load_json(file_path)
        
        # Initialize analysis stats
        source_analysis = {
            'total_analyzed': 0,  # This will be set to len(subdomain_requests)
            'source_categories': {},
            'source_owners': {},
            'identified_sources': [],
            'filter_matches': []
        }
        
        # Count requests per subdomain
        subdomain_requests = Counter()
        for page_data in site_data['pages'].values():
            for request in page_data.get('requests', []):
                base_url = self._get_base_url(request['url'])
                subdomain_requests[base_url] += 1
        
        # Set total analyzed to number of unique subdomains
        source_analysis['total_analyzed'] = len(subdomain_requests)
                
        return site_data, source_analysis, subdomain_requests

    def _finalize_site_analysis(self, site_data, source_analysis, file_path):
        """Finalize analysis by sorting results, saving data, and printing summary."""
        # Sort identified sources by request count (most frequent first)
        source_analysis['identified_sources'].sort(key=lambda x: x['request_count'], reverse=True)
        source_analysis['filter_matches'].sort(key=lambda x: x['request_count'], reverse=True)
        
        # Add analysis to site data
        site_data['source_analysis'] = source_analysis
        site_data['last_analyzed'] = datetime.now()
        
        # Save updated data
        self._save_json(site_data, file_path)
        
        # Print analysis summary
        if self.verbose:
            self._print_analysis_summary(site_data, source_analysis)

    def identify_site_sources(self, data_dir):
        """Identify the sources/origins of URLs in site data (public method)."""
        json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
        
        for filename in tqdm(json_files, desc="Analysing Sources", unit="site"):
            file_path = os.path.join(data_dir, filename)
            
            try:
                # Load site data
                site_data = self._load_json(file_path)
                
                # Get main site domain from the site_data
                main_site = site_data.get('domain', filename.replace('.json', ''))
                
                # Extract all requests based on the new structure
                all_requests = []
                if 'network_data' in site_data and '1' in site_data['network_data'] and 'requests' in site_data['network_data']['1']:
                    all_requests = site_data['network_data']['1']['requests']
                
                # Get unique domains
                unique_domains = set()
                for request in all_requests:
                    if 'url' in request:
                        unique_domains.add(self._get_base_url(request['url']))
                
                # Skip if no domains found
                if not unique_domains:
                    self._log(f"No domains found in {filename}")
                    continue
                    
                self._log(f"Found {len(unique_domains)} unique domains in {filename}")
                
                # Initialize statistics
                stats = {
                    'total_domains': len(unique_domains),
                    'filter_matches': 0,
                    'cname_cloaking': {
                        'total': 0,
                        'trackers_using_cloaking': Counter(),  # Which trackers use CNAME cloaking
                    },
                    'first_party': {
                        'total': 0,
                        'trackers': {
                            'total': 0,
                            'direct': 0,      # Direct first-party trackers
                            'cloaked': 0      # First-party trackers using CNAME cloaking
                        },
                        'clean': 0            # Non-tracking first-party domains
                    },
                    'third_party': {
                        'total': 0,
                        'infrastructure': 0,    # CDNs, hosting, etc.
                        'trackers': {
                            'total': 0,
                            'direct': 0,        # Direct third-party trackers
                            'cloaked': 0        # Third-party trackers using CNAME cloaking
                        },
                        'other': 0              # Other third-party domains
                    },
                    'categories': Counter(),    # Will count occurrences of each category
                    'organizations': Counter(),  # Will count occurrences of each organization
                    'trackers': {
                        'total': 0,
                        'filter_list_matches': 0,
                        'category_based': 0,
                        'organization_based': 0
                    }
                }
                
                # Count the number of requests per domain
                domain_request_count = Counter()
                for request in all_requests:
                    if 'url' in request:
                        base_url = self._get_base_url(request['url'])
                        domain_request_count[base_url] += 1
                
                # Analyze each unique domain
                analyzed_domains = {}
                
                with tqdm(total=len(unique_domains), desc=f"Analyzing domains for {main_site}", 
                        unit="domain", leave=False, disable=not self.verbose) as pbar:
                    for domain in unique_domains:
                        # Get request count for this domain
                        request_count = domain_request_count.get(domain, 0)
                        
                        # Analyze domain
                        analysis = self._analyze_subdomain(main_site, domain, request_count)
                        analyzed_domains[domain] = analysis
                        
                        # Check for CNAME cloaking
                        has_cname_chain = bool(analysis['cname_chain'])
                        is_cname_cloaking = False
                        
                        # Only consider CNAME cloaking for first-party domains
                        if analysis['is_first_party_domain'] and has_cname_chain:
                            # Check if any CNAME in the chain is a known tracker
                            cname_filter_evidence = any(
                                "CNAME chain member" in evidence and "found in" in evidence
                                for evidence in analysis['analysis_notes']
                            )
                            
                            if cname_filter_evidence:
                                # This is true CNAME cloaking: first-party domain pointing to third-party tracker
                                is_cname_cloaking = True
                                stats['cname_cloaking']['total'] += 1
                                
                                # Record organizations behind the cloaking
                                for cname in analysis['cname_chain']:
                                    cname_info = self._get_tracker_categorization(cname)
                                    if cname_info:
                                        for org in cname_info.get('organizations', []):
                                            stats['cname_cloaking']['trackers_using_cloaking'][org] += 1
                        
                        # Update global filter match count
                        if analysis['filter_match']:  # Only count direct filter list matches
                            stats['filter_matches'] += 1
                        
                        # Check if domain is first-party or third-party
                        if analysis['is_first_party_domain'] == True:
                            stats['first_party']['total'] += 1
                            
                            # Check if first-party domain is also a tracker
                            if analysis['filter_match']:
                                stats['first_party']['trackers']['total'] += 1
                                
                                if is_cname_cloaking:
                                    stats['first_party']['trackers']['cloaked'] += 1
                                else:
                                    stats['first_party']['trackers']['direct'] += 1
                            else:
                                stats['first_party']['clean'] += 1
                                
                        elif analysis['is_first_party_domain'] == False:
                            stats['third_party']['total'] += 1
                            
                            # Determine third-party type
                            is_infrastructure = 'Hosting' in analysis['categories'] or 'CDN' in analysis['categories']
                            
                            if is_infrastructure:
                                stats['third_party']['infrastructure'] += 1
                            elif analysis['filter_match']:
                                stats['third_party']['trackers']['total'] += 1
                                
                                if is_cname_cloaking:
                                    stats['third_party']['trackers']['cloaked'] += 1
                                else:
                                    stats['third_party']['trackers']['direct'] += 1
                            else:
                                stats['third_party']['other'] += 1
                        
                        # Count categories
                        for category in analysis['categories']:
                            stats['categories'][category] += 1
                        
                        # Count organizations
                        for org in analysis['organizations']:
                            stats['organizations'][org] += 1
                        
                        # Update trackers
                        if analysis.get('is_tracker', False):
                            stats['trackers']['total'] += 1
                            
                            # Count by detection method
                            method = analysis.get('tracking_method', '')
                            if method == 'filter_list':
                                stats['trackers']['filter_list_matches'] += 1
                            elif method == 'categorized_tracker':
                                stats['trackers']['category_based'] += 1
                            elif method == 'organization_difference':
                                stats['trackers']['organization_based'] += 1
                        
                        pbar.update(1)
                
                # Convert counters to dictionaries for JSON serialization
                stats['categories'] = dict(stats['categories'])
                stats['organizations'] = dict(stats['organizations'])
                stats['cname_cloaking']['trackers_using_cloaking'] = dict(stats['cname_cloaking']['trackers_using_cloaking'])
                
                # Save results
                site_data['domain_analysis'] = {
                    'analyzed_at': datetime.now().isoformat(),
                    'domains': list(analyzed_domains.values()),
                    'statistics': stats
                }
                self._save_json(site_data, file_path)
                
            except Exception as e:
                tqdm.write(f"Error processing {filename}: {str(e)}")
                import traceback
                tqdm.write(traceback.format_exc())  # Print the full error trace

    def _print_analysis_summary(self, site_data, source_analysis):
        """Print a summary of the source analysis results (private method)."""
        tqdm.write(f"\nResults for {site_data.get('domain', 'unknown domain')}:")
        tqdm.write(f"Unique domains analyzed: {source_analysis['total_analyzed']}")
        tqdm.write(f"Identified sources: {len([s for s in source_analysis['identified_sources'] if s['category'] != 'unidentified'])}")
        
        # Print Ghostery matches
        tqdm.write("\nTop 5 most frequent identified sources:")
        for source in [s for s in source_analysis['identified_sources'] if s['category'] != 'unidentified'][:5]:
            tqdm.write(f"  - {source['domain']}: {source['request_count']} requests ({source['category']})")
        
        # Print unidentified domains
        unidentified = [s for s in source_analysis['identified_sources'] if s['category'] == 'unidentified']
        if unidentified:
            tqdm.write("\nUnidentified domains:")
            for source in unidentified:
                tqdm.write(f"  - {source['domain']}: {source['request_count']} requests")
        
        # Print filter matches
        if source_analysis['filter_matches']:
            tqdm.write("\nFilter list matches:")
            for match in source_analysis['filter_matches']:
                status = "direct tracker" if match['is_direct_tracker'] else "cloaked tracker"
                cname_info = f" -> {match['cname_resolution']}" if match['is_cname_cloaked'] else ""
                tqdm.write(f"  - {match['url']}{cname_info} ({status})")

    def _is_first_party_cname_chain(self, subdomain, main_site, cname_chain, public_suffixes, verbose=False):
        """Check if a CNAME chain is first-party.
        
        Args:
            subdomain: The full subdomain being checked (e.g., dnklry.plushbeds.com)
            main_site: The second-level domain (e.g., plushbeds.com)
            cname_chain: List of CNAMEs in resolution chain
            public_suffixes: List of public suffixes
            verbose: Whether to print debug information
        
        A chain is first-party if the final CNAME matches main site domain
        """
        if not cname_chain:
            return True
            
        # Get base domains using PSL
        main_base, main_suffix = get_base_domain(main_site, public_suffixes)
        final_cname = cname_chain[-1]
        final_base, final_suffix = get_base_domain(final_cname, public_suffixes)
        

        self._log(f"\nFirst-party check debug:")
        self._log(f"Subdomain: {subdomain}")
        self._log(f"Main site: {main_site} -> base='{main_base}', suffix='{main_suffix}'")
        self._log(f"Final CNAME: {final_cname} -> base='{final_base}', suffix='{final_suffix}'")
        
        # Check if final CNAME matches main site domain
        domains_match = main_base == final_base and main_suffix == final_suffix
        self._log(f"Domains match: {domains_match}")
        
        return domains_match

    def _get_tracker_categorization(self, domain):
        """Get detailed categorization of a domain using Ghostery's trackerdb."""
        result = self.ghostery.analyze_request(f"https://{domain}")
        
        if result.get('matches'):
            categories = set()
            organizations = set()
            
            for match in result['matches']:
                if match.get('category') and match['category'].get('name'):
                    categories.add(match['category']['name'])
                if match.get('organization') and match['organization'].get('name'):
                    organizations.add(match['organization']['name'])
            
            return {
                'categories': list(categories),
                'organizations': list(organizations),
                'details': result['matches']
            }
        
        return None

    def _analyze_cname_chain(self, subdomain, main_site, cname_chain, public_suffixes, verbose=False):
        """Analyze each node in the CNAME chain for tracking behavior.
        First checks filter lists, then falls back to Ghostery for detailed categorization.
        
        Args:
            subdomain: The subdomain being analyzed
            main_site: The main site domain
            cname_chain: List of CNAMEs in the resolution chain
            public_suffixes: List of public suffixes
            verbose: Whether to print detailed analysis information
        
        Returns:
            tuple: (is_tracking, evidence, categorization)
        """
        if not cname_chain:
            return False, [], {}
        
        evidence = []
        categorization = {}
        
        self._log(f"\nCNAME chain analysis:")
        self._log(f"Original: {subdomain}")
        for i, cname in enumerate(cname_chain, 1):
            self._log(f"  {i}. → {cname}")
        
        # First check if chain is first-party
        is_first_party = self._is_first_party_cname_chain(
            subdomain,
            main_site,
            cname_chain,
            public_suffixes,
            verbose=verbose
        )
        
        self._log(f"\nIs first-party chain? {is_first_party}")
        
        if not is_first_party:
            self._log("\nAnalyzing domains for tracking behavior:")
            
            # Check the original subdomain
            filter_name, rule = self.filter_manager.is_domain_in_filters(subdomain)
            if filter_name:
                self._log(f"  Found in filter: {filter_name}")
                self._log(f"  Matching rule: {rule}")
                evidence.append(f"{subdomain} found in {filter_name}")
            
            # Always check Ghostery for categorization
            tracker_info = self._get_tracker_categorization(subdomain)
            if tracker_info:
                categorization[subdomain] = tracker_info
                self._log(f"  Categories: {', '.join(tracker_info['categories'])}")
                self._log(f"  Organizations: {', '.join(tracker_info['organizations'])}")
                evidence.append(f"{subdomain} identified as {'/'.join(tracker_info['categories'])} tracker by Ghostery")
            else:
                self._log("  No Ghostery matches found")
            
            # Check each CNAME in the chain
            for cname in cname_chain:
                self._log(f"\nAnalyzing CNAME: {cname}")
                filter_name, rule = self.filter_manager.is_domain_in_filters(cname)
                if filter_name:
                    self._log(f"  Found in filter: {filter_name}")
                    self._log(f"  Matching rule: {rule}")
                    evidence.append(f"{cname} found in {filter_name}")
                
                # Always check Ghostery for categorization
                tracker_info = self._get_tracker_categorization(cname)
                if tracker_info:
                    categorization[cname] = tracker_info
                    self._log(f"  Categories: {', '.join(tracker_info['categories'])}")
                    self._log(f"  Organizations: {', '.join(tracker_info['organizations'])}")
                    evidence.append(f"{cname} identified as {'/'.join(tracker_info['categories'])} tracker by Ghostery")
                else:
                    self._log("  No Ghostery matches found")
        
        # Flag as tracking if any node in the chain was identified as a tracker
        is_tracking = len(evidence) > 0
        
        if is_tracking and verbose:
            self._log("\nCNAME chain classified as tracking due to:")
            for finding in evidence:
                self._log(f"- {finding}")
            
            self._log("\nDetailed categorization:")
            for domain, info in categorization.items():
                self._log(f"\n{domain}:")
                self._log(f"  Categories: {', '.join(info['categories'])}")
                self._log(f"  Organizations: {', '.join(info['organizations'])}")
        
        return is_tracking, evidence, categorization

    def _is_cdn_or_hosting(self, tracker_info: dict) -> bool:
        """Check if a domain is categorized as hosting/CDN infrastructure (private method)."""
        if not tracker_info:
            return False
            
        return 'Hosting' in tracker_info['categories']


if __name__ == "__main__":
    data_directory = 'data/crawler_data Non-kameleo/test'
    
    # Validate directory exists
    if not os.path.exists(data_directory):
        tqdm.write(f"Error: Directory not found: {data_directory}")
        tqdm.write("Please ensure the data directory exists before running the script.")
        sys.exit(1)
    
    # Create the SourceIdentifier instance and run the analysis
    identifier = SourceIdentifier()
    identifier.identify_site_sources(data_directory)