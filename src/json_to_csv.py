import os
import json
import csv
import re
from urllib.parse import urlparse
from collections import defaultdict
from tqdm import tqdm  # Import tqdm for progress bars

# Global sets to collect all unique categories and unmatched categories
ALL_CATEGORIES_ENCOUNTERED = set()
UNMATCHED_CATEGORIES = set()

# Load site rankings from CSV
def load_site_rankings(csv_path='data/db+ref/Tranco_final_sample.csv'):
    """Load site rankings from CSV file"""
    rankings = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Store lowercase domain as key for case-insensitive matching
                rankings[row['domain'].lower()] = int(row['rank'])
        return rankings
    except Exception as e:
        tqdm.write(f"Warning: Could not load site rankings from {csv_path}: {e}")
        return {}

# Global variable to store site rankings
SITE_RANKINGS = load_site_rankings()

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


def analyze_crawler_data(json_file):
    """Extract key metrics from a crawler data file"""
    try:
        # Initialize third-party tracking variables before use
        third_party_domains = set()
        third_party_domain_categories = defaultdict(set)
        
        # Extract profile from filepath
        file_path = os.path.normpath(json_file)
        path_parts = file_path.split(os.sep)
        profile = path_parts[-2] if len(path_parts) > 2 else "unknown"
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Basic data
        domain = data.get('domain', '')
        timestamp = data.get('timestamp', '')
        
        # If domain is empty, extract it from the filename
        if not domain:
             # Get the filename from the path
            filename = os.path.basename(json_file)
            # Remove the .json extension to get the domain
            domain = filename[:-5]  # Remove '.json'
        
        # Get site rank if available
        site_rank = None
        if domain:
            # Try exact match first
            site_rank = SITE_RANKINGS.get(domain.lower())
            if site_rank is None:
                # Try without www prefix
                if domain.lower().startswith('www.'):
                    site_rank = SITE_RANKINGS.get(domain.lower()[4:])
                # Try with www prefix
                else:
                    site_rank = SITE_RANKINGS.get(f"www.{domain.lower()}")
        
        # Extract website categories
        categories = data.get('categories', [])
        primary_category = categories[0] if categories else ""
        additional_categories = "|".join(categories[1:]) if len(categories) > 1 else ""
        
        # Get page loaded status directly from banner_analysis if available
        page_loaded = None  # Start with None (no assumption)
        
        # Get the visit ID from the JSON if available, otherwise use default
        visit_id = data.get('visit_id', '0')
        visit_key = f"visit{visit_id}"  # Format as visit0, visit1, etc.
        
        # Enhanced banner analysis extraction - simplified
        banner_analysis = data.get('banner_analysis', {})
        banner_removed = None
        page_status = None
        banner_conclusion = None
        
        if banner_analysis:
            # Try to get data from specific visit
            if visit_key in banner_analysis:
                visit_data = banner_analysis[visit_key]
                if 'page_loaded' in visit_data:
                    page_loaded = visit_data['page_loaded']
                
                # Extract only the essential banner details
                page_status = visit_data.get('page_status', None)
                banner_conclusion = visit_data.get('conclusion', None)
            
            # If not found but summary_status exists, use that for overall banner status
            if 'summary_status' in banner_analysis:
                summary_status = banner_analysis['summary_status']
                
                if summary_status == 'removed' or summary_status == 'likely_removed':
                    banner_removed = True
                elif summary_status == 'not_removed':
                    banner_removed = False
                # Leave as None for other values
        
        # Fall back to original page_loaded field if banner_analysis doesn't have it
        if page_loaded is None and 'page_loaded' in data:
            page_loaded_info = data['page_loaded']
            if isinstance(page_loaded_info, dict):
                if 'loaded' in page_loaded_info:
                    page_loaded = page_loaded_info['loaded']
            elif page_loaded_info is not None:
                page_loaded = bool(page_loaded_info)
        
        # Get the visit ID from the JSON if available, otherwise use default
        fallback_id = '0' if visit_id != '0' else '1'  # If primary is 0, try 1 as fallback
        
        # Function to get visit-specific data or fall back to another visit
        def get_visit_data(key, primary_id, fallback_id):
            data_by_visit = data.get(key, {})
            if primary_id in data_by_visit:
                return data_by_visit[primary_id]
            elif fallback_id in data_by_visit:
                return data_by_visit[fallback_id]
            return None
        
        # Network Data - Use visit 1
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
        
        # Initialize domain analysis metrics
        first_party_requests = 0
        third_party_requests = 0
        uncategorized_requests = 0
        filter_match_requests = 0
        
        # Initialize category counters
        category_requests = {
            "Advertising": 0,
            "Analytics": 0,
            "Social": 0,
            "Essential": 0,
            "Misc": 0,
            "Hosting": 0,
            "Content": 0,
            # Add other categories as needed
        }
        
        # Get domain analysis if available
        domain_analysis = data.get('domain_analysis', {})
        if domain_analysis and 'domains' in domain_analysis:
            domains = domain_analysis.get('domains', [])
            
            # Recalculate total requests from domain_analysis for accuracy
            domain_requests_total = sum(d.get('request_count', 0) for d in domains)
            if domain_requests_total > 0:
                total_requests = domain_requests_total
            
            # Count by domain type
            cname_cloaking_count = 0
            
            for d in domains:
                req_count = d.get('request_count', 0)
                categories = d.get('categories', [])
                
                # Count filter matches
                if d.get('filter_match', False):
                    filter_match_requests += req_count
                
                # Count CNAME cloaking instances using the new field name
                if d.get('cname_cloaking', False):
                    cname_cloaking_count += 1
                
                # Count by first-party/third-party status
                if d.get('is_first_party_domain', False):
                    first_party_requests += req_count
                else:
                    third_party_requests += req_count
                    third_party_domains.add(d.get('domain', ''))
                
                # Count requests by category (this handles all categories including Advertising)
                for category in categories:
                    if category in category_requests:
                        category_requests[category] += req_count
                    else:
                        # Handle unexpected categories
                        category_requests.setdefault(category, 0)
                        category_requests[category] += req_count
                    
                    # Categorize the domain based on its categories
                    if category in third_party_domain_categories:
                        third_party_domain_categories[category].add(d.get('domain', ''))
            
            # Count unique domains
            unique_domains = len(domains)
            
            # Update potential_cname_cloaking value if we counted it from the domains
            if cname_cloaking_count > 0:
                potential_cname_cloaking = cname_cloaking_count
            
            # Check for statistics within domain_analysis
            domain_statistics = domain_analysis.get('statistics', {})
            if domain_statistics:
                filter_matches = domain_statistics.get('filter_matches', filter_matches)
                # Use total_domains as the authoritative source for unique_domains if available
                if 'total_domains' in domain_statistics:
                    unique_domains = domain_statistics.get('total_domains')
        
        # Check for pre-calculated statistics - kept for backward compatibility 
        statistics = data.get('statistics', {})
        if statistics:
            # Only use statistics if we haven't already found values in domain_analysis
            if filter_matches == 0:
                filter_matches = statistics.get('filter_matches', 0)
            
            # Use total_domains from statistics if we haven't found it in domain_analysis.statistics
            if 'total_domains' in statistics:
                unique_domains = statistics.get('total_domains')
            
            # Get resource type counts directly from statistics if available
            request_types = statistics.get('request_types', {})
            if request_types:
                js_requests = request_types.get('script', 0)
                css_requests = request_types.get('stylesheet', 0)
                image_requests = request_types.get('image', 0)
                # If total_requests is not set yet, set it from statistics
                if not total_requests and 'total_requests' in statistics:
                    total_requests = statistics.get('total_requests', 0)
            
            # Get CNAME cloaking stats - keep this for backward compatibility
            cname_data = statistics.get('cname_cloaking', {})
            if cname_data:
                potential_cname_cloaking = cname_data.get('total', 0)
        
        if network_data and not domain_analysis and not (statistics and statistics.get('request_types')):
            # Only use network_data if domain_analysis and statistics aren't available
            requests = network_data.get('requests', [])
            total_requests = len(requests)
            unique_domains = count_unique_domains(requests)
            
            # Count resources by type
            resource_types = get_resource_type_counts(requests)
            js_requests = resource_types.get('script', 0)
            css_requests = resource_types.get('stylesheet', 0)
            image_requests = resource_types.get('image', 0)
        
        # Cookie Data
        cookies_data = get_visit_data('cookies', visit_id, fallback_id)
        
        # Initialize cookie metrics
        unique_cookies = 0
        overlapping_cookies = 0
        identified_cookies = 0
        first_party_cookies = 0
        third_party_cookies = 0
        secure_cookies = 0
        httponly_cookies = 0
        necessary_cookies = 0
        functional_cookies = 0
        advertising_cookies = 0
        analytics_cookies = 0
        performance_cookies = 0  # Added Performance category
        other_cookies = 0
        unknown_cookies = 0
        shared_identifiers_count = 0  # Initialize new metric
        
        # Initialize tracking cookie variables
        potential_tracking_cookies_count = 0
        
        # Extract cookie analysis data if available
        cookie_analysis = data.get('cookie_analysis', {})
        if cookie_analysis:
            # Use pre-calculated values from cookie analysis
            unique_cookies = cookie_analysis.get('unique_cookies', 0)
            overlapping_cookies = cookie_analysis.get('overlapping_cookies', 0)
            identified_cookies = cookie_analysis.get('identified_cookies', 0)
            first_party_cookies = cookie_analysis.get('first_party_cookies', 0)
            third_party_cookies = cookie_analysis.get('third_party_cookies', 0)
        
            
            # Get potential tracking cookies information
            potential_tracking = cookie_analysis.get('potential_tracking_cookies', {})
            if potential_tracking:
                potential_tracking_cookies_count = potential_tracking.get('total', 0)
                cookie_names = potential_tracking.get('cookie_names', [])
            
            # Get category counts if available
            categories = cookie_analysis.get('categories', {})
            necessary_cookies = categories.get('Necessary', 0)
            functional_cookies = categories.get('Functional', 0)
            advertising_cookies = categories.get('Advertisement', 0)
            analytics_cookies = categories.get('Analytics', 0)
            performance_cookies = categories.get('Performance', 0)  # Added Performance category
            other_cookies = categories.get('Other', 0)
            # Combine Unknown, Unclassified, and Not specified into unknown_cookies
            unknown_cookies = (categories.get('Unknown', 0) + 
                            categories.get('Unclassified', 0) + 
                            categories.get('Not specified', 0))
            
            # Get shared identifiers count
            cookie_sharing = cookie_analysis.get('cookie_sharing', {})
            if cookie_sharing:
                shared_identifiers = cookie_sharing.get('shared_identifiers', {})
                shared_identifiers_count = shared_identifiers.get('count', 0)
        
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
                
                # Count cookies by category if available
                category = cookie.get('category', '').lower()
                if category:
                    identified_cookies += 1
                    
                    # Keep original categories and handle Other/Unknown explicitly
                    if 'necessary' in category:
                        necessary_cookies += 1
                    elif 'functional' in category:
                        functional_cookies += 1
                    elif 'advertisement' in category:
                        advertising_cookies += 1
                    elif 'analytics' in category:
                        analytics_cookies += 1
                    elif 'performance' in category:  # Added Performance category handling
                        performance_cookies += 1
                    elif 'other' in category:
                        other_cookies += 1
                    elif ('unknown' in category or 
                          'unclassified' in category or 
                          'not specified' in category):
                        unknown_cookies += 1
                    else:
                        # If category exists but doesn't match known types, count as Other
                        other_cookies += 1
                else:
                    # If no category is provided, count as Unknown
                    unknown_cookies += 1
        
        # Always count secure and httpOnly regardless of where cookie data comes from
        if cookies_data:
            for cookie in cookies_data:
                if cookie.get('secure', False):
                    secure_cookies += 1
                if cookie.get('httpOnly', False):
                    httponly_cookies += 1
        
        # Storage API Usage - Use visit 1
        storage_data = get_visit_data('storage', visit_id, fallback_id)
        
        local_storage_count = 0
        session_storage_count = 0
        local_storage_get = 0
        session_storage_get = 0
        storage_potential_identifiers_count = 0
        local_storage_potential_identifiers = 0  # Added variable for localStorage identifiers
        session_storage_potential_identifiers = 0  # Added variable for sessionStorage identifiers
        
        if storage_data:
            local_storage_count = storage_data.get('local_storage_count', 0)
            session_storage_count = storage_data.get('session_storage_count', 0)
            
            # Get API usage counts - check both "api_usage" and "api_count" locations
            api_usage = storage_data.get('api_usage', {})
            api_count = storage_data.get('api_count', {})
            
            # First try api_usage (old format)
            if api_usage:
                local_storage_api = api_usage.get('localStorage', {})
                session_storage_api = api_usage.get('sessionStorage', {})
                
                local_storage_get = local_storage_api.get('getItem_count', 0)
                session_storage_get = session_storage_api.get('getItem_count', 0)
            
            # Then try api_count (new format)
            elif api_count:
                local_storage_api = api_count.get('localStorage', {})
                session_storage_api = api_count.get('sessionStorage', {})
                
                local_storage_get = local_storage_api.get('getItem_count', 0)
                session_storage_get = session_storage_api.get('getItem_count', 0)
        
        # Check for storage analysis data
        storage_analysis = data.get('storage_analysis', {})
        if storage_analysis:
            potential_identifiers = storage_analysis.get('potential_identifiers', {})
            storage_potential_identifiers_count = potential_identifiers.get('total', 0)
            local_storage_potential_identifiers = potential_identifiers.get('localStorage', 0)  # Extract localStorage identifiers
            session_storage_potential_identifiers = potential_identifiers.get('sessionStorage', 0)  # Extract sessionStorage identifiers
        
        # Track top organizations and providers
        top_organizations = defaultdict(int)
        
        # Initialize service counters for unique domains
        advertising_domains = 0
        analytics_domains = 0
        social_media_domains = 0
        essential_domains = 0
        hosting_domains = 0
        customer_interaction_domains = 0
        audio_video_domains = 0
        extensions_domains = 0
        adult_advertising_domains = 0
        consent_management_domains = 0
        miscellaneous_domains = 0
        utilities_domains = 0  # Added for "Utilities" category
        uncategorized_domains = 0
        
        # Initialize service counters for request counts
        advertising_requests = 0
        analytics_requests = 0
        social_media_requests = 0
        essential_requests = 0
        hosting_requests = 0
        customer_interaction_requests = 0
        audio_video_requests = 0
        extensions_requests = 0
        adult_advertising_requests = 0
        consent_management_requests = 0
        miscellaneous_requests = 0
        utilities_requests = 0  # Added for "Utilities" category
        uncategorized_requests = 0
        
        # Process domain analysis if available
        if domain_analysis and 'domains' in domain_analysis:
            for domain_data in domain_analysis['domains']:
                request_count = domain_data.get('request_count', 0)
                categories = domain_data.get('categories', [])
                
                # Track organizations
                for org in domain_data.get('organizations', []):
                    top_organizations[org] += request_count
                
                # Count services by category
                if categories:
                    for category in categories:
                        # Add to our global set of encountered categories
                        ALL_CATEGORIES_ENCOUNTERED.add(category)
                        
                        # Handle each category - exact matches only
                        if category == "Advertising":
                            advertising_domains += 1
                            advertising_requests += request_count
                        elif category == "Site Analytics":
                            analytics_domains += 1
                            analytics_requests += request_count
                        elif category == "Social Media":
                            social_media_domains += 1
                            social_media_requests += request_count
                        elif category == "Essential":
                            essential_domains += 1
                            essential_requests += request_count
                        elif category == "Hosting":
                            hosting_domains += 1
                            hosting_requests += request_count
                        elif category == "Customer Interaction":
                            customer_interaction_domains += 1
                            customer_interaction_requests += request_count
                        elif category == "Audio/Video Player":
                            audio_video_domains += 1
                            audio_video_requests += request_count
                        elif category == "Extensions":
                            extensions_domains += 1
                            extensions_requests += request_count
                        elif category == "Adult Advertising":
                            adult_advertising_domains += 1
                            adult_advertising_requests += request_count
                        elif category == "Consent Management":
                            consent_management_domains += 1
                            consent_management_requests += request_count
                        elif category == "Misc":
                            miscellaneous_domains += 1
                            miscellaneous_requests += request_count
                        elif category == "Utilities":
                            utilities_domains += 1
                            utilities_requests += request_count
                        else:
                            # Category not explicitly handled
                            UNMATCHED_CATEGORIES.add(category)
                            uncategorized_domains += 1
                            uncategorized_requests += request_count
                else:
                    # If no categories, count as uncategorized
                    uncategorized_domains += 1
                    uncategorized_requests += request_count
        
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
        
        # Get the top organizations (limit to top 5)
        top_orgs_list = sorted(top_organizations.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Now extract category counts from our dictionary
        advertising_requests = category_requests["Advertising"]
        analytics_requests = category_requests["Analytics"]
        social_media_requests = category_requests.get("Social Media", 0)
        essential_requests = category_requests.get("Essential", 0)
        hosting_requests = category_requests.get("Hosting", 0)
        customer_interaction_requests = category_requests.get("Customer Interaction", 0)
        audio_video_requests = category_requests.get("Audio/Video Player", 0)
        extensions_requests = category_requests.get("Extensions", 0)
        adult_advertising_requests = category_requests.get("Adult Advertising", 0)
        consent_management_requests = category_requests.get("Consent Management", 0)
        miscellaneous_requests = category_requests.get("Misc", 0)
        utilities_requests = category_requests.get("Utilities", 0)
        uncategorized_requests = category_requests.get("Uncategorized", 0)
        
        
        # Return the data with related fields grouped together
        return {
            # Basic site info
            'profile': profile,
            'domain': domain,
            'rank': site_rank,
            'primary_category': primary_category,
            'additional_categories': additional_categories,
            'timestamp': timestamp,
            
            # Page/banner status
            'page_loaded': page_loaded,
            'banner_removed': banner_removed,
            'page_status': page_status,
            'banner_conclusion': banner_conclusion,
            
            # Request counts
            'total_requests': total_requests,
            
            # Domain-related metrics grouped together
            'unique_domains': unique_domains,
            'first_party_requests': first_party_requests,
            'third_party_requests': third_party_requests,
            'filter_matches': filter_matches,
            'filter_match_requests': filter_match_requests,
            'potential_cname_cloaking': potential_cname_cloaking,
            
            # Domain categories and counts
            'advertising_domains': advertising_domains,
            'analytics_domains': analytics_domains,
            'social_media_domains': social_media_domains,
            'essential_domains': essential_domains,
            'hosting_domains': hosting_domains,
            'customer_interaction_domains': customer_interaction_domains,
            'audio_video_domains': audio_video_domains,
            'extensions_domains': extensions_domains,
            'adult_advertising_domains': adult_advertising_domains,
            'consent_management_domains': consent_management_domains,
            'miscellaneous_domains': miscellaneous_domains,
            'uncategorized_domains': uncategorized_domains,
            
            # Request categories
            'advertising_requests': advertising_requests,
            'analytics_requests': analytics_requests,
            'social_media_requests': social_media_requests,
            'essential_requests': essential_requests,
            'hosting_requests': hosting_requests,
            'customer_interaction_requests': customer_interaction_requests,
            'audio_video_requests': audio_video_requests,
            'extensions_requests': extensions_requests,
            'adult_advertising_requests': adult_advertising_requests,
            'consent_management_requests': consent_management_requests,
            'miscellaneous_requests': miscellaneous_requests,
            'utilities_requests': utilities_requests,
            'uncategorized_requests': uncategorized_requests,
            
            # Resource types
            'js_requests': js_requests,
            'css_requests': css_requests,
            'image_requests': image_requests,
            
            # Cookie metrics
            'unique_cookies': unique_cookies,
            'overlapping_cookies': overlapping_cookies,
            'identified_cookies': identified_cookies,
            'first_party_cookies': first_party_cookies,
            'third_party_cookies': third_party_cookies,
            'secure_cookies': secure_cookies,
            'httponly_cookies': httponly_cookies,
            'necessary_cookies': necessary_cookies,
            'functional_cookies': functional_cookies,
            'advertising_cookies': advertising_cookies,
            'analytics_cookies': analytics_cookies,
            'performance_cookies': performance_cookies,
            'other_cookies': other_cookies,
            'unknown_cookies': unknown_cookies,
            'potential_tracking_cookies_count': potential_tracking_cookies_count,
            'shared_identifiers_count': shared_identifiers_count,
            
            # Storage metrics
            'local_storage_count': local_storage_count,
            'session_storage_count': session_storage_count,
            'local_storage_get': local_storage_get,
            'session_storage_get': session_storage_get,
            'storage_potential_identifiers_count': storage_potential_identifiers_count,
            'local_storage_potential_identifiers': local_storage_potential_identifiers,
            'session_storage_potential_identifiers': session_storage_potential_identifiers,
            
            # Fingerprinting metrics
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
            'intl_fingerprinting_calls': intl_fp_calls,
            
            # New fields for third-party domain analysis
            'total_third_party_domains': len(third_party_domains),
            'social_media_domains_count': len(third_party_domain_categories.get('Social Media', set())),
            'advertising_domains_count': len(third_party_domain_categories.get('Advertising', set())),
            'analytics_domains_count': len(third_party_domain_categories.get('Site Analytics', set())),
            'consent_management_domains_count': len(third_party_domain_categories.get('Consent Management', set())),
            'hosting_domains_count': len(third_party_domain_categories.get('Hosting', set())),
            'customer_interaction_domains_count': len(third_party_domain_categories.get('Customer Interaction', set())),
            'audio_video_domains_count': len(third_party_domain_categories.get('Audio/Video Player', set())),
            'extensions_domains_count': len(third_party_domain_categories.get('Extensions', set())),
            'adult_advertising_domains_count': len(third_party_domain_categories.get('Adult Advertising', set())),
            'utilities_domains_count': len(third_party_domain_categories.get('Utilities', set())),
            'miscellaneous_domains_count': len(third_party_domain_categories.get('Misc', set())),
            'uncategorized_domains_count': len(third_party_domain_categories.get('Uncategorized', set())),
        }
        
    except Exception as e:
        tqdm.write(f"Error processing {json_file}: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_folder(folder_path, extension_name):
    """
    Process all JSON files in a single folder
    
    Args:
        folder_path: Path to the folder containing JSON files
        extension_name: Name of the extension/folder to include in results
        
    Returns:
        List of dictionaries containing the processed data
    """
    results = []
    json_files = []
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
    
    tqdm.write(f"Processing folder '{extension_name}': {len(json_files)} JSON files")
    
    # Use tqdm to create a progress bar for files
    for json_file in tqdm(json_files, desc=f"Processing {extension_name}", unit="file"):
        result = analyze_crawler_data(json_file)
        if result:
            results.append(result)
    
    # Print all the unique categories we've found once per folder
    #tqdm.write(f"\nCategories encountered in '{extension_name}':")
    #tqdm.write(f"- All categories: {sorted(ALL_CATEGORIES_ENCOUNTERED)}")
    #tqdm.write(f"- Unmatched categories: {sorted(UNMATCHED_CATEGORIES)}\n")
            
    return results

def process_single_folder(json_dir, output_csv, folder_name):
    """Process a single folder and save results to CSV"""
    folder_path = os.path.join(json_dir, folder_name)
    
    if not os.path.isdir(folder_path):
        tqdm.write(f"Error: {folder_path} is not a valid directory")
        return
        
    results = process_folder(folder_path, folder_name)
    
    if not results:
        tqdm.write("No valid data extracted")
        return
    
    # Write to CSV, removing extension from fieldnames
    fieldnames = list(results[0].keys())
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    tqdm.write(f"Successfully created CSV file: {output_csv} with {len(results)} rows")

def process_all_folders(json_dir, output_csv):
    """Process all folders in the directory and combine results to a single CSV"""
    # Get all extension directories
    extension_dirs = [d for d in os.listdir(json_dir) if os.path.isdir(os.path.join(json_dir, d))]
    extension_dirs.sort()  # Sort by extension name
    
    tqdm.write(f"Found {len(extension_dirs)} extension directories to process")
    
    # Process each extension directory and collect all results
    all_results = []
    
    # Use tqdm to create a progress bar for folders
    for ext_dir in tqdm(extension_dirs, desc="Processing folders", unit="folder"):
        ext_path = os.path.join(json_dir, ext_dir)
        results = process_folder(ext_path, ext_dir)
        all_results.extend(results)
    
    if not all_results:
        tqdm.write("No valid data extracted")
        return
    
    
    # Write to CSV
    fieldnames = list(all_results[0].keys())
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    
    tqdm.write(f"Successfully created CSV file: {output_csv} with {len(all_results)} rows")
if __name__ == "__main__":
    # Base directory for crawler data
    json_dir = "data/crawler_data"
    output_csv = "data/csv/final_data.csv"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    
    # Choose whether to process a single folder or all folders
    process_single = False  # Set to False to process all folders
    specific_folder = "test"
    
    if process_single:
        tqdm.write(f"Processing specific folder: {specific_folder}")
        process_single_folder(json_dir, output_csv, specific_folder)
    else:
        tqdm.write(f"Processing all extension folders in: {json_dir}")
        process_all_folders(json_dir, output_csv)
    
    # Print all encountered categories
    print("\nAll encountered domain categories:")
    for category in sorted(ALL_CATEGORIES_ENCOUNTERED):
        print(f"- {category}")

    if UNMATCHED_CATEGORIES:
        print("\nUnmatched categories (not explicitly handled):")
        for category in sorted(UNMATCHED_CATEGORIES):
            print(f"- {category}") 