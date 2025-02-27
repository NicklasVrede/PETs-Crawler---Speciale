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
from src.managers.ghostery_manager import analyze_request, check_organization_consistency
from src.analyzers.check_filters import DomainFilterAnalyzer
from utils.domain_parser import get_base_domain, are_domains_related
from utils.public_suffix_updater import update_public_suffix_list

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

def get_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def resolve_cname(domain: str) -> str:
    """Resolve the CNAME for a given domain"""
    try:
        answers = dns.resolver.resolve(domain, 'CNAME')
        for rdata in answers:
            return str(rdata.target).rstrip('.')
    except dns.resolver.NoAnswer:
        print(f"No CNAME record found for {domain}.")
    except dns.resolver.NXDOMAIN:
        print(f"Domain {domain} does not exist.")
    except dns.exception.Timeout:
        print(f"DNS query for {domain} timed out.")
    except Exception as e:
        print(f"An error occurred while resolving CNAME for {domain}: {e}")
    return None

def check_tracking_cname(cname: str, tracking_list: list) -> bool:
    """Check if the CNAME resolution matches a known tracking domain"""
    if cname:
        for tracker in tracking_list:
            if tracker in cname:
                return True
    return False

def analyze_subdomain(domain_analyzer, main_site, base_url, request_count):
    """Analyze a single subdomain for tracking behavior and ownership."""
    if not hasattr(domain_analyzer, 'public_suffixes'):
        domain_analyzer.public_suffixes = update_public_suffix_list()
    
    # Get base domains using PSL
    main_base, main_suffix = get_base_domain(main_site, domain_analyzer.public_suffixes)
    url_base, url_suffix = get_base_domain(base_url, domain_analyzer.public_suffixes)
    
    # Check if this is actually a subdomain of the main site
    is_subdomain = are_domains_related(main_site, base_url, domain_analyzer.public_suffixes)
    
    # Analyze the base URL using Ghostery database
    result = analyze_request(base_url)
    
    # Only check for CNAME cloaking if it's actually a subdomain
    is_cloaked = False
    is_direct_tracker = False
    cloaking_rule = None
    cname_resolution = None
    
    if is_subdomain:
        # Get CNAME resolution and check for cloaking
        parsed_url = urlparse(base_url).netloc
        cname_resolution = domain_analyzer.resolve_cname(parsed_url)
        
        if cname_resolution:
            # Check if CNAME points to a different domain
            is_third_party_cname = not are_domains_related(
                cname_resolution, 
                main_site, 
                domain_analyzer.public_suffixes
            )
            
            if is_third_party_cname:
                # Check if the CNAME destination is a known tracking domain
                is_cloaked, cloaking_rule, _ = domain_analyzer.check_for_cname_cloaking(cname_resolution)
    else:
        # If not a subdomain, check for direct tracking
        is_direct_tracker, cloaking_rule, _ = domain_analyzer.check_for_cname_cloaking(base_url)
    
    # Initialize filter analysis results
    filter_analysis = {
        'is_first_party': is_subdomain,
        'is_direct_tracker': is_direct_tracker,
        'is_cname_cloaked': is_cloaked,
        'cname_resolution': cname_resolution,
        'matching_rule': cloaking_rule
    }
    
    # Process Ghostery trackerdb matches
    identified_sources = []
    if result.get('matches'):
        for match in result['matches']:
            identified_sources.append({
                'domain': base_url,
                'is_first_party': is_subdomain,
                'request_count': request_count,
                'resource_type': match['pattern']['name'],
                'category': match['category']['name'],
                'organization': match['organization']['name'],
                'filter_analysis': filter_analysis,
                'details': match['pattern']
            })
    else:
        # Log unidentified subdomain
        identified_sources.append({
            'domain': base_url,
            'is_first_party': is_subdomain,
            'request_count': request_count,
            'resource_type': 'unknown',
            'category': 'unidentified',
            'organization': 'unknown',
            'filter_analysis': filter_analysis,
            'details': None
        })
    
    # Create filter match if applicable
    filter_match = None
    if is_cloaked or is_direct_tracker:
        filter_match = {
            'url': base_url,
            'is_first_party': is_subdomain,
            'request_count': request_count,
            'is_direct_tracker': is_direct_tracker,
            'is_cname_cloaked': is_cloaked,
            'cname_resolution': cname_resolution,
            'matching_rule': cloaking_rule
        }
    
    return {
        'identified_sources': identified_sources,
        'filter_match': filter_match,
        'categories': [match['category']['name'] for match in result.get('matches', [])],
        'owners': [match['organization']['name'] for match in result.get('matches', [])]
    }

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
    """Identify the sources/origins of URLs in site data using both Ghostery and filter analysis"""
    
    domain_analyzer = DomainFilterAnalyzer()
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    for filename in tqdm(json_files, desc="Analyzing sites", unit="site"):
        file_path = os.path.join(data_dir, filename)
        
        try:
            # Load site data
            site_data = load_json(file_path)
            main_site = site_data['pages']['homepage']['url']
            
            # Initialize analysis
            site_data, source_analysis, subdomain_requests = initialize_site_analysis(file_path)
            
            # Analyze each unique subdomain
            with tqdm(total=len(subdomain_requests), desc=f"Analyzing {filename}", leave=False) as pbar:
                for base_url, request_count in subdomain_requests.items():
                    analysis = analyze_subdomain(domain_analyzer, main_site, base_url, request_count)
                    
                    # Update categories and owners
                    for category in analysis['categories']:
                        source_analysis['source_categories'][category] = source_analysis['source_categories'].get(category, 0) + 1
                    for owner in analysis['owners']:
                        source_analysis['source_owners'][owner] = source_analysis['source_owners'].get(owner, 0) + 1
                    
                    # Add identified sources
                    source_analysis['identified_sources'].extend(analysis['identified_sources'])
                    
                    # Add filter match if present
                    if analysis['filter_match']:
                        source_analysis['filter_matches'].append(analysis['filter_match'])
                    
                    pbar.update(1)
            
            # Finalize and save analysis
            finalize_site_analysis(site_data, source_analysis, file_path)
            
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {str(e)}")

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

