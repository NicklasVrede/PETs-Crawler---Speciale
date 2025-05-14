import os
import json
import csv
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
from urllib.parse import urlparse
from tqdm import tqdm
import numpy as np
import argparse
from multiprocessing import Pool, cpu_count

# Define larger rank buckets for 1-100,000 range
# Following the format from your example image
DEFAULT_LARGE_BUCKETS = [
    (1, 10000),        # [1-10k]
    (10000, 30000),    # [10k-30k]
    (30000, 50000),    # [30k-50k]
    (50000, 70000),    # [50k-70k]
    (70000, 90000),    # [70k-90k]
    (90000, 110000),   # [90k-110k]
    (110000, 130000),  # [110k-130k]
    (130000, 150000),  # [130k-150k]
    (150000, 170000),  # [150k-170k]
    (170000, 190000),  # [170k-190k]
]

def get_rank_bucket_label(rank, buckets):
    """Convert a rank to a bucket label based on provided buckets"""
    for start, end in buckets:
        if start <= rank < end:
            if start >= 1000:
                return f"[{start//1000}k-{end//1000}k]"
            else:
                return f"[{start}-{end//1000}k]"
    return "unknown"

def load_site_rankings(csv_path='data/db+ref/study-sites.csv'):
    """Load site rankings from CSV file"""
    rankings = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Store domain as key
                rankings[row['domain'].lower()] = int(row['rank'])
        return rankings
    except Exception as e:
        print(f"Warning: Could not load site rankings from {csv_path}: {e}")
        return {}

def extract_domain_data(args):
    """Extract third-party domain data from a JSON file (for parallel processing)"""
    json_file, site_rankings, buckets = args
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get site domain and rank
        site_domain = data.get('domain', '')
        
        # If domain is empty, extract from filename
        if not site_domain:
            filename = os.path.basename(json_file)
            site_domain = filename[:-5]  # Remove '.json'
        
        # Convert to lowercase for case-insensitive matching
        site_domain_lower = site_domain.lower()
        
        # Get site rank
        site_rank = site_rankings.get(site_domain_lower)
        
        # Try alternative domain formats if rank not found
        if site_rank is None:
            if site_domain_lower.startswith('www.'):
                site_rank = site_rankings.get(site_domain_lower[4:])
            else:
                site_rank = site_rankings.get(f"www.{site_domain_lower}")
            
            # As a fallback, try to get rank from filename
            if site_rank is None:
                filename = os.path.basename(json_file)
                parts = filename.split('_', 1)
                if len(parts) == 2 and parts[0].isdigit():
                    site_rank = int(parts[0])
        
        # Skip if no rank found
        if site_rank is None:
            return None
            
        # Skip if rank is outside our buckets
        if site_rank < buckets[0][0] or site_rank >= buckets[-1][1]:
            return None
            
        # Get rank bucket
        rank_bucket = get_rank_bucket_label(site_rank, buckets)
        
        # First-party domains (to exclude from third-party analysis)
        first_party_domains = {site_domain_lower}
        if site_domain_lower.startswith('www.'):
            first_party_domains.add(site_domain_lower[4:])
        else:
            first_party_domains.add(f"www.{site_domain_lower}")
            
        # Extract all third-party domains
        third_party_domains = set()
        
        # Try to get network requests from different formats
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
            
        # Skip if no requests found
        if not requests:
            return None
            
        # Process requests
        for req in requests:
            url = req.get('url', '')
            if not url:
                continue
                
            # Parse URL to get domain
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()
                
                # Skip empty domains
                if not domain:
                    continue
                    
                # Extract base domain (TLD+1)
                # Handle special cases like co.uk
                parts = domain.split('.')
                if len(parts) > 2:
                    # Special case for domains like .co.uk, .com.au
                    if len(parts[-2]) <= 3 and len(parts[-1]) <= 3:
                        if len(parts) > 3:
                            base_domain = '.'.join(parts[-3:])
                        else:
                            base_domain = domain
                    else:
                        base_domain = '.'.join(parts[-2:])
                else:
                    base_domain = domain
                    
                # Skip first-party domains
                is_third_party = True
                for fp_domain in first_party_domains:
                    if domain == fp_domain or domain.endswith(f".{fp_domain}"):
                        is_third_party = False
                        break
                        
                if is_third_party:
                    third_party_domains.add(base_domain)
            except Exception:
                continue
                
        return {
            'site_domain': site_domain,
            'rank_bucket': rank_bucket,
            'site_rank': site_rank,
            'third_party_domains': list(third_party_domains)
        }
                
    except Exception:
        return None

