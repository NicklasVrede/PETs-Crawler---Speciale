import os
import json
import re
from analyzers.cache_analyser import CacheAnalyzer

def process_site_file(file_path, analyzer, create_backup=False):
    """Process a single site file, adding identifier flags to individual entries."""
    # Read the original file
    with open(file_path, 'r', encoding='utf-8') as f:
        site_data = json.load(f)
    
    # Create backup if requested
    if create_backup:
        backup_path = file_path + '.bak'
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(site_data, f, indent=2, default=str)
    
    # Try to run the analysis, but fall back to direct detection if it fails
    try:
        analysis = analyzer.analyze_site(site_data)
        # If analysis returned None or empty dict, use fallback detection
        if not analysis:
            analysis = direct_identifier_detection(site_data)
    except Exception as e:
        print(f"Analyzer failed: {str(e)}, using direct detection instead")
        analysis = direct_identifier_detection(site_data)
    
    # Get list of potential identifiers
    potential_identifiers = analysis.get('potential_identifiers', [])
    if potential_identifiers is None:
        potential_identifiers = []
    
    # Create lookup for quick identification
    identifier_lookup = {}
    for identifier in potential_identifiers:
        storage_type = identifier.get('storage_type', '')
        key = identifier.get('key', '')
        visit = identifier.get('visit', '')
        
        # Create composite key for lookup
        lookup_key = f"{storage_type}:{visit}:{key}"
        identifier_lookup[lookup_key] = {
            'confidence': identifier.get('confidence', 0),
            'reasons': identifier.get('reasons', [])
        }
    
    # Create a mapping of storage values and keys to their sharing information
    value_sharing_info = {}
    key_sharing_info = {}
    
    # First, build a domain info lookup from the domain_analysis section
    domain_info = {}
    if 'domain_analysis' in site_data and 'domains' in site_data['domain_analysis']:
        for domain_data in site_data['domain_analysis']['domains']:
            domain_url = domain_data.get('domain', '')
            if domain_url:
                # Strip off https:// if present for easier matching
                clean_domain = domain_url.replace('https://', '')
                domain_info[clean_domain] = {
                    'categories': domain_data.get('categories', []),
                    'organizations': domain_data.get('organizations', []),
                    'is_infrastructure': domain_data.get('infrastructure_type') is not None
                }
    
    # Collect all keys and values from storage for potential sharing detection
    all_keys = set()
    
    if 'storage' in site_data and 'visits' in site_data['storage']:
        for visit_data in site_data['storage']['visits'].values():
            for storage_type in ['local_storage', 'session_storage']:
                if storage_type in visit_data:
                    for item in visit_data.get(storage_type, []) or []:
                        if isinstance(item, dict):
                            key = item.get('key', '')
                            if key and len(key) >= 8:  # Only consider keys that are long enough
                                all_keys.add(key)
    
    # Now check all requests for both value and key sharing
    if 'requests' in site_data:
        requests = site_data.get('requests', [])
        for request in requests:
            domain = request.get('domain', '')
            if not domain:
                continue
                
            # Get domain categories and organizations
            domain_categories = []
            domain_organizations = []
            is_infrastructure = False
            
            if domain in domain_info:
                domain_categories = domain_info[domain]['categories']
                domain_organizations = domain_info[domain]['organizations']
                is_infrastructure = domain_info[domain]['is_infrastructure']
            
            # Get request URL and data for searching
            request_url = str(request.get('url', '') or '')
            request_data = str(request.get('post_data', '') or '')
            
            # Check each key to see if it appears in the request
            for key in all_keys:
                if key in request_url or key in request_data:
                    if key not in key_sharing_info:
                        key_sharing_info[key] = {
                            'domains': set(),
                            'categories': set(),
                            'organizations': set(),
                            'is_infrastructure_only': True
                        }
                    
                    key_sharing_info[key]['domains'].add(domain)
                    
                    for category in domain_categories:
                        key_sharing_info[key]['categories'].add(category)
                    
                    for org in domain_organizations:
                        key_sharing_info[key]['organizations'].add(org)
                    
                    if not is_infrastructure:
                        key_sharing_info[key]['is_infrastructure_only'] = False
    
    # Now process shared items
    if 'third_party_sharing' in analysis and 'items_shared' in analysis['third_party_sharing']:
        for shared_item in analysis['third_party_sharing']['items_shared']:
            value = shared_item.get('value', '')
            if value:
                # Remove trailing ellipsis if present
                if value.endswith('...'):
                    clean_value = value[:-3]
                else:
                    clean_value = value
                
                # If we don't have this value yet, initialize it
                if clean_value not in value_sharing_info:
                    value_sharing_info[clean_value] = {
                        'domains': set(),
                        'categories': set(),
                        'organizations': set(),
                        'is_infrastructure_only': True
                    }
                
                domain = shared_item.get('third_party_domain', '')
                value_sharing_info[clean_value]['domains'].add(domain)
                
                # Try to get domain info from our lookup
                if domain in domain_info:
                    for category in domain_info[domain]['categories']:
                        value_sharing_info[clean_value]['categories'].add(category)
                    
                    for org in domain_info[domain]['organizations']:
                        value_sharing_info[clean_value]['organizations'].add(org)
                    
                    if not domain_info[domain]['is_infrastructure']:
                        value_sharing_info[clean_value]['is_infrastructure_only'] = False
    
    # Flag individual storage entries and add to "analysis" object
    if 'storage' in site_data and 'visits' in site_data['storage']:
        for visit_num, visit_data in site_data['storage']['visits'].items():
            # Process localStorage
            if 'local_storage' in visit_data:
                for item in visit_data['local_storage']:
                    key = item.get('key', '')
                    value = str(item.get('value', ''))
                    lookup_key = f"localStorage:{visit_num}:{key}"
                    
                    # Create analysis object
                    item['analysis'] = {}
                    
                    # If already identified by analyzer
                    if lookup_key in identifier_lookup:
                        item['analysis']['is_potential_identifier'] = True
                        item['analysis']['confidence'] = identifier_lookup[lookup_key]['confidence']
                        item['analysis']['reasons'] = identifier_lookup[lookup_key]['reasons']
                    else:
                        # Direct detection based on criteria
                        reasons = []
                        confidence = 0
                        
                        # 1. Long, Unique, and Encoded Strings
                        if len(value) >= 16:
                            reasons.append("Long value (≥16 chars)")
                            confidence += 0.1
                            
                            # Check if it contains both letters and numbers
                            if re.search(r'[a-zA-Z]', value) and re.search(r'[0-9]', value):
                                reasons.append("Contains both letters and numbers")
                                confidence += 0.1
                        
                        # Check for UUID format
                        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.I)
                        if uuid_pattern.match(value):
                            reasons.append("Matches UUID format")
                            confidence += 0.4
                        
                        # Check for Base64 encoding
                        base64_pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
                        if base64_pattern.match(value) and len(value) >= 16:
                            reasons.append("Appears to be Base64-encoded")
                            confidence += 0.3
                        
                        # Check for hash patterns
                        hash_patterns = {
                            'md5': re.compile(r'^[0-9a-f]{32}$', re.I),
                            'sha1': re.compile(r'^[0-9a-f]{40}$', re.I),
                            'sha256': re.compile(r'^[0-9a-f]{64}$', re.I),
                            'sha512': re.compile(r'^[0-9a-f]{128}$', re.I)
                        }
                        for hash_type, pattern in hash_patterns.items():
                            if pattern.match(value):
                                reasons.append(f"Matches {hash_type.upper()} hash format")
                                confidence += 0.4
                                break
                        
                        # 4. Tracking-Related Key Names
                        key_lower = key.lower()
                        tracking_keywords = [
                            'id', 'user', 'visitor', 'client', 'device', 'machine', 'fingerprint', 'track',
                            'analytics', 'session', 'token', 'uuid', 'guid', 'uid', 'fp', 'account',
                            'profile', 'customer', 'tracking', 'identify', 'canvas', 'persist', 'unique'
                        ]
                        for keyword in tracking_keywords:
                            if keyword in key_lower:
                                reasons.append(f"Key contains tracking-related term: '{keyword}'")
                                confidence += 0.3
                                break
                        
                        # Assign results
                        if confidence > 0:
                            item['analysis']['is_potential_identifier'] = True
                            item['analysis']['confidence'] = min(confidence, 1.0)  # Cap at 1.0
                            item['analysis']['reasons'] = reasons
                        else:
                            item['analysis']['is_potential_identifier'] = False
                    
                    # Add sharing information if available (check both value and key)
                    if value in value_sharing_info or key in key_sharing_info:
                        item['analysis']['is_shared'] = True
                        item['analysis']['shared_with'] = {
                            'domains': [],
                            'categories': [],
                            'organizations': [],
                            'is_infrastructure_only': True,
                            'shared_by': []  # What was shared - key, value, or both
                        }
                        
                        # Add value sharing info if available
                        if value in value_sharing_info:
                            sharing = value_sharing_info[value]
                            item['analysis']['shared_with']['domains'].extend(list(sharing['domains']))
                            item['analysis']['shared_with']['categories'].extend(list(sharing['categories']))
                            item['analysis']['shared_with']['organizations'].extend(list(sharing['organizations']))
                            item['analysis']['shared_with']['is_infrastructure_only'] &= sharing['is_infrastructure_only']
                            item['analysis']['shared_with']['shared_by'].append('value')
                        
                        # Add key sharing info if available
                        if key in key_sharing_info:
                            sharing = key_sharing_info[key]
                            item['analysis']['shared_with']['domains'].extend(list(sharing['domains']))
                            item['analysis']['shared_with']['categories'].extend(list(sharing['categories']))
                            item['analysis']['shared_with']['organizations'].extend(list(sharing['organizations']))
                            item['analysis']['shared_with']['is_infrastructure_only'] &= sharing['is_infrastructure_only']
                            item['analysis']['shared_with']['shared_by'].append('key')
                        
                        # Remove duplicates
                        item['analysis']['shared_with']['domains'] = list(set(item['analysis']['shared_with']['domains']))
                        item['analysis']['shared_with']['categories'] = list(set(item['analysis']['shared_with']['categories']))
                        item['analysis']['shared_with']['organizations'] = list(set(item['analysis']['shared_with']['organizations']))
                        
                        # Increase confidence if shared with non-infrastructure parties
                        if not item['analysis']['shared_with']['is_infrastructure_only'] and item['analysis'].get('confidence', 0) > 0:
                            item['analysis']['confidence'] = min(item['analysis']['confidence'] + 0.2, 1.0)
                            
                            if 'key' in item['analysis']['shared_with']['shared_by']:
                                item['analysis']['reasons'].append("Key shared with non-infrastructure third parties")
                            else:
                                item['analysis']['reasons'].append("Value shared with non-infrastructure third parties")
                    else:
                        item['analysis']['is_shared'] = False
            
            # Process sessionStorage (similar logic)
            if 'session_storage' in visit_data:
                for item in visit_data['session_storage']:
                    # Similar code as localStorage processing
                    key = item.get('key', '')
                    value = str(item.get('value', ''))
                    lookup_key = f"sessionStorage:{visit_num}:{key}"
                    
                    # Create analysis object
                    item['analysis'] = {}
                    
                    # Check if already identified
                    if lookup_key in identifier_lookup:
                        item['analysis']['is_potential_identifier'] = True
                        item['analysis']['confidence'] = identifier_lookup[lookup_key]['confidence']
                        item['analysis']['reasons'] = identifier_lookup[lookup_key]['reasons']
                    else:
                        # Simplified version for session storage
                        key_lower = key.lower()
                        tracking_keywords = [
                            'id', 'user', 'visitor', 'client', 'device', 'machine', 'fingerprint', 'track',
                            'analytics', 'session', 'token', 'uuid', 'guid', 'uid', 'fp', 'account',
                            'profile', 'customer', 'tracking', 'identify', 'canvas', 'persist', 'unique'
                        ]
                        
                        reasons = []
                        confidence = 0
                        
                        for keyword in tracking_keywords:
                            if keyword in key_lower:
                                reasons.append(f"Key contains tracking-related term: '{keyword}'")
                                confidence += 0.3
                                break
                        
                        if confidence > 0:
                            item['analysis']['is_potential_identifier'] = True
                            item['analysis']['confidence'] = confidence
                            item['analysis']['reasons'] = reasons
                        else:
                            item['analysis']['is_potential_identifier'] = False
                    
                    # Add sharing information if available (check both value and key)
                    if value in value_sharing_info or key in key_sharing_info:
                        item['analysis']['is_shared'] = True
                        item['analysis']['shared_with'] = {
                            'domains': [],
                            'categories': [],
                            'organizations': [],
                            'is_infrastructure_only': True,
                            'shared_by': []  # What was shared - key, value, or both
                        }
                        
                        # Add value sharing info if available
                        if value in value_sharing_info:
                            sharing = value_sharing_info[value]
                            item['analysis']['shared_with']['domains'].extend(list(sharing['domains']))
                            item['analysis']['shared_with']['categories'].extend(list(sharing['categories']))
                            item['analysis']['shared_with']['organizations'].extend(list(sharing['organizations']))
                            item['analysis']['shared_with']['is_infrastructure_only'] &= sharing['is_infrastructure_only']
                            item['analysis']['shared_with']['shared_by'].append('value')
                        
                        # Add key sharing info if available
                        if key in key_sharing_info:
                            sharing = key_sharing_info[key]
                            item['analysis']['shared_with']['domains'].extend(list(sharing['domains']))
                            item['analysis']['shared_with']['categories'].extend(list(sharing['categories']))
                            item['analysis']['shared_with']['organizations'].extend(list(sharing['organizations']))
                            item['analysis']['shared_with']['is_infrastructure_only'] &= sharing['is_infrastructure_only']
                            item['analysis']['shared_with']['shared_by'].append('key')
                        
                        # Remove duplicates
                        item['analysis']['shared_with']['domains'] = list(set(item['analysis']['shared_with']['domains']))
                        item['analysis']['shared_with']['categories'] = list(set(item['analysis']['shared_with']['categories']))
                        item['analysis']['shared_with']['organizations'] = list(set(item['analysis']['shared_with']['organizations']))
                        
                        # Increase confidence if shared with non-infrastructure parties
                        if not item['analysis']['shared_with']['is_infrastructure_only'] and item['analysis'].get('confidence', 0) > 0:
                            item['analysis']['confidence'] = min(item['analysis']['confidence'] + 0.2, 1.0)
                            
                            if 'key' in item['analysis']['shared_with']['shared_by']:
                                item['analysis']['reasons'].append("Key shared with non-infrastructure third parties")
                            else:
                                item['analysis']['reasons'].append("Value shared with non-infrastructure third parties")
                    else:
                        item['analysis']['is_shared'] = False
            
            # Process cacheStorage
            if 'cache_storage' in visit_data:
                for item in visit_data['cache_storage']:
                    # Similar processing for cache storage
                    name = item.get('name', '')
                    lookup_key = f"cacheStorage:{visit_num}:{name}"
                    
                    # Create analysis object
                    item['analysis'] = {}
                    
                    # Check if already identified
                    if lookup_key in identifier_lookup:
                        item['analysis']['is_potential_identifier'] = True
                        item['analysis']['confidence'] = identifier_lookup[lookup_key]['confidence']
                        item['analysis']['reasons'] = identifier_lookup[lookup_key]['reasons']
                    else:
                        # Simple check for tracking-related names in cache
                        name_lower = name.lower()
                        tracking_keywords = ['track', 'analytic', 'stat', 'pixel', 'beacon', 'monitor']
                        
                        reasons = []
                        confidence = 0
                        
                        for keyword in tracking_keywords:
                            if keyword in name_lower:
                                reasons.append(f"Cache name contains tracking-related term: '{keyword}'")
                                confidence += 0.6
                                break
                        
                        if confidence > 0:
                            item['analysis']['is_potential_identifier'] = True
                            item['analysis']['confidence'] = confidence
                            item['analysis']['reasons'] = reasons
                        else:
                            item['analysis']['is_potential_identifier'] = False
                    
                    # For cache storage, we don't have a direct value to check for sharing
                    item['analysis']['is_shared'] = False
    
    # Count identifiers for statistics
    total_identifiers = 0
    high_confidence = 0
    medium_confidence = 0
    low_confidence = 0
    shared_identifiers = 0
    
    if 'storage' in site_data and 'visits' in site_data['storage']:
        for visit_data in site_data['storage']['visits'].values():
            for storage_type in ['local_storage', 'session_storage', 'cache_storage']:
                if storage_type in visit_data:
                    for item in visit_data[storage_type]:
                        analysis_data = item.get('analysis', {})
                        if analysis_data.get('is_potential_identifier', False):
                            total_identifiers += 1
                            confidence = analysis_data.get('confidence', 0)
                            
                            if confidence >= 0.8:
                                high_confidence += 1
                            elif confidence >= 0.5:
                                medium_confidence += 1
                            else:
                                low_confidence += 1
                            
                            if analysis_data.get('is_shared', False):
                                shared_identifiers += 1
    
    # Get persistence and third-party sharing from the original analysis
    persistent_identifiers = 0
    if 'persistence_analysis' in analysis and 'persistent_items' in analysis['persistence_analysis']:
        persistent_items = analysis['persistence_analysis']['persistent_items']
        if persistent_items is not None:
            persistent_identifiers = len(persistent_items)
    
    third_party_sharing = 0
    if 'third_party_sharing' in analysis and 'sharing_count' in analysis['third_party_sharing']:
        third_party_sharing = analysis['third_party_sharing']['sharing_count']
    
    # Update statistics
    if 'statistics' not in site_data:
        site_data['statistics'] = {}
    
    # Add our identifier analysis to the statistics without overwriting other stats
    site_data['statistics']['identifier_analysis'] = {
        'total_potential_identifiers': total_identifiers,
        'high_confidence_identifiers': high_confidence,
        'medium_confidence_identifiers': medium_confidence,
        'low_confidence_identifiers': low_confidence,
        'persistent_identifiers': persistent_identifiers,
        'shared_identifiers': shared_identifiers,
        'third_party_sharing': third_party_sharing
    }
    
    # If we have enhanced third-party sharing data (categories and organizations)
    if 'third_party_sharing' in analysis and 'sharing_by_category' in analysis['third_party_sharing']:
        site_data['statistics']['identifier_analysis']['sharing_by_category'] = analysis['third_party_sharing']['sharing_by_category']
    
    if 'third_party_sharing' in analysis and 'sharing_by_organization' in analysis['third_party_sharing']:
        site_data['statistics']['identifier_analysis']['sharing_by_organization'] = analysis['third_party_sharing']['sharing_by_organization']
    
    # Save the updated data back to the original file
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(site_data, f, indent=2, default=str)
    
    # Print a brief summary
    print_summary(os.path.basename(file_path), total_identifiers, high_confidence, shared_identifiers)

