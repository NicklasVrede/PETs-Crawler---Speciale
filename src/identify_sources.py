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
from managers.ghostery_manager import analyze_request, check_organization_consistency
from analyzers.check_filters import DomainFilterAnalyzer

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

def analyze_subdomain(domain_analyzer, base_url, request_count):
    """Analyze a single subdomain for tracking behavior and ownership."""
    # Analyze the base URL using Ghostery database
    result = analyze_request(base_url)
    
    # Check for CNAME cloaking using the analyzer
    is_cloaked, cloaking_rule, is_direct_tracker = domain_analyzer.check_for_cname_cloaking(base_url)
    cname_resolution = domain_analyzer.resolve_cname(urlparse(base_url).netloc)
    
    # Initialize filter analysis results
    filter_analysis = {
        'is_direct_tracker': is_direct_tracker,
        'is_cname_cloaked': is_cloaked,
        'cname_resolution': cname_resolution,
        'matching_rule': cloaking_rule if is_cloaked else (cloaking_rule if is_direct_tracker else None)
    }
    
    # Process Ghostery trackerdb matches
    identified_sources = []
    for match in result.get('matches', []):
        identified_sources.append({
            'subdomain': base_url,
            'request_count': request_count,
            'resource_type': match['pattern']['name'],
            'category': match['category']['name'],
            'organization': match['organization']['name'],
            'filter_analysis': filter_analysis,
            'details': match['pattern']
        })
    
    # Create filter match if applicable
    filter_match = None
    if is_cloaked or is_direct_tracker:
        filter_match = {
            'url': base_url,
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

def identify_site_sources(data_dir):
    """Identify the sources/origins of URLs in site data using both Ghostery and filter analysis"""
    
    # Initialize the DomainFilterAnalyzer
    domain_analyzer = DomainFilterAnalyzer()
    
    # Get list of JSON files
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    # Process each JSON file in the directory with progress bar
    for filename in tqdm(json_files, desc="Analyzing sites", unit="site"):
        file_path = os.path.join(data_dir, filename)
        
        try:
            # Load existing data
            site_data = load_json(file_path)
            
            # Extract main site URL from the homepage
            main_site = site_data['pages']['homepage']['url']
            
            # Initialize analysis stats
            source_analysis = {
                'total_analyzed': 0,
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
            
            # Analyze each unique subdomain
            with tqdm(total=len(subdomain_requests), desc=f"Analyzing {filename}", leave=False) as pbar:
                for base_url, request_count in subdomain_requests.items():
                    analysis = analyze_subdomain(domain_analyzer, base_url, request_count)
                    
                    # Update source analysis
                    source_analysis['total_analyzed'] += 1
                    
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
            
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {str(e)}")

def print_analysis_summary(site_data, source_analysis):
    """Print a summary of the source analysis results."""
    tqdm.write(f"\nResults for {site_data.get('domain', 'unknown domain')}:")
    tqdm.write(f"Total analyzed subdomains: {source_analysis['total_analyzed']}")
    tqdm.write(f"Unique subdomains analyzed: {len(source_analysis['identified_sources'])}")
    
    # Print Ghostery matches
    tqdm.write("\nTop 5 most frequent subdomains (Ghostery):")
    for source in source_analysis['identified_sources'][:5]:
        tqdm.write(f"  - {source['subdomain']}: {source['request_count']} requests ({source['category']})")
    
    # Print filter matches
    if source_analysis['filter_matches']:
        tqdm.write("\nFilter list matches:")
        for match in source_analysis['filter_matches']:
            status = "direct tracker" if match['is_direct_tracker'] else "cloaked tracker"
            cname_info = f" -> {match['cname_resolution']}" if match['is_cname_cloaked'] else ""
            tqdm.write(f"  - {match['url']}{cname_info} ({status})")

if __name__ == "__main__":
    # Example usage
    data_directory = 'data/consent_o_matic_opt_out_non_headless'
    identify_site_sources(data_directory) 