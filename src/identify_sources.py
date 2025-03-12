## https://github.com/ghostery/trackerdb


import os
import json
import dns.resolver
from datetime import datetime
import sys
from tqdm import tqdm
from urllib.parse import urlparse
from collections import Counter
sys.path.append('.')
from src.managers.ghostery_manager import analyze_request
from src.analyzers.check_filters import DomainFilterAnalyzer
from src.utils.domain_parser import get_base_domain, are_domains_related
from src.utils.public_suffix_updater import update_public_suffix_list
import functools
import pickle
import atexit
from cachetools import TTLCache, cached
import time

# Define the cache file path
CACHE_FILE = 'data/dns_cache.pickle'

# Initialize the DNS cache
dns_cache = TTLCache(maxsize=10000, ttl=3600)

def load_dns_cache():
    """Load DNS cache from file if it exists"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'rb') as f:
                cached_data = pickle.load(f)
                # Only load cache entries that haven't expired
                current_time = time.time()
                for key, (value, expire_time) in cached_data.items():
                    if expire_time > current_time:
                        dns_cache[key] = value
                print(f"Loaded {len(dns_cache)} DNS cache entries from {CACHE_FILE}")
    except Exception as e:
        print(f"Error loading DNS cache: {e}")

def save_dns_cache():
    """Save DNS cache to file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        
        # Save cache entries with their expiration times
        cache_with_ttl = {}
        for key in dns_cache:
            # Get the internal timer from the cache
            expire_time = dns_cache.timer() + dns_cache.ttl
            cache_with_ttl[key] = (dns_cache[key], expire_time)
        
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(cache_with_ttl, f)
        print(f"Saved {len(dns_cache)} DNS cache entries to {CACHE_FILE}")
    except Exception as e:
        print(f"Error saving DNS cache: {e}")

# Register the save function to run when the script exits
atexit.register(save_dns_cache)

def resolve_cname(domain):
    """Resolve CNAME record for a domain. Returns None if no CNAME found."""
    try:
        answers = dns.resolver.resolve(domain, 'CNAME')
        return str(answers[0].target)
    except Exception:
        return None

def get_ip_addresses(domain):
    """Get IP addresses for a domain using A record lookup with caching."""
    try:
        answers = dns.resolver.resolve(domain, 'A')
        return {str(rdata) for rdata in answers}
    except Exception:
        return set()

# Define the cache file path
CNAME_CACHE_FILE = 'data/cname_chain_cache.pickle'

# Create a dictionary to store our cache
cname_chain_cache = {}
cache_loaded = False

def load_cname_chain_cache():
    """Load CNAME chain cache from file if it exists"""
    global cname_chain_cache, cache_loaded
    if cache_loaded:
        return
        
    try:
        if os.path.exists(CNAME_CACHE_FILE):
            with open(CNAME_CACHE_FILE, 'rb') as f:
                loaded_cache = pickle.load(f)
                if isinstance(loaded_cache, dict):
                    cname_chain_cache.update(loaded_cache)
                    print(f"Loaded {len(cname_chain_cache)} CNAME chain cache entries")
                else:
                    cname_chain_cache = {}
        cache_loaded = True
    except Exception as e:
        print(f"Error loading CNAME chain cache: {e}")
        cname_chain_cache = {}
        cache_loaded = True

def save_cname_chain_cache():
    """Save CNAME chain cache to file"""
    try:
        # Only save if we have entries
        if not cname_chain_cache:
            return
            
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CNAME_CACHE_FILE), exist_ok=True)
        
        # Write cache to file
        with open(CNAME_CACHE_FILE, 'wb') as f:
            pickle.dump(cname_chain_cache, f)
    except Exception as e:
        print(f"Error saving CNAME chain cache: {e}")

# Register the save function to run on exit
atexit.register(save_cname_chain_cache)