def get_cname_chain(domain_analyzer, domain):
    """Follow and return the complete CNAME chain until we hit an A record."""
    chain = []
    current = domain
    seen = set()  # Prevent infinite loops
    
    while True:
        cname = domain_analyzer.resolve_cname(current)
        if not cname or cname in seen:
            break
        chain.append(cname)
        seen.add(cname)
        current = cname
    
    return chain

def get_ip_addresses(domain):
    """Get IP addresses for a domain using A record lookup."""
    try:
        answers = dns.resolver.resolve(domain, 'A')
        return {str(rdata) for rdata in answers}
    except Exception as e:
        print(f"Error resolving IP for {domain}: {e}")
        return set()

def is_first_party_cname_chain(domain_analyzer, subdomain, main_site, cname_chain, public_suffixes):
    """Check if a CNAME chain is first-party.
    
    Args:
        subdomain: The full subdomain being checked (e.g., dnklry.plushbeds.com)
        main_site: The second-level domain (e.g., plushbeds.com)
        cname_chain: List of CNAMEs in resolution chain
    
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
    
    print(f"\nFirst-party check debug:")
    print(f"Subdomain: {subdomain}")
    print(f"Main site: {main_site} -> base='{main_base}', suffix='{main_suffix}'")
    print(f"Final CNAME: {final_cname} -> base='{final_base}', suffix='{final_suffix}'")
    
    # Check if final CNAME matches main site domain
    domains_match = main_base == final_base and main_suffix == final_suffix
    print(f"Domains match: {domains_match}")
    
    # Check IP addresses of main site (not subdomain) and final CNAME
    main_ips = get_ip_addresses(main_site)
    final_ips = get_ip_addresses(final_cname)
    
    print(f"Main site IPs: {main_ips}")
    print(f"Final CNAME IPs: {final_ips}")
    ip_match = bool(main_ips & final_ips)
    print(f"IP addresses match: {ip_match}")
    
    return domains_match or ip_match

def analyze_cname_chain(domain_analyzer, subdomain, main_site, cname_chain, public_suffixes):
    """Analyze each node in the CNAME chain for tracking behavior."""
    if not cname_chain:
        return
        
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
        public_suffixes
    )
    
    print(f"\nIs first-party chain? {is_first_party}")
    
    if not is_first_party:
        print("\nChecking each domain against tracking filters and Ghostery:")
        
        tracking_nodes = []
        
        # Check the original subdomain
        print(f"\nOriginal domain: {subdomain}")
        filter_name, rule = domain_analyzer.is_domain_in_filters(subdomain)
        if filter_name:
            print(f"  Found in filter: {filter_name}")
            print(f"  Matching rule: {rule}")
            tracking_nodes.append((subdomain, f"Filter: {filter_name}", rule))
        else:
            # Check Ghostery if not in filters
            result = analyze_request(subdomain)
            if result.get('matches'):
                for match in result['matches']:
                    print(f"  Found in Ghostery:")
                    print(f"    Category: {match['category']['name']}")
                    print(f"    Organization: {match['organization']['name']}")
                    tracking_nodes.append((
                        subdomain,
                        f"Ghostery: {match['category']['name']}",
                        match['organization']['name']
                    ))
            else:
                print("  No matches found")
        
        # Check each CNAME in the chain
        for i, cname in enumerate(cname_chain, 1):
            print(f"\nNode {i}: {cname}")
            filter_name, rule = domain_analyzer.is_domain_in_filters(cname)
            if filter_name:
                print(f"  Found in filter: {filter_name}")
                print(f"  Matching rule: {rule}")
                tracking_nodes.append((cname, f"Filter: {filter_name}", rule))
            else:
                # Check Ghostery if not in filters
                result = analyze_request(cname)
                if result.get('matches'):
                    for match in result['matches']:
                        print(f"  Found in Ghostery:")
                        print(f"    Category: {match['category']['name']}")
                        print(f"    Organization: {match['organization']['name']}")
                        tracking_nodes.append((
                            cname,
                            f"Ghostery: {match['category']['name']}",
                            match['organization']['name']
                        ))
                else:
                    print("  No matches found")

if __name__ == "__main__":
    # Regular execution
    data_directory = 'data/consent_o_matic_opt_out_non_headless'
    #identify_site_sources(data_directory)
    
    # Test domain processing
    print("\nTesting domain processing:")
    print("-" * 80)
    
    test_cases = [
        # (main_site, test_url, description)
        ("https://plushbeds.com", "https://dnklry.plushbeds.com", "Suspicious subdomain"),
        # Add more test cases here
    ]
    
    # Initialize domain analyzer and get public suffixes
    domain_analyzer = DomainFilterAnalyzer()
    public_suffixes = update_public_suffix_list()
    
    for main_site, test_url, description in test_cases:
        print(f"\nTesting: {description}")
        print(f"Main site: {main_site}")
        print(f"Test URL: {test_url}")
        
        # Parse domains using PSL
        main_base, main_suffix = get_base_domain(main_site, public_suffixes)
        test_base, test_suffix = get_base_domain(test_url, public_suffixes)
        
        # Check if domains are related
        is_related = are_domains_related(main_site, test_url, public_suffixes)
        
        print("\nDomain parsing results:")
        print(f"Main site: base='{main_base}', suffix='{main_suffix}'")
        print(f"Test URL: base='{test_base}', suffix='{test_suffix}'")
        print(f"Are domains related? {is_related}")
        
        # If related, analyze CNAME chain
        if is_related:
            parsed_url = urlparse(test_url).netloc
            cname_chain = get_cname_chain(domain_analyzer, parsed_url)
            
            if cname_chain:
                analyze_cname_chain(
                    domain_analyzer,
                    parsed_url,
                    f"{main_base}.{main_suffix}",
                    cname_chain,
                    public_suffixes
                )
            else:
                print("\nNo CNAME records found")
        
        print("-" * 80)