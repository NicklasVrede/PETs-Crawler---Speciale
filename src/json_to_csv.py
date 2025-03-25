import os
import json
import csv
import re
from urllib.parse import urlparse
from collections import defaultdict

def extract_domain_from_url(url):
    """Extract base domain from URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Get base domain (e.g., example.com from sub.example.com)
        parts = domain.split('.')
        if len(parts) > 2:
            return '.'.join(parts[-2:])
        return domain
    except:
        return None

def count_unique_domains(requests):
    """Count unique domains in request data"""
    domains = set()
    for req in requests:
        if 'domain' in req:
            domains.add(req['domain'])
    return len(domains)

def count_third_party_requests(requests, base_domain):
    """Count requests to domains other than the base domain"""
    third_party = 0
    for req in requests:
        if 'domain' in req and base_domain not in req['domain']:
            third_party += 1
    return third_party

def get_resource_type_counts(requests):
    """Count requests by resource type"""
    types = {}
    for req in requests:
        if 'resource_type' in req:
            resource_type = req['resource_type']
            types[resource_type] = types.get(resource_type, 0) + 1
    return types

def count_filter_matches(requests):
    """
    Count potential filter list matches by checking request URLs
    against common patterns found in filter lists
    """
    # Simplified patterns from common filter lists like EasyList
    filter_patterns = [
        r'/(ads?|banner|pop|track|log|pixel|stat)([^a-z0-9]|$)',
        r'/(analytic|beacon|count|count|ping|tag|tracking|webtrends)([^a-z0-9]|$)',
        r'/(click|clk|counter|hit|lt|p?imp|posst|pv|view|viewt?)([^a-z0-9]|$)',
        r'/ga([.-]|$)',
        r'google-analytics',
        r'googletagmanager',
        r'facebook.*?/impression',
        r'doubleclick\.net',
        r'scorecardresearch\.com'
    ]
    
    filter_matches = 0
    for req in requests:
        url = req.get('url', '').lower()
        for pattern in filter_patterns:
            if re.search(pattern, url):
                filter_matches += 1
                break
    
    return filter_matches

def count_potential_cname_cloaking(requests, base_domain):
    """
    Estimate potential CNAME cloaking by looking for first-party domains
    loading typical tracker resources
    """
    potential_cname_candidates = 0
    first_party_domains = set()
    
    # Find all subdomains of the main domain
    for req in requests:
        req_domain = req.get('domain', '')
        if base_domain in req_domain:
            first_party_domains.add(req_domain)
    
    # Check each first-party domain for tracker-like behavior
    for domain in first_party_domains:
        # Check for suspicious resource patterns from this domain
        suspicious_paths = 0
        resources_from_domain = [r for r in requests if r.get('domain') == domain]
        
        for resource in resources_from_domain:
            url = resource.get('url', '')
            path = urlparse(url).path
            
            # Patterns often seen in tracking endpoints
            suspicious_patterns = [
                '/collect', '/pixel', '/track', '/beacon', '/analytics', '/event', 
                '/stats', '/log', '/ping', '/metric', '/hit', '/g/collect'
            ]
            
            for pattern in suspicious_patterns:
                if pattern in path:
                    suspicious_paths += 1
                    break
                    
        # If domain serves suspicious resources, it might be using CNAME cloaking
        if suspicious_paths > 0:
            potential_cname_candidates += 1
    
    return potential_cname_candidates

def analyze_crawler_data(json_file):
    """Extract key metrics from a crawler data file"""
    try:
        # Extract profile from filepath
        file_path = os.path.normpath(json_file)
        path_parts = file_path.split(os.sep)
        profile = path_parts[-2] if len(path_parts) > 2 else "unknown"
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Basic info
        domain = data.get('domain', '')
        timestamp = data.get('timestamp', '')
        base_domain = domain.lower().replace('www.', '')
        
        # Network metrics
        all_requests = []
        for visit in data.get('visits', []):
            visit_requests = visit.get('network', {}).get('requests', [])
            all_requests.extend(visit_requests)
        
        total_requests = len(all_requests)
        unique_domains = count_unique_domains(all_requests)
        third_party_requests = count_third_party_requests(all_requests, base_domain)
        
        # Resource type breakdown
        resource_types = get_resource_type_counts(all_requests)
        js_requests = resource_types.get('script', 0)
        css_requests = resource_types.get('stylesheet', 0)
        image_requests = resource_types.get('image', 0)
        
        # Cookie metrics using existing cookie_analysis if available
        cookie_analysis = data.get('cookie_analysis', {})
        if cookie_analysis:
            # Use the pre-computed cookie analysis
            total_cookies = cookie_analysis.get('total_cookies', 0)
            identified_cookies = cookie_analysis.get('identified_cookies', 0)
            
            # Cookie categories from analysis - updated to match the actual capitalization
            categories = cookie_analysis.get('categories', {})
            necessary_cookies = categories.get('Necessary', 0)
            preference_cookies = categories.get('Preference', 0)
            functional_cookies = categories.get('Functional', 0)
            marketing_cookies = categories.get('Marketing', 0) + categories.get('Advertisement', 0)
            statistics_cookies = categories.get('Statistics', 0) + categories.get('Analytics', 0)
            unclassified_cookies = categories.get('Unknown', 0) + categories.get('Unclassified', 0) + categories.get('Other', 0)
            
            # Get cookies with secure flag and httpOnly flag
            all_cookies = []
            for visit_num, cookies in data.get('cookies', {}).items():
                all_cookies.extend(cookies)
            
            secure_cookies = sum(1 for c in all_cookies if c.get('secure', False))
            httponly_cookies = sum(1 for c in all_cookies if c.get('httpOnly', False))
            
            # Determine third-party cookies based on domain
            third_party_cookies = 0
            for cookie_info in cookie_analysis.get('cookies', []):
                cookie_domain = cookie_info.get('domain', '')
                if base_domain not in cookie_domain:
                    third_party_cookies += 1
        else:
            # Fallback to raw cookie collection if no analysis exists
            all_cookies = []
            for visit_num, cookies in data.get('cookies', {}).items():
                all_cookies.extend(cookies)
            
            total_cookies = len(all_cookies)
            identified_cookies = 0
            necessary_cookies = 0
            preference_cookies = 0
            functional_cookies = 0
            marketing_cookies = 0
            statistics_cookies = 0
            unclassified_cookies = total_cookies
            
            secure_cookies = sum(1 for c in all_cookies if c.get('secure', False))
            httponly_cookies = sum(1 for c in all_cookies if c.get('httpOnly', False))
            third_party_cookies = sum(1 for c in all_cookies if base_domain not in c.get('domain', '').lower())
        
        # Get filter matches from the correct path in the JSON structure
        # First check domain_stats
        filter_matches = 0
        domain_stats = data.get('domain_stats', {})
        if domain_stats:
            filter_matches = domain_stats.get('statistics', {}).get('filter_matches', 0)
        
        # If not found in domain_stats, check domain_analysis
        if filter_matches == 0 and 'domain_analysis' in data:
            domain_analysis = data.get('domain_analysis', {})
            if domain_analysis:
                filter_matches = domain_analysis.get('statistics', {}).get('filter_matches', 0)
        
        # CNAME cloaking detection from domain_stats
        potential_cname_cloaking = 0
        cname_stats = domain_stats.get('statistics', {}).get('cname_cloaking', {})
        if cname_stats:
            potential_cname_cloaking = cname_stats.get('total', 0)
        
        # Web Storage metrics - SIMPLIFIED to just counts and reads
        # First look in top-level storage stats
        local_storage_count = data.get('local_storage_count', 0)
        session_storage_count = data.get('session_storage_count', 0)
        
        # Just include getItem operations
        local_storage_get = data.get('localStorage_getItem', 0)
        session_storage_get = data.get('sessionStorage_getItem', 0)
        
        # Domain categories, organizations, and providers from domain_analysis
        domain_analysis = data.get('domain_analysis', {})
        analyzed_domains = domain_analysis.get('domains', [])
        
        # Initialize counters - RENAMED to be more accurate
        advertising_services = 0
        analytics_services = 0
        social_media_services = 0
        content_delivery_services = 0
        hosting_services = 0
        cdn_services = 0
        
        # Top organizations and providers
        top_organizations = set()
        top_providers = set()
        
        for domain_info in analyzed_domains:
            # Count categories
            categories = domain_info.get('categories', [])
            for category in categories:
                category = category.lower()
                if any(term in category for term in ['ad', 'advertising', 'marketin']):
                    advertising_services += 1
                elif any(term in category for term in ['analytic', 'statistics', 'measurement']):
                    analytics_services += 1
                elif any(term in category for term in ['social', 'comment', 'share']):
                    social_media_services += 1
                elif any(term in category for term in ['cdn', 'content']):
                    content_delivery_services += 1
                elif 'hosting' in category:
                    hosting_services += 1
            
            # Track organizations (limit to 5 to avoid overly long fields)
            organizations = domain_info.get('organizations', [])
            if len(top_organizations) < 5:
                for org in organizations:
                    if org and org not in top_organizations:
                        top_organizations.add(org)
            
            # Track providers (limit to 5)
            provider = domain_info.get('provider')
            if provider and len(top_providers) < 5 and provider not in top_providers:
                top_providers.add(provider)
        
        # Convert sets to strings for CSV
        top_organizations_str = ", ".join(sorted(top_organizations))
        top_providers_str = ", ".join(sorted(top_providers))
        
        # Other third-party services (those that don't fit into specific categories)
        other_services = unique_domains - (advertising_services + analytics_services + 
                                        social_media_services + content_delivery_services + 
                                        hosting_services + cdn_services)
        if other_services < 0:  # Handle potential overlaps in categories
            other_services = 0
        
        # Fingerprinting metrics - fixed to match the actual JSON structure
        fingerprinting = data.get('fingerprinting', {})
        total_fp_calls = 0
        hardware_fp_calls = 0
        canvas_fp_calls = 0
        webgl_fp_calls = 0
        
        # The correct path based on the provided JSON structure
        if 'summary' in fingerprinting and 'summary' in fingerprinting['summary']:
            fp_summary = fingerprinting['summary']['summary']
            total_fp_calls = fp_summary.get('total_calls', 0)
            
            # Category counts are at this path
            category_counts = fp_summary.get('category_counts', {})
            hardware_fp_calls = category_counts.get('hardware', 0)
            canvas_fp_calls = category_counts.get('canvas', 0)
            webgl_fp_calls = category_counts.get('webgl', 0)
        
        return {
            'profile': profile,
            'domain': domain,
            'timestamp': timestamp,
            'total_requests': total_requests,
            'unique_domains': unique_domains,
            'third_party_requests': third_party_requests,
            'js_requests': js_requests,
            'css_requests': css_requests,
            'image_requests': image_requests,
            'total_cookies': total_cookies,
            'identified_cookies': identified_cookies,
            'secure_cookies': secure_cookies,
            'httponly_cookies': httponly_cookies,
            'third_party_cookies': third_party_cookies,
            'necessary_cookies': necessary_cookies,
            'preference_cookies': preference_cookies,
            'functional_cookies': functional_cookies,
            'marketing_cookies': marketing_cookies,
            'statistics_cookies': statistics_cookies,
            'unclassified_cookies': unclassified_cookies,
            'filter_matches': filter_matches,
            'potential_cname_cloaking': potential_cname_cloaking,
            'local_storage_count': local_storage_count,
            'session_storage_count': session_storage_count,
            'local_storage_get': local_storage_get,
            'session_storage_get': session_storage_get,
            'advertising_services': advertising_services,
            'analytics_services': analytics_services,
            'social_media_services': social_media_services,
            'content_delivery_services': content_delivery_services,
            'hosting_services': hosting_services,
            'cdn_services': cdn_services,
            'other_services': other_services,
            'top_organizations': top_organizations_str,
            'top_providers': top_providers_str,
            'total_fingerprinting_calls': total_fp_calls,
            'hardware_fingerprinting_calls': hardware_fp_calls,
            'canvas_fingerprinting_calls': canvas_fp_calls,
            'webgl_fingerprinting_calls': webgl_fp_calls
        }
        
    except Exception as e:
        print(f"Error processing {json_file}: {e}")
        import traceback
        traceback.print_exc()
        return None

def convert_to_csv(json_dir, output_csv):
    """Convert all JSON files to a single CSV"""
    # Get all JSON files from all subdirectories
    json_files = []
    for root, dirs, files in os.walk(json_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    
    if not json_files:
        print(f"No JSON files found in {json_dir}")
        return
    
    print(f"Found {len(json_files)} JSON files to process")
    
    # Process each file
    results = []
    for i, json_file in enumerate(json_files):
        if i % 10 == 0:
            print(f"Processing file {i+1}/{len(json_files)}: {json_file}")
        result = analyze_crawler_data(json_file)
        if result:
            results.append(result)
    
    if not results:
        print("No valid data extracted")
        return
    
    # Write to CSV
    fieldnames = results[0].keys()
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Successfully created CSV file: {output_csv} with {len(results)} rows")

if __name__ == "__main__":
    # Use the specific directory as requested
    json_dir = "data/crawler_data/test"
    output_csv = "data/csv/main_data.csv"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    print(f"Processing JSON files from: {json_dir}")
    print(f"Output will be saved to: {output_csv}")
    
    convert_to_csv(json_dir, output_csv) 