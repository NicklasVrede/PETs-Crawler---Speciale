import os
import json
import csv
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
from urllib.parse import urlparse
from tqdm import tqdm
import numpy as np
import sys


# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)


from analysis.third_party.third_party_domain_prevalence import get_successful_domains

# Use sampling buckets to ensure consistent data representation
RANK_BUCKETS = [
    (1, 5000),           # [1-5k]
    (5001, 10000),       # [5k-10k]
    (10001, 50000),      # [10k-50k]
    (50001, 250000),     # [50k-250k]
    (250001, 500000),    # [250k-500k]
    (500001, 1000000),   # [500k-1M]
]

def get_rank_bucket_label(rank):
    """Convert a rank to a bucket label"""
    for start, end in RANK_BUCKETS:
        if start <= rank <= end:
            if start < 1000:
                start_label = str(start)
            else:
                start_label = f"{start//1000}k"
            if end < 1000:
                end_label = str(end)
            else:
                end_label = f"{end//1000}k"
            return f"[{start_label}-{end_label}]"
    return "unknown"

def load_site_rankings(csv_path='data/db+ref/Tranco_final_sample.csv'):
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

def extract_domain_data(json_file, site_rankings):
    """Extract third-party domain data from a JSON file"""
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
        
        # Get site rank - first try direct lookup
        site_rank = site_rankings.get(site_domain_lower)
        
        # If rank not found, try alternative methods
        if site_rank is None:
            if site_domain_lower.startswith('www.'):
                site_rank = site_rankings.get(site_domain_lower[4:])
            else:
                site_rank = site_rankings.get(f"www.{site_domain_lower}")
                
            # If still not found, print some helpful debug info
            if site_rank is None:
                print(f"No rank found for site: {site_domain} (tried {site_domain_lower} and alternatives)")
                # As a fallback, use a rank based on filename pattern if possible
                # Some datasets name files like "1_google.com.json" where 1 is the rank
                filename = os.path.basename(json_file)
                parts = filename.split('_', 1)
                if len(parts) == 2 and parts[0].isdigit():
                    site_rank = int(parts[0])
                    print(f"Using rank {site_rank} from filename")
        
        # Skip if no rank found
        if site_rank is None:
            return None
            
        # Skip if rank is outside our buckets
        if site_rank < RANK_BUCKETS[0][0] or site_rank > RANK_BUCKETS[-1][1]:
            return None
            
        # Get rank bucket
        rank_bucket = get_rank_bucket_label(site_rank)
        
        # First-party domains (to exclude from third-party analysis)
        first_party_domains = {site_domain_lower}
        if site_domain_lower.startswith('www.'):
            first_party_domains.add(site_domain_lower[4:])
        else:
            first_party_domains.add(f"www.{site_domain_lower}")
            
        # Extract all third-party domains
        third_party_domains = set()
        
        # Get network data - try different visit keys
        network_data = None
        for key in ['0', '1', 'visit0', 'visit1']:
            if key in data.get('network_data', {}):
                network_data = data['network_data'][key]
                break
        
        if not network_data:
            # Try looking for requests directly
            requests = data.get('requests', [])
            if not requests:
                return None
        else:
            # Get requests from network_data
            requests = network_data.get('requests', [])
            
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
                    # Special case for domains like .co.uk
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
            except Exception as e:
                print(f"Error parsing URL {url}: {e}")
                continue
                
        return {
            'site_domain': site_domain,
            'rank_bucket': rank_bucket,
            'site_rank': site_rank,
            'third_party_domains': list(third_party_domains)
        }
                
    except Exception as e:
        print(f"Error processing {json_file}: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_data(json_dir, output_dir, profile="no_extensions"):
    """Analyze data from specified profile and generate domain prevalence graph"""
    # Load site rankings and successful domains
    site_rankings = load_site_rankings()
    successful_domains = get_successful_domains()
    
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
                # Extract domain from filename
                domain = file[:-5]  # Remove '.json'
                if domain.startswith('www.'):
                    domain = domain[4:]
                # Only include files for domains that loaded successfully across all profiles
                if domain.lower() in successful_domains:
                    json_files.append(os.path.join(root, file))
                
    print(f"Found {len(json_files)} JSON files for successfully loaded domains in {target_dir}")
    
    # Process JSON files
    sites_data = []
    for json_file in tqdm(json_files, desc="Processing JSON files"):
        result = extract_domain_data(json_file, site_rankings)
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
    for domain, buckets in domain_presence.items():
        for bucket, count in buckets.items():
            if bucket_counts[bucket] > 0:
                percentage = (count / bucket_counts[bucket]) * 100
                domain_percentages[domain][bucket] = percentage
                
    # Find top domains by overall prevalence
    domain_avg_presence = {}
    for domain, buckets in domain_percentages.items():
        values = list(buckets.values())
        if values:
            domain_avg_presence[domain] = sum(values) / len(values)
            
    # Sort domains by prevalence
    top_domains = sorted(domain_avg_presence.items(), key=lambda x: x[1], reverse=True)[:12]
    print(f"Top third-party domains: {top_domains}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create DataFrame for visualization
    df_data = []
    bucket_labels = [get_rank_bucket_label(bucket[0]) for bucket in RANK_BUCKETS]
    
    for domain, _ in top_domains:
        for bucket in bucket_labels:
            percentage = domain_percentages[domain].get(bucket, 0)
            df_data.append({
                'domain': domain,
                'rank_bucket': bucket,
                'percentage': percentage
            })
            
    df = pd.DataFrame(df_data)
    
    # Generate visualization
    generate_domain_prevalence_visualization(df, top_domains, output_dir, profile)

def generate_domain_prevalence_visualization(df, top_domains, output_dir, profile="no_extensions"):
    """Generate domain prevalence visualization with styling that closely matches the reference"""
    plt.figure(figsize=(12, 8))
    
    # Get ordered bucket labels
    bucket_labels = [get_rank_bucket_label(bucket[0]) for bucket in RANK_BUCKETS]
    
    # Create custom x-axis positions - slightly wider spacing for larger buckets
    x_positions = [0, 0.4, 0.8, 1.5, 2.3, 3.0]  # Manually adjusted positions
    
    # Rest of the color and marker definitions remain the same
    colors = [
        '#20B2AA', '#FFD700', '#FF6347', '#4169E1', '#9370DB',
        '#FF7F50', '#A9A9A9', '#00CED1', '#32CD32', '#FF69B4',
        '#FFFF00', '#98FB98', '#DDA0DD', '#FFDEAD',
    ]
    markers = ['o', 'v', 'D', 'x', 's', '^', 'o', 'v', 'D', 'o', 'v', 'D', 'x', 's']
    
    # Plot each domain with the new x_positions
    lines = []
    legend_labels = []
    
    for i, (domain, avg_pct) in enumerate(top_domains):
        domain_data = df[df['domain'] == domain]
        
        # Create a complete dataset with all buckets
        complete_data = []
        for bucket, x_pos in zip(bucket_labels, x_positions):
            bucket_data = domain_data[domain_data['rank_bucket'] == bucket]
            percentage = bucket_data['percentage'].values[0] if len(bucket_data) > 0 else 0
            complete_data.append({'x_position': x_pos, 'percentage': percentage})
            
        complete_df = pd.DataFrame(complete_data)
        
        line, = plt.plot(
            complete_df['x_position'],
            complete_df['percentage'],
            color=colors[i % len(colors)],
            marker=markers[i % len(markers)],
            markersize=8,
            markeredgecolor='black',
            markeredgewidth=1.5,
            linestyle='-',
            linewidth=5.0,
            label=f"{domain} ({avg_pct:.1f}%)"
        )
        
        lines.append(line)
        legend_labels.append(f"{domain}")
    
    # Set custom x-tick positions and labels
    plt.xticks(x_positions, bucket_labels, rotation=45)
    
    # Rest of the formatting remains the same
    plt.box(True)
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x)}%'))
    plt.ylim(10, 100)
    plt.grid(axis='y', color='lightgray', linestyle='-', linewidth=0.5, alpha=0.7)
    
    plt.xlabel("", fontsize=14)
    plt.ylabel("% of pages including 3rd party domain", fontsize=12)
    
    legend = plt.legend(
        lines, 
        legend_labels,
        loc='upper center',
        bbox_to_anchor=(0.5, 1.15),
        ncol=3,
        frameon=True,
        fontsize=10,
        handlelength=3,
        borderpad=1.0,
        labelspacing=0.5,
        columnspacing=1.0
    )
    
    # Remove suptitle
    plt.suptitle("")
    
    # Keep other formatting elements
    frame = legend.get_frame()
    frame.set_edgecolor('black')
    frame.set_linewidth(1.0)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.75)
    
    output_file = os.path.join(output_dir, f'domain_prevalence_{profile}.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Generated domain prevalence visualization: {output_file}")

if __name__ == "__main__":
    # Base directory for crawler data
    json_dir = "data/crawler_data"
    output_dir = "analysis/graphs"
    
    # Analyze data - try different profiles
    analyze_data(json_dir, output_dir, profile="no_extensions") 