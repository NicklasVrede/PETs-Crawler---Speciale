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

def get_resource_type_counts(requests):
    """Count requests by resource type"""
    types = {}
    for req in requests:
        if 'resource_type' in req:
            resource_type = req['resource_type']
            types[resource_type] = types.get(resource_type, 0) + 1
    return types

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
        
        # Basic data
        domain = data.get('domain', '')
        timestamp = data.get('timestamp', '')
        
        # Extract website categories
        categories = data.get('categories', [])
        primary_category = categories[0] if categories else ""
        additional_categories = "|".join(categories[1:]) if len(categories) > 1 else ""
        
        # Helper to get specific visit data
        def get_visit_data(section, preferred_visit="1", fallback_visit="0"):
            if section not in data:
                return None
            
            section_data = data[section]
            # Try to get the preferred visit
            if preferred_visit in section_data:
                return section_data[preferred_visit]
            # Fall back to an alternative visit
            elif fallback_visit in section_data:
                return section_data[fallback_visit]
            # Try any available numeric key
            for key in section_data:
                if isinstance(key, (int, str)) and (isinstance(key, int) or key.isdigit()):
                    return section_data[key]
            return None
        
        # Network Data - Use visit 1
        visit_id = "1"  # Prefer visit 1
        fallback_id = "0"  # Fallback to visit 0 if needed
        
        network_data = get_visit_data('network_data', visit_id, fallback_id)
        
        # Default values in case data is missing
        requests = []
        total_requests = 0
        unique_domains = 0
        js_requests = 0
        css_requests = 0
        image_requests = 0
        filter_matches = 0
        potential_cname_cloaking = 0
        banner_removed = False
        page_loaded = True
        
        # Initialize domain analysis metrics
        first_party_requests = 0
        infrastructure_service_requests = 0
        third_party_requests = 0
        advertising_requests = 0
        uncategorized_requests = 0
        filter_match_requests = 0  # New counter for requests to filter-matched domains
        
        # Get domain analysis if available
        domain_analysis = data.get('domain_analysis', {})
        if domain_analysis and 'domains' in domain_analysis:
            domains = domain_analysis.get('domains', [])
            
            # Recalculate total requests from domain_analysis for accuracy
            domain_requests_total = sum(d.get('request_count', 0) for d in domains)
            if domain_requests_total > 0:
                total_requests = domain_requests_total
            
            # Count by domain type
            for d in domains:
                req_count = d.get('request_count', 0)
                categories = d.get('categories', [])
                
                # Count filter matches
                if d.get('filter_match', False):
                    filter_match_requests += req_count
                
                # Count by first-party/third-party status
                if d.get('is_first_party_domain', False):
                    first_party_requests += req_count
                elif d.get('infrastructure_type') is not None:
                    infrastructure_service_requests += req_count
                else:
                    # True third-party: not first party and not infrastructure
                    third_party_requests += req_count
                
                # Count advertising requests
                if "Advertising" in categories:
                    advertising_requests += req_count
                
                # Count uncategorized requests
                if not categories:
                    uncategorized_requests += req_count
            
            # Count unique domains
            unique_domains = len(domains)
        
        # Check for pre-calculated statistics
        statistics = data.get('statistics', {})
        if statistics:
            # Use pre-calculated values from the JSON
            filter_matches = statistics.get('filter_matches', 0)
            
            # Get CNAME cloaking stats
            cname_data = statistics.get('cname_cloaking', {})
            if cname_data:
                potential_cname_cloaking = cname_data.get('total', 0)
        
        if network_data and not domain_analysis:
            # Only use network_data if domain_analysis isn't available
            requests = network_data.get('requests', [])
            total_requests = len(requests)
            unique_domains = count_unique_domains(requests)
            
            # Count resources by type
            resource_types = get_resource_type_counts(requests)
            js_requests = resource_types.get('script', 0)
            css_requests = resource_types.get('stylesheet', 0)
            image_requests = resource_types.get('image', 0)
            
            # Only calculate CNAME cloaking if not already provided in statistics
            if not statistics or 'cname_cloaking' not in statistics:
                potential_cname_cloaking = count_potential_cname_cloaking(requests, domain)
        
        # Cookie Data
        cookies_data = get_visit_data('cookies', visit_id, fallback_id)
        
        # Initialize cookie metrics
        unique_cookies = 0
        overlapping_cookies = 0
        identified_cookies = 0
        unidentified_cookies = 0
        secure_cookies = 0
        httponly_cookies = 0
        third_party_cookies = 0
        necessary_cookies = 0
        preference_cookies = 0
        functional_cookies = 0 
        marketing_cookies = 0
        statistics_cookies = 0
        unclassified_cookies = 0
        
        # Initialize tracking cookie variables
        potential_tracking_cookies_count = 0
        potential_tracking_cookie_names = ""
        
        # Extract cookie analysis data if available
        cookie_analysis = data.get('cookie_analysis', {})
        if cookie_analysis:
            # Use pre-calculated values from cookie analysis
            unique_cookies = cookie_analysis.get('unique_cookies', 0)
            overlapping_cookies = cookie_analysis.get('overlapping_cookies', 0)
            identified_cookies = cookie_analysis.get('identified_cookies', 0)
            unidentified_cookies = cookie_analysis.get('unidentified_cookies', 0)
            
            # Get potential tracking cookies information
            potential_tracking = cookie_analysis.get('potential_tracking_cookies', {})
            if potential_tracking:
                potential_tracking_cookies_count = potential_tracking.get('total', 0)
                cookie_names = potential_tracking.get('cookie_names', [])
                potential_tracking_cookie_names = '|'.join(cookie_names)
            
            # Get category counts if available
            categories = cookie_analysis.get('categories', {})
            necessary_cookies = categories.get('Necessary', 0)
            functional_cookies = categories.get('Functional', 0)
            preference_cookies = categories.get('Preference', 0) + categories.get('Preferences', 0)
            marketing_cookies = categories.get('Marketing', 0) + categories.get('Advertisement', 0)
            statistics_cookies = categories.get('Statistics', 0) + categories.get('Analytics', 0)
            unclassified_cookies = categories.get('Other', 0) + categories.get('Unknown', 0) + categories.get('Unclassified', 0)
        
        # Fall back to manual counting if cookie_analysis isn't available
        elif cookies_data:
            # For cookies, the visit data is directly an array of cookies
            total_cookies = len(cookies_data)
            
            # Count cookie properties
            for cookie in cookies_data:
                if cookie.get('secure', False):
                    secure_cookies += 1
                if cookie.get('httpOnly', False):
                    httponly_cookies += 1
                    
                # Check if cookie is third-party
                cookie_domain = cookie.get('domain', '')
                if cookie_domain and domain not in cookie_domain:
                    third_party_cookies += 1
                
                # Count cookies by category if available
                category = cookie.get('category', '').lower()
                if category:
                    identified_cookies += 1
                    
                    if 'necessary' in category or 'essential' in category:
                        necessary_cookies += 1
                    elif 'preference' in category or 'functional' in category:
                        preference_cookies += 1
                    elif 'functional' in category:
                        functional_cookies += 1
                    elif 'marketing' in category or 'advertising' in category or 'targeting' in category:
                        marketing_cookies += 1
                    elif 'statistic' in category or 'analytics' in category or 'performance' in category:
                        statistics_cookies += 1
                    else:
                        unclassified_cookies += 1
        
        # Always count secure and httpOnly regardless of where cookie data comes from
        if cookies_data:
            for cookie in cookies_data:
                if cookie.get('secure', False):
                    secure_cookies += 1
                if cookie.get('httpOnly', False):
                    httponly_cookies += 1
                
                # Check if cookie is third-party
                cookie_domain = cookie.get('domain', '')
                if cookie_domain and domain not in cookie_domain:
                    third_party_cookies += 1
        
        # Storage API Usage - Use visit 1
        storage_data = get_visit_data('storage', visit_id, fallback_id)
        
        local_storage_count = 0
        session_storage_count = 0
        local_storage_get = 0
        session_storage_get = 0
        storage_potential_identifiers_count = 0
        
        if storage_data:
            local_storage_count = storage_data.get('local_storage_count', 0)
            session_storage_count = storage_data.get('session_storage_count', 0)
            
            # Get API usage counts if available
            api_usage = storage_data.get('api_usage', {})
            local_storage_api = api_usage.get('localStorage', {})
            session_storage_api = api_usage.get('sessionStorage', {})
            
            local_storage_get = local_storage_api.get('getItem_count', 0)
            session_storage_get = session_storage_api.get('getItem_count', 0)
        
        # Check for storage analysis data
        storage_analysis = data.get('storage_analysis', {})
        if storage_analysis:
            potential_identifiers = storage_analysis.get('potential_identifiers', {})
            storage_potential_identifiers_count = potential_identifiers.get('total', 0)
        
        # Service categorization
        # Initialize service counts
        advertising_services = 0
        analytics_services = 0
        social_media_services = 0
        content_delivery_services = 0
        hosting_services = 0
        cdn_services = 0
        other_services = 0
        
        # Track top organizations and providers
        top_organizations = defaultdict(int)
        top_providers = defaultdict(int)
        
        # Get unique domains from the requests
        domains = set()
        for req in requests:
            if 'domain' in req:
                domains.add(req['domain'])
        
        # Categorize each domain
        for domain_name in domains:
            category = "unknown"
            organization = "unknown"
            provider = "unknown"
            
            # Simple classification - this would be more comprehensive in practice
            if "ad" in domain_name or "ads" in domain_name or "doubleclick" in domain_name:
                category = "advertising"
                if "google" in domain_name:
                    organization = "Google"
                    provider = "DoubleClick"
            elif "analytics" in domain_name or "stats" in domain_name:
                category = "analytics"
                if "google" in domain_name:
                    organization = "Google"
                    provider = "Google Analytics"
            elif "facebook" in domain_name or "twitter" in domain_name or "linkedin" in domain_name:
                category = "social media"
                if "facebook" in domain_name:
                    organization = "Meta"
                    provider = "Facebook"
                elif "twitter" in domain_name:
                    organization = "Twitter"
                    provider = "Twitter"
            elif "cdn" in domain_name or "cloudfront" in domain_name or "cloudflare" in domain_name:
                category = "cdn"
                if "cloudfront" in domain_name:
                    organization = "Amazon"
                    provider = "CloudFront"
                elif "cloudflare" in domain_name:
                    organization = "Cloudflare"
                    provider = "Cloudflare CDN"
            elif "aws" in domain_name or "azure" in domain_name or "gcp" in domain_name:
                category = "hosting"
                if "aws" in domain_name or "amazon" in domain_name:
                    organization = "Amazon"
                    provider = "AWS"
                elif "azure" in domain_name or "microsoft" in domain_name:
                    organization = "Microsoft"
                    provider = "Azure"
            
            # Record the organization and provider
            if organization != "unknown":
                top_organizations[organization] += 1
            if provider != "unknown":
                top_providers[provider] += 1
            
            # Increment category counters
            if category == "advertising":
                advertising_services += 1
            elif category == "analytics":
                analytics_services += 1
            elif category == "social media":
                social_media_services += 1
            elif category == "content delivery":
                content_delivery_services += 1
            elif category == "hosting":
                hosting_services += 1
            elif "cdn" in category.lower():
                cdn_services += 1
            else:
                other_services += 1
        
        # Format top organizations and providers
        # Format with counts: "Org1:42|Org2:23|Org3:17"
        top_organizations_str = '|'.join([f"{org}:{count}" for org, count in 
                                        sorted(top_organizations.items(), key=lambda x: x[1], reverse=True)[:3]])
        
        top_providers_str = '|'.join([f"{provider}:{count}" for provider, count in 
                                    sorted(top_providers.items(), key=lambda x: x[1], reverse=True)[:3]])
        
        # Fingerprinting metrics - Use visit 1
        fingerprinting_data = get_visit_data('fingerprinting', visit_id, fallback_id)
        
        # Default values
        total_fp_calls = 0
        hardware_fp_calls = 0
        canvas_fp_calls = 0
        webgl_fp_calls = 0
        
        # Fingerprinting variables
        navigator_fp_calls = 0
        screen_fp_calls = 0
        storage_fp_calls = 0
        date_fp_calls = 0
        media_fp_calls = 0
        performance_fp_calls = 0
        intl_fp_calls = 0
        
        if fingerprinting_data:
            # Get technique breakdown if available
            technique_breakdown = fingerprinting_data.get('technique_breakdown', {})
            if not technique_breakdown and 'domain_summary' in fingerprinting_data:
                # Try to get from domain_summary if the direct breakdown is not there
                domain_summary = fingerprinting_data.get('domain_summary', {})
                technique_breakdown = domain_summary.get('technique_breakdown', {})
            
            # Calculate call counts
            total_fp_calls = sum(technique_breakdown.values())
            hardware_fp_calls = technique_breakdown.get('hardware', 0)
            canvas_fp_calls = technique_breakdown.get('canvas', 0)
            webgl_fp_calls = technique_breakdown.get('webgl', 0)
            
            # Additional fingerprinting techniques
            navigator_fp_calls = technique_breakdown.get('navigator', 0)
            screen_fp_calls = technique_breakdown.get('screen', 0)
            storage_fp_calls = technique_breakdown.get('storage', 0)
            date_fp_calls = technique_breakdown.get('date', 0)
            media_fp_calls = technique_breakdown.get('media', 0)
            performance_fp_calls = technique_breakdown.get('performance', 0)
            intl_fp_calls = technique_breakdown.get('intl', 0)
        
        # Return the data with categories added after domain and new request metrics
        return {
            'profile': profile,
            'domain': domain,
            'primary_category': primary_category,
            'additional_categories': additional_categories,
            'timestamp': timestamp,
            'page_loaded': page_loaded,
            'banner_removed': banner_removed,
            'total_requests': total_requests,
            'unique_domains': unique_domains,
            'first_party_requests': first_party_requests,
            'infrastructure_service_requests': infrastructure_service_requests,
            'third_party_requests': third_party_requests,
            'advertising_requests': advertising_requests,
            'uncategorized_requests': uncategorized_requests,
            'filter_match_requests': filter_match_requests,
            'js_requests': js_requests,
            'css_requests': css_requests,
            'image_requests': image_requests,
            'unique_cookies': unique_cookies,
            'overlapping_cookies': overlapping_cookies,
            'identified_cookies': identified_cookies,
            'unidentified_cookies': unidentified_cookies,
            'secure_cookies': secure_cookies,
            'httponly_cookies': httponly_cookies,
            'third_party_cookies': third_party_cookies,
            'necessary_cookies': necessary_cookies,
            'preference_cookies': preference_cookies,
            'functional_cookies': functional_cookies,
            'marketing_cookies': marketing_cookies,
            'statistics_cookies': statistics_cookies,
            'unclassified_cookies': unclassified_cookies,
            'potential_tracking_cookies_count': potential_tracking_cookies_count,
            'potential_tracking_cookie_names': potential_tracking_cookie_names,
            'filter_matches': filter_matches,
            'potential_cname_cloaking': potential_cname_cloaking,
            'local_storage_count': local_storage_count,
            'session_storage_count': session_storage_count,
            'local_storage_get': local_storage_get,
            'session_storage_get': session_storage_get,
            'storage_potential_identifiers_count': storage_potential_identifiers_count,
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
            'webgl_fingerprinting_calls': webgl_fp_calls,
            'navigator_fingerprinting_calls': navigator_fp_calls,
            'screen_fingerprinting_calls': screen_fp_calls,
            'storage_fingerprinting_calls': storage_fp_calls,
            'date_fingerprinting_calls': date_fp_calls,
            'media_fingerprinting_calls': media_fp_calls,
            'performance_fingerprinting_calls': performance_fp_calls,
            'intl_fingerprinting_calls': intl_fp_calls
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
    json_dir = "data/crawler_data non-kameleo/test"
    output_csv = "data/csv/main_data.csv"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    print(f"Processing JSON files from: {json_dir}")
    print(f"Output will be saved to: {output_csv}")
    
    convert_to_csv(json_dir, output_csv) 