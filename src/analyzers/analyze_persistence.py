import json
import os
import datetime
from collections import Counter, defaultdict
import glob
import difflib  # For Ratcliff/Obershelp string comparison
from tqdm import tqdm


def analyze_persistence(data_path):
    """
    Analyze persistent storage and cookies in crawler data
    and identify potential fingerprinting cookies.
    """
    try:
        with open(data_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        tqdm.write(f"Error: File not found at {data_path}")
        return
    except json.JSONDecodeError:
        tqdm.write(f"Error: Invalid JSON at {data_path}")
        return
    
    # Add persistent flag to storage items
    mark_persistent_storage(data)
    
    # Add persistent flag to cookies and update cookie analysis
    mark_persistent_cookies(data)
    
    # Check for identical cookie values across visits
    check_identical_cookies(data)
    
    # Identify potential fingerprinting cookies
    identify_fingerprinting_cookies(data)
    
    # Analyze cookie sharing across domains
    analyze_cookie_domain_sharing(data)
    
    # Save enhanced data
    output_path = data_path.replace('.json', '_enhanced.json')
    with open(output_path, 'w') as file:
        json.dump(data, file, indent=2)
    
    tqdm.write(f"Enhanced data saved to {output_path}")

def mark_persistent_storage(data):
    """Mark localStorage items as persistent"""
    if 'storage' not in data:
        tqdm.write("No storage data found")
        return
    
    # Process each visit's storage data
    for visit_key, visit_data in data['storage'].items():
        if visit_key == '...':  # Skip the summary entry
            continue
        
        # Mark localStorage items as persistent (they typically persist between sessions)
        if 'local_storage' in visit_data:
            for item in visit_data['local_storage']:
                item['persistent'] = True
        
        # SessionStorage items are not persistent by definition
        if 'session_storage' in visit_data:
            for item in visit_data['session_storage']:
                item['persistent'] = False

def mark_persistent_cookies(data):
    """Mark cookies as persistent if they have a future expiration date"""
    if 'cookies' not in data:
        tqdm.write("No cookie data found")
        return
    
    current_time = datetime.datetime.now().timestamp()
    
    # Count persistent and non-persistent cookies
    persistent_count = 0
    non_persistent_count = 0
    
    # Handle different cookie data structures
    if isinstance(data['cookies'], dict):
        # Format: {'visit1': [cookies], 'visit2': [cookies]}
        for visit_id, visit_cookies in data['cookies'].items():
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
        total_cookies = sum(len(cookies) for cookies in data['cookies'].values())
    
    elif isinstance(data['cookies'], list):
        # Simple list format
        for cookie in data['cookies']:
            if cookie.get('expires') and cookie['expires'] > current_time:
                cookie['persistent'] = True
                # Add days until expiry as a user-friendly metric
                days_until_expiry = (cookie['expires'] - current_time) / (60 * 60 * 24)
                cookie['days_until_expiry'] = round(days_until_expiry, 2)
                persistent_count += 1
            else:
                cookie['persistent'] = False
                non_persistent_count += 1
        
        total_cookies = len(data['cookies'])
    
    # Update cookie_analysis with persistence statistics
    if 'cookie_analysis' in data:
        data['cookie_analysis']['persistent_count'] = persistent_count
        data['cookie_analysis']['non_persistent_count'] = non_persistent_count
        data['cookie_analysis']['persistence_ratio'] = round(persistent_count / total_cookies * 100, 2) if total_cookies else 0

def check_identical_cookies(data):
    """Check if cookies have identical values across visits"""
    if 'network_data' not in data:
        tqdm.write("No network data found for cookie value comparison")
        return
    
    # Track cookie values across visits
    cookie_values = defaultdict(dict)
    identical_count = 0
    changing_count = 0
    
    # Collect cookie values from all visits
    visit_count = 0
    for visit_key, visit_data in data['network_data'].items():
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
    if cookie_values and 'cookie_analysis' in data:
        total_multi_visit = identical_count + changing_count
        
        data['cookie_analysis']['value_consistency'] = {
            'cookies_in_multiple_visits': total_multi_visit,
            'identical_value_count': identical_count,
            'changing_value_count': changing_count,
            'identical_percentage': round(identical_count / total_multi_visit * 100, 1) if total_multi_visit > 0 else 0
        }

def identify_fingerprinting_cookies(data):
    """
    Identify cookies with characteristics of potential identifiers:
    1. Not a session cookie and has a lifetime of more than 90 days
    2. Has a length of at least 8 bytes to hold enough entropy
    3. Is unique in each measurement run, and the length of each value differs by no more than 25%
    4. Values are similar according to the Ratcliff/Obershelp algorithm (≥ 60%)
    """
    if 'cookies' not in data:
        tqdm.write("No cookie data found for identifier analysis")
        return
    
    # Track statistics for summary
    potential_id_count = 0
    categories_counter = Counter()
    
    # Extract cookie values across visits from network data
    cookie_values_by_visit = defaultdict(dict)
    
    if 'network_data' in data:
        for visit_key, visit_data in data['network_data'].items():
            if visit_key == '...':  # Skip the summary entry
                continue
                
            if 'requests' not in visit_data:
                continue
                
            for request in visit_data['requests']:
                if 'headers' in request and 'cookie' in request['headers']:
                    cookie_header = request['headers']['cookie']
                    cookies = cookie_header.split(';')
                    
                    for cookie in cookies:
                        if '=' in cookie:
                            name, value = cookie.strip().split('=', 1)
                            cookie_values_by_visit[name][visit_key] = value
    
    # Process cookies based on their structure
    current_time = datetime.datetime.now().timestamp()
    
    def process_cookie(cookie):
        nonlocal potential_id_count
        cookie_name = cookie.get('name')
        
        # Skip if cookie name not found in network data
        if cookie_name not in cookie_values_by_visit:
            return
            
        # Get values across visits
        values = list(cookie_values_by_visit[cookie_name].values())
        
        # Skip if we don't have enough visits
        if len(values) < 2:
            return
        
        # Criterion 1: Check if it's a persistent cookie with lifetime > 90 days
        long_lived = False
        if cookie.get('expires'):
            days_until_expiry = (cookie['expires'] - current_time) / (60 * 60 * 24)
            long_lived = days_until_expiry > 90
        
        # Criterion 2: Check if length is at least 8 bytes
        min_length = min(len(value) for value in values)
        sufficient_entropy = min_length >= 8
        
        # Criterion 3: Check if length varies by no more than 25%
        max_length = max(len(value) for value in values)
        length_variation = (max_length - min_length) / max_length if max_length > 0 else 0
        consistent_length = length_variation <= 0.25
        
        # Criterion 4: Check similarity using Ratcliff/Obershelp
        similarity_scores = []
        for i in range(len(values)):
            for j in range(i + 1, len(values)):
                similarity = difflib.SequenceMatcher(None, values[i], values[j]).ratio()
                similarity_scores.append(similarity)
        
        # Average similarity across all pairs
        avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0
        similar_values = avg_similarity >= 0.6
        
        # Check if all criteria are met
        is_potential_id = long_lived and sufficient_entropy and consistent_length and similar_values
        
        # Add flag to cookie (rename to reflect it's a potential identifier)
        cookie['is_potential_identifier'] = is_potential_id
        
        if is_potential_id:
            potential_id_count += 1
            category = cookie.get('classification', {}).get('category', 'Unknown')
            categories_counter[category] += 1
    
    # Handle different cookie data structures
    if isinstance(data['cookies'], dict):
        # Format: {'visit1': [cookies], 'visit2': [cookies]}
        for visit_cookies in data['cookies'].values():
            for cookie in visit_cookies:
                process_cookie(cookie)
    elif isinstance(data['cookies'], list):
        # Simple list format
        for cookie in data['cookies']:
            process_cookie(cookie)
    
    # Add summary to cookie_analysis section (rename to reflect potential identifiers)
    if 'cookie_analysis' in data:
        data['cookie_analysis']['potential_identifiers'] = {
            'total': potential_id_count,
            'by_category': dict(categories_counter)
        }

def analyze_cookie_domain_sharing(data):
    """
    Analyze which cookies are shared with which domains,
    with special focus on third-party sharing.
    """
    if 'network_data' not in data or 'domain_analysis' not in data:
        tqdm.write("Missing network_data or domain_analysis for cookie sharing analysis")
        return
    
    # Create lookup table for domain classification
    domain_classification = {}
    for domain_info in data['domain_analysis'].get('domains', []):
        domain_url = domain_info.get('domain', '')
        domain_classification[domain_url] = {
            'is_first_party': domain_info.get('is_first_party_domain', False),
            'is_infrastructure': domain_info.get('infrastructure_type') is not None,
            'categories': domain_info.get('categories', []),
            'organizations': domain_info.get('organizations', [])
        }
    
    # Analyze cookie sharing across domains
    cookie_sharing = defaultdict(lambda: {'all_domains': set(), 'third_party_domains': set()})
    
    for visit_key, visit_data in data['network_data'].items():
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
    if 'cookies' in data:
        if isinstance(data['cookies'], dict):
            # Format: {'visit1': [cookies], 'visit2': [cookies]}
            for visit_cookies in data['cookies'].values():
                for cookie in visit_cookies:
                    update_cookie_with_sharing(cookie)
        elif isinstance(data['cookies'], list):
            # Simple list format
            for cookie in data['cookies']:
                update_cookie_with_sharing(cookie)
    
    # Add summary to cookie_analysis section
    if 'cookie_analysis' in data:
        data['cookie_analysis']['cookie_sharing'] = {
            'total_cookies_shared': len(cookie_sharing),
            'cookies_shared_with_third_parties': len(cookies_with_third_parties),  # Count of unique cookies
            'third_party_domains_receiving_cookies': list(third_party_domains)
        }

if __name__ == "__main__":
    #add root path
    import sys
    root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.append(root_path)

    # Direct path to the data file
    data_path = os.path.join(root_path, "data", "crawler_data", "test", "webex.com.json")
    
    # If not found, try alternative name
    if not os.path.exists(data_path):
        tqdm.write(f"File not found at {data_path}")
        # Try alternative naming pattern
        alt_data_path = os.path.join(root_path, "data", "crawler_data", "test", "webex.com.json")
        if os.path.exists(alt_data_path):
            data_path = alt_data_path
            tqdm.write(f"Using alternative file: {data_path}")
        else:
            tqdm.write("Could not find test data file.")
            exit()

    analyze_persistence(data_path) 