def get_cname_chain(domain_analyzer, domain):
    """Follow and return the complete CNAME chain until we hit an A record.
    
    Results are cached to improve performance when the same domain is queried multiple times.
    The cache is persisted between program runs.
    """
    # Ensure cache is loaded (if not already)
    load_cname_chain_cache()
    
    # Normalize domain to ensure consistent caching
    domain = domain.lower().strip()
    cache_key = domain
    
    # Check if in cache
    if cache_key in cname_chain_cache:
        return cname_chain_cache[cache_key]
    
    # Not in cache, perform DNS lookups
    chain = []
    current = domain
    seen = set()  # Prevent infinite loops
    
    while True:
        cname = resolve_cname(current)
        if not cname or cname in seen:
            break
        chain.append(cname)
        seen.add(cname)
        current = cname
    
    # Store in cache and return
    result = tuple(chain)  # Convert to tuple for immutability
    cname_chain_cache[cache_key] = result
    return result

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

def get_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def check_tracking_cname(cname: str, tracking_list: list) -> bool:
    """Check if the CNAME resolution matches a known tracking domain"""
    if cname:
        for tracker in tracking_list:
            if tracker in cname:
                return True
    return False



def analyze_subdomain(domain_analyzer, main_site, base_url, request_count):
    """Analyze a single subdomain."""
    analysis_result = {
        'domain': base_url,
        'request_count': request_count,
        'is_first_party_domain': None,
        'tracking_type': None,
        'tracking_evidence': [],
        'categories': [],
        'organizations': [],
        'infrastructure_type': None,
        'provider': None,
        'cname_chain': []
    }
    
    # First determine if this is a first-party domain
    parsed_url = urlparse(base_url).netloc
    main_domain = main_site if '://' not in main_site else urlparse(main_site).netloc
    
    # Use are_domains_related to check first-party status
    try:
        if not domain_analyzer.public_suffixes:
            # Make sure we have public suffixes loaded
            domain_analyzer.public_suffixes = update_public_suffix_list()
        
        is_first_party = are_domains_related(
            main_domain, 
            parsed_url, 
            domain_analyzer.public_suffixes
        )
        analysis_result['is_first_party_domain'] = is_first_party
    except Exception as e:
        print(f"Error checking domain relationship: {e}")
        # Keep as None if there's an error
    
    # Check if URL matches filter rules
    filter_name, rule = domain_analyzer.is_domain_in_filters(base_url)
    if filter_name:
        analysis_result['tracking_type'] = 'filter_match'
        analysis_result['is_first_party_domain'] = False  # Override for known trackers
        analysis_result['tracking_evidence'].append(f"Domain found in {filter_name}: {rule}")
    
    # Check CNAME chain
    cname_chain = get_cname_chain(domain_analyzer, parsed_url)
    if cname_chain:
        analysis_result['cname_chain'] = cname_chain
        # Check each CNAME in chain against filters
        for cname in cname_chain:
            filter_name, rule = domain_analyzer.is_domain_in_filters(cname)
            if filter_name:
                analysis_result['tracking_type'] = 'cname_tracking'
                analysis_result['is_first_party_domain'] = False
                analysis_result['tracking_evidence'].append(f"CNAME chain member {cname} found in {filter_name}: {rule}")
    
    # Always check Ghostery DB for additional info
    tracker_info = get_tracker_categorization(parsed_url)
    if tracker_info:
        analysis_result['categories'] = tracker_info['categories']
        analysis_result['organizations'] = tracker_info['organizations']
        
        if 'Hosting' in tracker_info['categories']:
            analysis_result['infrastructure_type'] = 'hosting'
            analysis_result['provider'] = tracker_info['organizations'][0]
    
    return analysis_result

def initialize_site_analysis(file_path):
    """Initialize analysis for a site by loading data and counting requests."""
    # Load existing data
    site_data = load_json(file_path)
    
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
            base_url = get_base_url(request['url'])
            subdomain_requests[base_url] += 1
    
    # Set total analyzed to number of unique subdomains
    source_analysis['total_analyzed'] = len(subdomain_requests)
            
    return site_data, source_analysis, subdomain_requests

def finalize_site_analysis(site_data, source_analysis, file_path):
    """Finalize analysis by sorting results, saving data, and printing summary."""
    # Sort identified sources by request count (most frequent first)
    source_analysis['identified_sources'].sort(key=lambda x: x['request_count'], reverse=True)
    source_analysis['filter_matches'].sort(key=lambda x: x['request_count'], reverse=True)
    
    # Add analysis to site data
    site_data['source_analysis'] = source_analysis
    site_data['last_analyzed'] = datetime.now()
    
    # Save updated data
    save_json(site_data, file_path)
    
    # Print analysis summary
    print_analysis_summary(site_data, source_analysis)

