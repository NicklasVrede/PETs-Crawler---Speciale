#!/usr/bin/env python3
"""
First-party tracking cookie analyzer

This script analyzes collected site data to identify first-party tracking cookies
using the criteria from Koop et al.:
1. Not a session cookie and has a lifetime of more than 90 days
2. Has a length of at least 8 bytes (enough entropy)
3. Unique in each measurement run with consistent length (±25%)
4. Similar values according to Ratcliff/Obershelp algorithm (≥60%)
"""

import os
import json
import difflib
import argparse
from datetime import datetime, timedelta
import re
from pathlib import Path
from tqdm import tqdm

def ratcliff_obershelp_similarity(s1, s2):
    """Calculate string similarity using Ratcliff/Obershelp algorithm"""
    return difflib.SequenceMatcher(None, s1, s2).ratio()

def parse_cookie_date(date_str):
    """Parse cookie expiration date to datetime object"""
    try:
        # Handle common formats
        if isinstance(date_str, (int, float)):
            # Unix timestamp (seconds since epoch)
            return datetime.fromtimestamp(date_str)
        elif re.match(r'^\d+$', str(date_str)):
            # Unix timestamp as string
            return datetime.fromtimestamp(int(date_str))
        else:
            # Try various date formats
            for fmt in [
                '%a, %d %b %Y %H:%M:%S %Z',  # RFC 1123
                '%a, %d-%b-%Y %H:%M:%S %Z',  # RFC 1036
                '%a, %d %b %Y %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',         # ISO 8601
                '%Y-%m-%d %H:%M:%S'
            ]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
    except Exception:
        pass
    return None

def is_tracking_cookie(cookies_across_visits):
    """
    Determine if a cookie is used for tracking based on criteria:
    1. Lifetime > 90 days and not session cookie
    2. Length ≥ 8 bytes
    3. Unique across visits with similar lengths (±25%)
    4. Similar values (≥60% similarity) using Ratcliff/Obershelp algorithm
    
    Args:
        cookies_across_visits: List of cookie objects for the same name across visits
    
    Returns:
        Boolean indicating if this cookie is used for tracking
    """
    # Need at least 2 visits to compare
    if len(cookies_across_visits) < 2:
        return False
    
    # Criterion 1: Check lifetime > 90 days and not session cookie
    for cookie in cookies_across_visits:
        # Skip if no expires attribute (session cookie)
        if not cookie.get('expires'):
            return False
        
        expiry = parse_cookie_date(cookie['expires'])
        # Use creation time or timestamp as cookie creation time
        creation = datetime.now()  # Default
        if cookie.get('created'):
            creation = parse_cookie_date(cookie['created'])
        elif cookie.get('timestamp'):
            creation = parse_cookie_date(cookie['timestamp'])
        
        if not expiry:
            continue  # Skip if dates can't be parsed
            
        lifetime_days = (expiry - creation).days
        if lifetime_days < 90:
            return False
    
    # Criterion 2: Check length ≥ 8 bytes
    for cookie in cookies_across_visits:
        if len(cookie['value'].encode('utf-8')) < 8:
            return False
    
    # Criterion 3: Check uniqueness and similar lengths
    values = [cookie['value'] for cookie in cookies_across_visits]
    if len(set(values)) != len(values):  # Not all values are unique
        return False
    
    # Check length similarity (within 25%)
    lengths = [len(value.encode('utf-8')) for value in values]
    base_length = lengths[0]
    for length in lengths[1:]:
        ratio = min(length, base_length) / max(length, base_length)
        if ratio < 0.75:  # More than 25% difference
            return False
    
    # Criterion 4: Check Ratcliff/Obershelp similarity ≥ 60%
    base_value = values[0]
    for value in values[1:]:
        similarity = ratcliff_obershelp_similarity(base_value, value)
        if similarity < 0.6:  # Less than 60% similar
            return False
    
    # All criteria passed
    return True

def analyze_first_party_tracking(domain, site_data):
    """Analyze site data focusing only on cookies"""
    network_data = site_data.get('network_data', {})
    
    print(f"\nAnalyzing cookies for {domain}")
    print("Network data keys:", network_data.keys())
    
    # Look at cookie_analysis if it exists
    if 'cookie_analysis' in network_data:
        print("\nCookie analysis data:")
        print(json.dumps(network_data['cookie_analysis'], indent=2))
    
    # Look at visits data
    visits = network_data.get('visits', [])
    if visits:
        print("\nVisits data structure:")
        print(f"Found {len(visits)} visits")
        print("First visit keys:", visits[0].keys() if visits else "No visits")
        if visits and 'network' in visits[0]:
            print("Network keys in first visit:", visits[0]['network'].keys())
    
    cookies = network_data.get('cookies_set', [])
    print(f"\nDirect cookies_set found: {len(cookies)}")
    
    return []

def load_site_data(data_dir, domain=None):
    """
    Load JSON data for a specific domain or all domains
    
    Args:
        data_dir: Directory containing site data
        domain: Optional domain to filter by
        
    Returns:
        Dictionary mapping domains to their data
    """
    site_data = {}
    data_path = Path(data_dir)
    
    # Ensure directory exists
    if not data_path.exists():
        print(f"Error: Data directory {data_dir} does not exist")
        print(f"Current working directory: {os.getcwd()}")
        return site_data
    
    # Find JSON files in the data directory
    json_files = list(data_path.glob('**/*.json'))
    print(f"Found {len(json_files)} JSON files in {data_dir} and subdirectories")
    
    # Debug: List all subdirectories to help troubleshoot
    print("Subdirectories found:")
    for subdir in data_path.glob('*'):
        if subdir.is_dir():
            print(f"  - {subdir.name} ({len(list(subdir.glob('*.json')))} JSON files)")
    
    if domain:
        # Filter by domain if specified
        json_files = [f for f in json_files if domain.lower() in f.name.lower()]
        print(f"Filtered to {len(json_files)} files for domain {domain}")
    
    # Debug: Show first few files found
    if json_files:
        print("First few JSON files found:")
        for f in json_files[:5]:
            print(f"  - {f}")
        if len(json_files) > 5:
            print(f"  - ... and {len(json_files) - 5} more")
    else:
        print("No JSON files found. Check directory structure and file extensions.")
    
    # Group files by domain for debug output
    domains_found = {}
    for json_file in json_files:
        file_domain = json_file.stem
        if file_domain not in domains_found:
            domains_found[file_domain] = []
        domains_found[file_domain].append(str(json_file.relative_to(data_path)))
    
    print(f"Found data for {len(domains_found)} unique domains")
    
    # Load the data
    for json_file in tqdm(json_files, desc="Loading data"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Get domain from filename (remove extension)
            file_domain = json_file.stem
            
            if file_domain not in site_data:
                site_data[file_domain] = []
                
            # Add data to site_data
            site_data[file_domain].append(data)
                
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    return site_data

def main():
    parser = argparse.ArgumentParser(description='Analyze cookies for tracking')
    parser.add_argument('--data-dir', '-d', type=str, default='data/crawler_data',
                        help='Directory containing site data JSON files')
    args = parser.parse_args()
    
    data_path = Path(args.data_dir)
    json_files = list(data_path.glob('**/*.json'))
    print(f"Found {len(json_files)} JSON files")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                site_data = json.load(f)
            domain = site_data.get('domain', '')
            if domain:
                analyze_first_party_tracking(domain, site_data)
        except Exception as e:
            print(f"Error processing {json_file}: {e}")

if __name__ == "__main__":
    main() 