def direct_identifier_detection(site_data):
    """Perform direct identifier detection without relying on the analyzer."""
    results = {
        'potential_identifiers': [],
        'identifier_count': 0,
        'scoring': {
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0
        },
        'persistence_analysis': {
            'persistent_items': []
        },
        'third_party_sharing': {
            'sharing_count': 0
        }
    }
    
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.I)
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')
    hash_patterns = {
        'md5': re.compile(r'^[0-9a-f]{32}$', re.I),
        'sha1': re.compile(r'^[0-9a-f]{40}$', re.I),
        'sha256': re.compile(r'^[0-9a-f]{64}$', re.I),
        'sha512': re.compile(r'^[0-9a-f]{128}$', re.I)
    }
    tracking_keywords = [
        'id', 'user', 'visitor', 'client', 'device', 'machine', 'fingerprint', 'track',
        'analytics', 'session', 'token', 'uuid', 'guid', 'uid', 'fp', 'account',
        'profile', 'customer', 'tracking', 'identify', 'canvas', 'persist', 'unique'
    ]
    
    # Find potential identifiers in storage
    if 'storage' in site_data and 'visits' in site_data['storage']:
        for visit_num, visit_data in site_data['storage']['visits'].items():
            # Process localStorage
            if 'local_storage' in visit_data:
                for item in visit_data['local_storage']:
                    key = item.get('key', '')
                    value = str(item.get('value', ''))
                    
                    # Check for identifier characteristics
                    reasons = []
                    confidence = 0
                    
                    # Long values
                    if len(value) >= 16:
                        reasons.append("Long value (≥16 chars)")
                        confidence += 0.1
                        
                        # Check if it contains both letters and numbers
                        if re.search(r'[a-zA-Z]', value) and re.search(r'[0-9]', value):
                            reasons.append("Contains both letters and numbers")
                            confidence += 0.1
                    
                    # Check for UUID format
                    if uuid_pattern.match(value):
                        reasons.append("Matches UUID format")
                        confidence += 0.4
                    
                    # Check for Base64 encoding
                    elif base64_pattern.match(value) and len(value) >= 16:
                        reasons.append("Appears to be Base64-encoded")
                        confidence += 0.3
                    
                    # Check for hash patterns
                    for hash_type, pattern in hash_patterns.items():
                        if pattern.match(value):
                            reasons.append(f"Matches {hash_type.upper()} hash format")
                            confidence += 0.4
                            break
                    
                    # Tracking-Related Key Names
                    key_lower = key.lower()
                    for keyword in tracking_keywords:
                        if keyword in key_lower:
                            reasons.append(f"Key contains tracking-related term: '{keyword}'")
                            confidence += 0.3
                            break
                    
                    # If looks like an identifier, add to results
                    if confidence > 0:
                        results['potential_identifiers'].append({
                            'storage_type': 'localStorage',
                            'visit': visit_num,
                            'key': key,
                            'value': value[:30] + ('...' if len(value) > 30 else ''),
                            'confidence': min(confidence, 1.0),
                            'reasons': reasons
                        })
                        
                        results['identifier_count'] += 1
                        
                        if confidence >= 0.8:
                            results['scoring']['high_confidence'] += 1
                        elif confidence >= 0.5:
                            results['scoring']['medium_confidence'] += 1
                        else:
                            results['scoring']['low_confidence'] += 1
            
            # Process sessionStorage (similar logic)
            if 'session_storage' in visit_data:
                # Similar code as localStorage processing
                pass
            
            # Process cacheStorage (abbreviated logic)
            if 'cache_storage' in visit_data:
                # Cache analysis would go here
                pass
    
    return results

def print_summary(filename, identifiers, high_conf, shared=None):
    """Print a very brief summary of what was found."""
    if identifiers > 0:
        if shared is not None:
            print(f"{filename}: Found {identifiers} potential identifiers ({high_conf} high confidence, {shared} shared with third parties)")
        else:
            print(f"{filename}: Found {identifiers} potential identifiers ({high_conf} high confidence)")
    else:
        print(f"{filename}: No potential identifiers found")

# MAIN CODE HERE - This will run directly
if __name__ == "__main__":
    import sys
    
    # Use command line argument for directory if provided, otherwise use default
    data_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/crawler_data/i_dont_care_about_cookies'
    
    # Create analyzer
    analyzer = CacheAnalyzer()
    
    # Get list of JSON files
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    print(f"Found {len(json_files)} JSON files in {data_dir}")
    
    # Process each file WITHOUT creating backups
    for filename in json_files:
        file_path = os.path.join(data_dir, filename)
        try:
            process_site_file(file_path, analyzer, create_backup=False)
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print(f"\nCompleted analysis of {len(json_files)} files") 