def identify_site_sources(data_dir):
    """Identify the sources/origins of URLs in site data"""
    domain_analyzer = DomainFilterAnalyzer()
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    for filename in tqdm(json_files, desc="Analyzing sites", unit="site"):
        file_path = os.path.join(data_dir, filename)
        
        try:
            # Load site data
            site_data = load_json(file_path)
            
            # Get main site domain from the site_data
            main_site = site_data.get('domain', filename.replace('.json', ''))
            
            # Extract all requests based on the actual structure
            all_requests = []
            if 'network_data' in site_data and 'requests' in site_data['network_data']:
                all_requests = site_data['network_data']['requests']
            
            # Get unique domains
            unique_domains = set()
            for request in all_requests:
                if 'url' in request:
                    unique_domains.add(get_base_url(request['url']))
            
            # Skip if no domains found
            if not unique_domains:
                tqdm.write(f"No domains found in {filename}")
                continue
                
            tqdm.write(f"Found {len(unique_domains)} unique domains in {filename}")
            
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
                'organizations': Counter()  # Will count occurrences of each organization
            }
            
            # Analyze each unique domain
            analyzed_domains = {}
            with tqdm(total=len(unique_domains), desc=f"Analyzing domains in {filename}", leave=False) as pbar:
                for domain in unique_domains:
                    request_count = sum(1 for req in all_requests if get_base_url(req['url']) == domain)
                    analysis = analyze_subdomain(
                        domain_analyzer,
                        main_site,
                        domain,
                        request_count
                    )
                    analyzed_domains[domain] = analysis
                    
                    # Check for CNAME cloaking
                    has_cname_chain = bool(analysis['cname_chain'])
                    is_cname_cloaking = has_cname_chain and any(
                        "CNAME chain member" in evidence for evidence in analysis['tracking_evidence']
                    )
                    
                    # Update global filter match count
                    is_tracker = bool(analysis['tracking_evidence'])
                    if is_tracker:
                        stats['filter_matches'] += 1
                    
                    # Update CNAME cloaking stats
                    if is_cname_cloaking:
                        stats['cname_cloaking']['total'] += 1
                        # Record which trackers use cloaking (from CNAME chain)
                        for cname in analysis['cname_chain']:
                            tracker_info = get_tracker_categorization(cname)
                            if tracker_info:
                                for org in tracker_info['organizations']:
                                    stats['cname_cloaking']['trackers_using_cloaking'][org] += 1
                    
                    # Check if domain is first-party or third-party
                    if analysis['is_first_party_domain'] == True:
                        stats['first_party']['total'] += 1
                        
                        # Check if first-party domain is also a tracker
                        if is_tracker:
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
                        elif is_tracker:
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
            save_json(site_data, file_path)
            
            # Print summary statistics
            tqdm.write(f"\nStatistics for {main_site}:")
            tqdm.write(f"Total unique domains: {stats['total_domains']}")
            tqdm.write(f"Total tracking domains: {stats['filter_matches']} ({stats['filter_matches']/stats['total_domains']*100:.1f}%)")
            
            # CNAME cloaking statistics
            cname_total = stats['cname_cloaking']['total']
            if cname_total > 0:
                tqdm.write(f"CNAME cloaking detected: {cname_total} domains ({cname_total/stats['total_domains']*100:.1f}%)")
                if stats['cname_cloaking']['trackers_using_cloaking']:
                    tqdm.write("  Top trackers using CNAME cloaking:")
                    for tracker, count in sorted(stats['cname_cloaking']['trackers_using_cloaking'].items(), 
                                              key=lambda x: x[1], reverse=True)[:3]:
                        tqdm.write(f"  - {tracker}: {count}")
            
            # First-party breakdown
            first_party_total = stats['first_party']['total']
            tqdm.write(f"First-party domains: {first_party_total} ({first_party_total/stats['total_domains']*100:.1f}%)")
            if first_party_total > 0:
                trackers_total = stats['first_party']['trackers']['total']
                trackers_direct = stats['first_party']['trackers']['direct']
                trackers_cloaked = stats['first_party']['trackers']['cloaked']
                clean = stats['first_party']['clean']
                
                if trackers_total > 0:
                    tqdm.write(f"  - First-party trackers: {trackers_total} ({trackers_total/first_party_total*100:.1f}% of first-party)")
                    if trackers_direct > 0:
                        tqdm.write(f"    - Direct: {trackers_direct} ({trackers_direct/trackers_total*100:.1f}% of first-party trackers)")
                    if trackers_cloaked > 0:
                        tqdm.write(f"    - CNAME cloaked: {trackers_cloaked} ({trackers_cloaked/trackers_total*100:.1f}% of first-party trackers)")
                
                tqdm.write(f"  - Clean first-party: {clean} ({clean/first_party_total*100:.1f}% of first-party)")
            
            # Third-party breakdown
            third_party_total = stats['third_party']['total']
            tqdm.write(f"Third-party domains: {third_party_total} ({third_party_total/stats['total_domains']*100:.1f}%)")
            if third_party_total > 0:
                infra = stats['third_party']['infrastructure']
                trackers_total = stats['third_party']['trackers']['total']
                trackers_direct = stats['third_party']['trackers']['direct']
                trackers_cloaked = stats['third_party']['trackers']['cloaked']
                other = stats['third_party']['other']
                
                tqdm.write(f"  - Infrastructure (CDN/Hosting): {infra} ({infra/third_party_total*100:.1f}% of third-party)")
                
                if trackers_total > 0:
                    tqdm.write(f"  - Trackers: {trackers_total} ({trackers_total/third_party_total*100:.1f}% of third-party)")
                    if trackers_direct > 0:
                        tqdm.write(f"    - Direct: {trackers_direct} ({trackers_direct/trackers_total*100:.1f}% of trackers)")
                    if trackers_cloaked > 0:
                        tqdm.write(f"    - CNAME cloaked: {trackers_cloaked} ({trackers_cloaked/trackers_total*100:.1f}% of trackers)")
                
                tqdm.write(f"  - Other third-party: {other} ({other/third_party_total*100:.1f}% of third-party)")
            
            if stats['categories']:
                tqdm.write("\nTop categories:")
                for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    tqdm.write(f"  - {category}: {count} ({count/stats['total_domains']*100:.1f}%)")
            
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {str(e)}")
            import traceback
            tqdm.write(traceback.format_exc())  # Print the full error trace