def analyze_large_dataset(json_dir, output_dir, buckets=None, profile="no_extensions", 
                          num_processes=None, min_domain_occurence=0.05):
    """
    Analyze a large dataset of web crawl data for third-party domain prevalence
    
    Args:
        json_dir: Directory containing JSON files
        output_dir: Directory to save output files
        buckets: List of tuples defining rank buckets, or None for default
        profile: Subfolder name if JSON files are in a profile-specific directory
        num_processes: Number of processes for parallel processing, or None for auto
        min_domain_occurence: Minimum prevalence (0-1) for a domain to be included in the visualization
    """
    # Use default buckets if none provided
    if buckets is None:
        buckets = DEFAULT_LARGE_BUCKETS
    
    # Determine number of processes
    if num_processes is None:
        num_processes = max(1, cpu_count() - 1)  # Leave one CPU free
    
    # Load site rankings
    site_rankings = load_site_rankings()
    
    # Get path to the directory
    target_dir = os.path.join(json_dir, profile)
    if not os.path.exists(target_dir):
        print(f"Warning: {profile} directory not found at {target_dir}")
        print("Trying direct path...")
        target_dir = json_dir
        if not os.path.exists(target_dir):
            print(f"Error: Directory not found: {target_dir}")
            return
        
    # Find all JSON files
    json_files = []
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.json'):
                json_files.append(os.path.join(root, file))
                
    print(f"Found {len(json_files)} JSON files in {target_dir}")
    
    # Prepare arguments for parallel processing
    process_args = [(json_file, site_rankings, buckets) for json_file in json_files]
    
    # Process JSON files in parallel
    sites_data = []
    with Pool(processes=num_processes) as pool:
        for result in tqdm(pool.imap_unordered(extract_domain_data, process_args), 
                          total=len(json_files), 
                          desc="Processing files"):
            if result:
                sites_data.append(result)
            
    print(f"Processed {len(sites_data)} sites with valid ranking data")
    
    # Count domains per rank bucket
    bucket_counts = defaultdict(int)
    domain_presence = defaultdict(lambda: defaultdict(int))
    
    for site in sites_data:
        bucket = site['rank_bucket']
        bucket_counts[bucket] += 1
        
        # Count domain occurrences
        for domain in site['third_party_domains']:
            domain_presence[domain][bucket] += 1
    
    # Show how many sites are in each bucket
    print("Sites per bucket:")
    for bucket, count in sorted(bucket_counts.items()):
        print(f"  {bucket}: {count} sites")
    
    # Calculate percentage presence for each domain across buckets
    domain_percentages = defaultdict(dict)
    for domain, buckets_dict in domain_presence.items():
        for bucket, count in buckets_dict.items():
            if bucket_counts[bucket] > 0:
                percentage = (count / bucket_counts[bucket]) * 100
                domain_percentages[domain][bucket] = percentage
                
    # Find top domains by overall prevalence
    domain_avg_presence = {}
    for domain, buckets_dict in domain_percentages.items():
        values = list(buckets_dict.values())
        if values:
            avg_presence = sum(values) / len(values)
            # Only include domains that appear in a minimum percentage of sites
            if avg_presence >= (min_domain_occurence * 100):
                domain_avg_presence[domain] = avg_presence
            
    # Sort domains by prevalence and take top 12
    top_domains = sorted(domain_avg_presence.items(), key=lambda x: x[1], reverse=True)[:12]
    print(f"Top third-party domains: {top_domains}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create DataFrame for visualization
    df_data = []
    bucket_labels = sorted(set(site['rank_bucket'] for site in sites_data))
    
    for domain, avg_pct in top_domains:
        for bucket in bucket_labels:
            percentage = domain_percentages[domain].get(bucket, 0)
            df_data.append({
                'domain': domain,
                'rank_bucket': bucket,
                'percentage': percentage
            })
            
    df = pd.DataFrame(df_data)
    
    # Save data to CSV
    csv_file = os.path.join(output_dir, 'domain_prevalence_large.csv')
    df.to_csv(csv_file, index=False)
    print(f"Saved domain prevalence data to {csv_file}")
    
    # Generate visualization
    generate_domain_prevalence_visualization(df, top_domains, output_dir, 'large')

def smooth_data(df, window=3):
    """Apply moving average smoothing to make trends more visible"""
    smoothed_df = df.copy()
    
    # Get unique domains and buckets
    domains = df['domain'].unique()
    buckets = sorted(df['rank_bucket'].unique())
    
    # Smooth each domain's data
    for domain in domains:
        domain_data = df[df['domain'] == domain].sort_values('rank_bucket')
        values = domain_data['percentage'].values
        
        # Apply moving average if enough data points
        if len(values) >= window:
            padded = np.pad(values, (window//2, window//2), mode='edge')
            smoothed = np.convolve(padded, np.ones(window)/window, mode='valid')
            
            # Update smoothed dataframe
            for i, bucket in enumerate(buckets):
                if i < len(smoothed):
                    idx = smoothed_df[(smoothed_df['domain'] == domain) & 
                                    (smoothed_df['rank_bucket'] == bucket)].index
                    if len(idx) > 0:
                        smoothed_df.loc[idx, 'percentage'] = smoothed[i]
    
    return smoothed_df

def generate_domain_prevalence_visualization(df, top_domains, output_dir, suffix='', smooth=True):
    """Generate domain prevalence visualization with styling to match the reference image"""
    # Setup the figure with the right size and DPI
    plt.figure(figsize=(10, 6), dpi=100)
    
    # Create a custom color palette and marker styles
    styles = [
        {'color': '#20B2AA', 'marker': 'o'},
        {'color': '#FF6347', 'marker': 'v'},
        {'color': '#6495ED', 'marker': '^'},
        {'color': '#DB7093', 'marker': 'd'},
        {'color': '#32CD32', 'marker': 's'},
        {'color': '#FFFF00', 'marker': 'o'},
        {'color': '#FFD700', 'marker': 's'},
        {'color': '#20B2AA', 'marker': 'o'},
        {'color': '#FF7F50', 'marker': 's'},
        {'color': '#87CEFA', 'marker': 'o'},
        {'color': '#FF1493', 'marker': 'd'},
        {'color': '#98FB98', 'marker': 'd'},
    ]
    
    # Get sorted bucket labels - ensure they're in the correct order
    all_buckets = set(df['rank_bucket'].unique())
    # Sort buckets like [1-10k], [10k-30k], etc.
    bucket_labels = sorted(all_buckets, key=lambda x: int(x.split('-')[0].replace('[', '').replace('k', '000')))
    
    # Smooth data if requested (makes lines less jagged)
    plot_df = smooth_data(df, window=3) if smooth else df
    
    # Plot each domain as a separate line
    for i, (domain, avg_pct) in enumerate(top_domains):
        domain_data = plot_df[plot_df['domain'] == domain]
        style = styles[i % len(styles)]
        
        # Create sorted dataset with all buckets
        complete_data = []
        for bucket in bucket_labels:
            bucket_data = domain_data[domain_data['rank_bucket'] == bucket]
            if len(bucket_data) > 0:
                percentage = bucket_data['percentage'].values[0]
            else:
                percentage = 0
            complete_data.append({'rank_bucket': bucket, 'percentage': percentage})
            
        complete_df = pd.DataFrame(complete_data)
        
        # Convert percentage values to actual percentages (0-100 range)
        if complete_df['percentage'].max() <= 1.0:
            complete_df['percentage'] = complete_df['percentage'] * 100
            
        # Plot the line with appropriate marker and color
        plt.plot(complete_df['rank_bucket'], complete_df['percentage'], 
                 marker=style['marker'], 
                 color=style['color'],
                 label=domain,
                 linewidth=1.5,
                 markersize=5,
                 markeredgecolor='black',     # Black border around markers
                 markeredgewidth=0.8,         # Width of marker border
                 markerfacecolor=style['color']) # Fill marker with line color
    
    # Set chart properties to match the reference image
    plt.xlabel('Alexa Rank', fontsize=10)
    plt.ylabel('% of pages including 3rd party domain', fontsize=10)
    
    # Set y-axis to show percentages with % symbol
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x)}%'))
    
    # Only show horizontal grid lines, make them light gray and dashed
    plt.grid(axis='y', linestyle='--', alpha=0.3, color='gray')
    plt.grid(axis='x', visible=False)
    
    # Set y-axis limits to match reference (10%-80% with a bit of padding)
    plt.ylim(10, 80)
    
    # Rotate x-axis labels and make them smaller
    plt.xticks(rotation=45, fontsize=9)
    plt.yticks(fontsize=9)
    
    # Create a box around the legend and place it at the top of the figure
    # Not inside the plot area but above it
    legend = plt.legend(
        ncol=2,                   # Two columns of items
        loc='upper center',       # Position at the upper center
        bbox_to_anchor=(0.5, 1.18), # Above the plot
        fontsize=9,               # Smaller font
        frameon=True,             # Show a frame
        borderaxespad=0.          # No padding
    )
    
    # Add a box (rectangle) around the legend
    frame = legend.get_frame()
    frame.set_linewidth(0.8)      # Thin border
    frame.set_edgecolor('black')  # Black border
    
    # Add title inside the plotting area
    plt.title('Distribution of most popular third-party domains (TLD+1)\nin Alexa Top 200,000 websites', fontsize=11, pad=40)
    
    # Tight layout but with more top space for the legend
    plt.tight_layout(rect=[0, 0, 1, 0.85])
    
    # Save figure
    output_file = os.path.join(output_dir, f'domain_prevalence_{suffix}.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Generated domain prevalence visualization: {output_file}")
    
    # Also save a version without the extra padding for normal use
    plt.tight_layout()
    simple_output = os.path.join(output_dir, f'domain_prevalence_{suffix}_simple.png')
    plt.savefig(simple_output, dpi=300)

if __name__ == "__main__":
    # Define parameters directly
    json_dir = "data/Varies runs/crawler_data_trial02"
    output_dir = "data/analysis"
    profile = "no_extensions"
    num_processes = None  # Will use default (number of CPU cores)
    min_prevalence = 0.05
    use_small_buckets = False
    
    # Define buckets based on parameter
    if use_small_buckets:
        buckets = [
            (1, 10), (11, 20), (21, 30), (31, 40), (41, 50),
            (51, 60), (61, 70), (71, 80), (81, 90), (91, 100)
        ]
    else:
        buckets = DEFAULT_LARGE_BUCKETS
    
    # Analyze the dataset
    analyze_large_dataset(
        json_dir=json_dir,
        output_dir=output_dir,
        buckets=buckets,
        profile=profile,
        num_processes=num_processes,
        min_domain_occurence=min_prevalence
    ) 