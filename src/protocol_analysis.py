import os
import json
import csv
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from urllib.parse import urlparse
from tqdm import tqdm
from collections import defaultdict

def extract_protocol_data(json_file):
    """Extract protocol information from network requests in a JSON file"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Initialize counters for protocols
        protocols = {'http': 0, 'https': 0}
        domains_by_protocol = {'http': set(), 'https': set()}
        all_third_party_domains = set()
        
        # Get the primary domain
        site_domain = data.get('domain', '').lower()
        if not site_domain:
            # Extract from filename if not in data
            filename = os.path.basename(json_file)
            site_domain = filename[:-5].lower()  # Remove '.json'
        
        # First-party domains (to exclude from third-party analysis)
        first_party_domains = {site_domain}
        if site_domain.startswith('www.'):
            first_party_domains.add(site_domain[4:])
        else:
            first_party_domains.add(f"www.{site_domain}")
            
        # Get requests from different possible formats
        requests = []
        
        # Format 1: network_data with visit keys
        network_data = None
        for key in ['0', '1', 'visit0', 'visit1']:
            if key in data.get('network_data', {}):
                network_data = data['network_data'][key]
                requests = network_data.get('requests', [])
                break
        
        # Format 2: requests directly in the root
        if not requests and 'requests' in data:
            requests = data['requests']
            
        # Process requests
        for req in requests:
            url = req.get('url', '')
            if not url:
                continue
                
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()
                
                # Remove www. prefix if present
                if domain.startswith('www.'):
                    domain = domain[4:]
                
                # Skip first-party requests
                if domain in first_party_domains:
                    continue
                    
                # Add to all third-party domains
                all_third_party_domains.add(domain)
                
                # Count protocols
                protocol = parsed_url.scheme
                if protocol in ['http', 'https']:
                    protocols[protocol] += 1
                    domains_by_protocol[protocol].add(domain)
            except Exception:
                continue
        
        # Calculate domain counts by protocol category
        https_only_domains = domains_by_protocol['https'] - domains_by_protocol['http']
        http_only_domains = domains_by_protocol['http'] - domains_by_protocol['https']
        both_protocols_domains = domains_by_protocol['https'] & domains_by_protocol['http']
        
        return {
            'https_only': len(https_only_domains),
            'http_only': len(http_only_domains),
            'http_https': len(both_protocols_domains),
            'total_domains': len(all_third_party_domains)
        }
        
    except Exception as e:
        print(f"Error processing {json_file}: {e}")
        return None

def analyze_protocols_by_extension(json_dir, output_dir):
    """Analyze protocol usage across different browser extensions and blocklists"""
    # Make sure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # List of extensions/profiles to analyze - use actual profile names from config
    extension_dirs = [d for d in os.listdir(json_dir) 
                    if os.path.isdir(os.path.join(json_dir, d))]
    
    # Define which profiles to include in which graph
    # Left side (browser extensions)
    browser_extensions = [
        'no_extensions',
        'adblock_plus',
        'disconnect',
        'ghostery_tracker_&_ad_blocker',
        'privacy_badger',
        'ublock',
        'ublock_origin_lite'
    ]
    
    # Right side (cookie/consent managers)
    cookie_managers = [
        'no_extensions',
        'consent_o_matic_opt_out',
        'consent_o_matic_opt_in',
        'i_dont_care_about_cookies',
        'super_agent'
    ]
    
    # Filter available dirs to match expected lists
    available_extensions = [d for d in extension_dirs if d in browser_extensions]
    available_managers = [d for d in extension_dirs if d in cookie_managers]
    
    # Process each extension
    results = []
    
    # Process browser extensions
    for ext in tqdm(available_extensions, desc="Processing browser extensions"):
        ext_dir = os.path.join(json_dir, ext)
        files = [os.path.join(ext_dir, f) for f in os.listdir(ext_dir) 
                if f.endswith('.json')]
        
        # Aggregate results across all files for this extension
        ext_totals = {'https_only': 0, 'http_only': 0, 'http_https': 0, 'total_domains': 0}
        
        for file in files:
            data = extract_protocol_data(file)
            if data:
                for key in ext_totals:
                    ext_totals[key] += data[key]
        
        # Calculate percentages
        if ext_totals['total_domains'] > 0:
            total = ext_totals['total_domains']
            results.append({
                'extension': ext,
                'type': 'browser',
                'https_only_pct': ext_totals['https_only'] / total * 100,
                'http_only_pct': ext_totals['http_only'] / total * 100,
                'http_https_pct': ext_totals['http_https'] / total * 100
            })
    
    # Process cookie/consent managers
    for manager in tqdm(available_managers, desc="Processing cookie/consent managers"):
        if manager == 'no_extensions':
            continue  # Already processed in browser extensions
            
        manager_dir = os.path.join(json_dir, manager)
        files = [os.path.join(manager_dir, f) for f in os.listdir(manager_dir) 
                if f.endswith('.json')]
        
        # Aggregate results across all files for this manager
        manager_totals = {'https_only': 0, 'http_only': 0, 'http_https': 0, 'total_domains': 0}
        
        for file in files:
            data = extract_protocol_data(file)
            if data:
                for key in manager_totals:
                    manager_totals[key] += data[key]
        
        # Calculate percentages
        if manager_totals['total_domains'] > 0:
            total = manager_totals['total_domains']
            results.append({
                'extension': manager,
                'type': 'cookie_manager',
                'https_only_pct': manager_totals['https_only'] / total * 100,
                'http_only_pct': manager_totals['http_only'] / total * 100,
                'http_https_pct': manager_totals['http_https'] / total * 100
            })
    
    # Add no_extensions to cookie managers as well if it exists
    if 'no_extensions' in available_extensions:
        plain_data = next((r for r in results if r['extension'] == 'no_extensions'), None)
        if plain_data:
            plain_cookie = plain_data.copy()
            plain_cookie['type'] = 'cookie_manager'
            results.append(plain_cookie)
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Save results to CSV
    csv_file = os.path.join(output_dir, 'protocol_analysis.csv')
    results_df.to_csv(csv_file, index=False)
    print(f"Saved protocol analysis to {csv_file}")
    
    # Generate visualization
    generate_protocol_visualization(results_df, output_dir)
    
    return results_df

def generate_protocol_visualization(df, output_dir):
    """Generate visualization similar to Figure 3 in the reference"""
    # Create figure with two subplots side by side
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    
    # Define display names for better readability
    name_mapping = {
        'no_extensions': 'plain',
        'adblock_plus': 'adblockplus',
        'ghostery_tracker_&_ad_blocker': 'ghostery',
        'privacy_badger': 'privacybadger',
        'ublock': 'ublock-origin',
        'ublock_origin_lite': 'ublock-lite',
        'consent_o_matic_opt_out': 'consent-opt-out',
        'consent_o_matic_opt_in': 'consent-opt-in',
        'i_dont_care_about_cookies': 'idontcare',
        'super_agent': 'superagent'
    }
    
    # Define order of extensions for browser and cookie managers
    browser_order = [
        'no_extensions', 'adblock_plus', 'disconnect', 
        'ghostery_tracker_&_ad_blocker', 'privacy_badger',
        'ublock', 'ublock_origin_lite'
    ]
    
    cookie_order = [
        'no_extensions', 'consent_o_matic_opt_out', 'consent_o_matic_opt_in',
        'i_dont_care_about_cookies', 'super_agent'
    ]
    
    # Filter and sort data
    browser_df = df[df['type'] == 'browser'].copy()
    cookie_df = df[df['type'] == 'cookie_manager'].copy()
    
    # Apply display name mapping
    browser_df['display_name'] = browser_df['extension'].map(
        lambda x: name_mapping.get(x, x))
    cookie_df['display_name'] = cookie_df['extension'].map(
        lambda x: name_mapping.get(x, x))
    
    # Sort according to desired order
    browser_df['order'] = browser_df['extension'].map(
        lambda x: browser_order.index(x) if x in browser_order else 999)
    cookie_df['order'] = cookie_df['extension'].map(
        lambda x: cookie_order.index(x) if x in cookie_order else 999)
    
    browser_df = browser_df.sort_values('order')
    cookie_df = cookie_df.sort_values('order')
    
    # Plot browser extensions (left plot)
    bottom_browser = np.zeros(len(browser_df))
    
    # HTTP only (light blue)
    ax1.bar(browser_df['display_name'], browser_df['http_only_pct'], 
            bottom=bottom_browser, color='#ADD8E6', label='http only')
    bottom_browser += browser_df['http_only_pct']
    
    # HTTP+HTTPS (blue)
    ax1.bar(browser_df['display_name'], browser_df['http_https_pct'], 
            bottom=bottom_browser, color='#1E90FF', label='http+https')
    bottom_browser += browser_df['http_https_pct']
    
    # HTTPS only (green)
    ax1.bar(browser_df['display_name'], browser_df['https_only_pct'], 
            bottom=bottom_browser, color='#90EE90', label='https only')
    
    # Plot cookie/consent managers (right plot)
    bottom_cookie = np.zeros(len(cookie_df))
    
    # HTTP only (light blue)
    ax2.bar(cookie_df['display_name'], cookie_df['http_only_pct'], 
            bottom=bottom_cookie, color='#ADD8E6')
    bottom_cookie += cookie_df['http_only_pct']
    
    # HTTP+HTTPS (blue)
    ax2.bar(cookie_df['display_name'], cookie_df['http_https_pct'], 
            bottom=bottom_cookie, color='#1E90FF')
    bottom_cookie += cookie_df['http_https_pct']
    
    # HTTPS only (green)
    ax2.bar(cookie_df['display_name'], cookie_df['https_only_pct'], 
            bottom=bottom_cookie, color='#90EE90')
    
    # Set titles and labels
    ax1.set_title('Activated Browser Extension')
    ax2.set_title('Activated Cookie/Consent Manager')
    
    ax1.set_ylabel('Requests to distinct 3rd party domains in %')
    ax2.set_ylabel('')
    
    # Set y-axis to show percentages
    ax1.set_ylim(0, 100)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x)}'))
    
    # Add horizontal grid lines
    ax1.grid(axis='y', linestyle='-', alpha=0.2)
    ax2.grid(axis='y', linestyle='-', alpha=0.2)
    
    # Remove top and right spines
    for ax in [ax1, ax2]:
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    
    # Add legend to figure (not to the individual axes)
    # Create a legend at the top center of the figure
    handles, labels = ax1.get_legend_handles_labels()
    legend = fig.legend(handles, labels, loc='upper center', 
                        bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=True)
    
    # Add a box around the legend
    frame = legend.get_frame()
    frame.set_linewidth(0.8)
    frame.set_edgecolor('black')
    
    # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    
    # Save figure
    output_file = os.path.join(output_dir, 'protocol_analysis.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Generated protocol analysis visualization: {output_file}")
    
    # Show figure
    plt.close()

if __name__ == "__main__":
    # Define parameters
    json_dir = "data/Varies runs/crawler_data_trial"
    output_dir = "data/analysis"
    
    # Analyze protocols by extension
    analyze_protocols_by_extension(json_dir, output_dir) 