def print_analysis_summary(site_data, source_analysis):
    """Print a summary of the source analysis results."""
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

def is_first_party_cname_chain(domain_analyzer, subdomain, main_site, cname_chain, public_suffixes, verbose=False):
    """Check if a CNAME chain is first-party.
    
    Args:
        subdomain: The full subdomain being checked (e.g., dnklry.plushbeds.com)
        main_site: The second-level domain (e.g., plushbeds.com)
        cname_chain: List of CNAMEs in resolution chain
        public_suffixes: List of public suffixes
        verbose: Whether to print debug information
    
    A chain is first-party if:
    1. Final CNAME matches main site domain, or
    2. IP addresses of final CNAME and main site match
    """
    if not cname_chain:
        return True
        
    # Get base domains using PSL
    main_base, main_suffix = get_base_domain(main_site, public_suffixes)
    final_cname = cname_chain[-1]
    final_base, final_suffix = get_base_domain(final_cname, public_suffixes)
    
    if verbose:
        print(f"\nFirst-party check debug:")
        print(f"Subdomain: {subdomain}")
        print(f"Main site: {main_site} -> base='{main_base}', suffix='{main_suffix}'")
        print(f"Final CNAME: {final_cname} -> base='{final_base}', suffix='{final_suffix}'")
    
    # Check if final CNAME matches main site domain
    domains_match = main_base == final_base and main_suffix == final_suffix
    if verbose:
        print(f"Domains match: {domains_match}")
    
    # Check IP addresses of main site (not subdomain) and final CNAME
    main_ips = get_ip_addresses(main_site)
    final_ips = get_ip_addresses(final_cname)
    
    if verbose:
        print(f"Main site IPs: {main_ips}")
        print(f"Final CNAME IPs: {final_ips}")
    
    ip_match = bool(main_ips & final_ips)
    if verbose:
        print(f"IP addresses match: {ip_match}")
    
    return domains_match or ip_match

def get_tracker_categorization(domain):
    """Get detailed categorization of a domain using Ghostery's trackerdb.
    
    Returns:
        dict: Dictionary containing categories and organizations found, or None if not identified
    """
    result = analyze_request(f"https://{domain}")
    if not result.get('matches'):
        return None
        
    categories = set()
    organizations = set()
    
    for match in result['matches']:
        categories.add(match['category']['name'])
        organizations.add(match['organization']['name'])
    
    return {
        'categories': list(categories),
        'organizations': list(organizations),
        'details': result['matches']
    }

def analyze_cname_chain(domain_analyzer, subdomain, main_site, cname_chain, public_suffixes, verbose=False):
    """Analyze each node in the CNAME chain for tracking behavior.
    First checks filter lists, then falls back to Ghostery for detailed categorization.
    
    Args:
        domain_analyzer: The analyzer instance
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
    
    if verbose:
        print("\nCNAME chain analysis:")
        print(f"Original: {subdomain}")
        for i, cname in enumerate(cname_chain, 1):
            print(f"  {i}. → {cname}")
    
    # First check if chain is first-party
    is_first_party = is_first_party_cname_chain(
        domain_analyzer,
        subdomain,
        main_site,
        cname_chain,
        public_suffixes,
        verbose=verbose
    )
    
    if verbose:
        print(f"\nIs first-party chain? {is_first_party}")
    
    if not is_first_party:
        if verbose:
            print("\nAnalyzing domains for tracking behavior:")
        
        # Check the original subdomain
        if verbose:
            print(f"\nOriginal domain: {subdomain}")
        filter_name, rule = domain_analyzer.is_domain_in_filters(subdomain)
        if filter_name:
            if verbose:
                print(f"  Found in filter: {filter_name}")
                print(f"  Matching rule: {rule}")
            evidence.append(f"{subdomain} found in {filter_name}")
        
        # Always check Ghostery for categorization
        tracker_info = get_tracker_categorization(subdomain)
        if tracker_info:
            categorization[subdomain] = tracker_info
            if verbose:
                print(f"  Categories: {', '.join(tracker_info['categories'])}")
                print(f"  Organizations: {', '.join(tracker_info['organizations'])}")
            evidence.append(f"{subdomain} identified as {'/'.join(tracker_info['categories'])} tracker by Ghostery")
        elif verbose:
            print("  No Ghostery matches found")
        
        # Check each CNAME in the chain
        for cname in cname_chain:
            if verbose:
                print(f"\nAnalyzing CNAME: {cname}")
            filter_name, rule = domain_analyzer.is_domain_in_filters(cname)
            if filter_name:
                if verbose:
                    print(f"  Found in filter: {filter_name}")
                    print(f"  Matching rule: {rule}")
                evidence.append(f"{cname} found in {filter_name}")
            
            # Always check Ghostery for categorization
            tracker_info = get_tracker_categorization(cname)
            if tracker_info:
                categorization[cname] = tracker_info
                if verbose:
                    print(f"  Categories: {', '.join(tracker_info['categories'])}")
                    print(f"  Organizations: {', '.join(tracker_info['organizations'])}")
                evidence.append(f"{cname} identified as {'/'.join(tracker_info['categories'])} tracker by Ghostery")
            elif verbose:
                print("  No Ghostery matches found")
    
    # Flag as tracking if any node in the chain was identified as a tracker
    is_tracking = len(evidence) > 0
    
    if is_tracking and verbose:
        print("\nCNAME chain classified as tracking due to:")
        for finding in evidence:
            print(f"- {finding}")
        
        print("\nDetailed categorization:")
        for domain, info in categorization.items():
            print(f"\n{domain}:")
            print(f"  Categories: {', '.join(info['categories'])}")
            print(f"  Organizations: {', '.join(info['organizations'])}")
    
    return is_tracking, evidence, categorization

def is_cdn_or_hosting(tracker_info: dict) -> bool:
    """Check if a domain is categorized as hosting/CDN infrastructure."""
    if not tracker_info:
        return False
        
    return 'Hosting' in tracker_info['categories']

if __name__ == "__main__":
    # Load the DNS cache at startup
    load_dns_cache()
    
    data_directory = 'data/crawler_data/i_dont_care_about_cookies'
    
    # Validate directory exists
    if not os.path.exists(data_directory):
        print(f"Error: Directory not found: {data_directory}")
        print("Please ensure the data directory exists before running the script.")
        sys.exit(1)
    
    identify_site_sources(data_directory)