import os
import json
import csv
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict
from urllib.parse import urlparse
from tqdm import tqdm
import numpy as np

# Use evenly sized buckets (100k each) to ensure consistent data representation
RANK_BUCKETS = [
    (1, 100000),          # [1-100k]
    (100001, 200000),     # [100k-200k]
    (200001, 300000),     # [200k-300k]
    (300001, 400000),     # [300k-400k]
    (400001, 500000),     # [400k-500k]
    (500001, 600000),     # [500k-600k]
    (600001, 700000),     # [600k-700k]
    (700001, 800000),     # [700k-800k]
    (800001, 900000),     # [800k-900k]
    (900001, 1000000),    # [900k-1M]
]

def get_rank_bucket_label(rank):
    """Convert a rank to a bucket label"""
    for start, end in RANK_BUCKETS:
        if start <= rank <= end:
            if end == 1000000:
                return f"[{start//1000}k-1M]"
            else:
                return f"[{start//1000}k-{end//1000}k]"
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
    
    # Save data to CSV
    csv_file = os.path.join(output_dir, 'domain_prevalence.csv')
    df.to_csv(csv_file, index=False)
    print(f"Saved domain prevalence data to {csv_file}")
    
    # Generate visualization
    generate_domain_prevalence_visualization(df, top_domains, output_dir, profile)

def generate_domain_prevalence_visualization(df, top_domains, output_dir, profile="no_extensions"):
    """Generate domain prevalence visualization with styling that closely matches the reference"""
    plt.figure(figsize=(12, 8))
    
    # Get ordered bucket labels
    bucket_labels = [get_rank_bucket_label(bucket[0]) for bucket in RANK_BUCKETS]
    
    # Define colors similar to the reference image
    colors = [
        '#20B2AA',  # Light Sea Green (google-analytics.com)
        '#FFD700',  # Gold (googleapis.com)
        '#FF6347',  # Tomato (gstatic.com)
        '#4169E1',  # Royal Blue (google.com)
        '#9370DB',  # Medium Purple (google-analytics.com)
        '#FF7F50',  # Coral (doubleclick.net)
        '#A9A9A9',  # Dark Gray (facebook.net)
        '#00CED1',  # Dark Turquoise (facebook.com)
        '#32CD32',  # Lime Green (google.dk)
        '#FF69B4',  # Hot Pink (googlesyndication.com)
        '#FFFF00',  # Yellow (cloudflare.com)
        '#98FB98',  # Pale Green (jsdelivr.net)
        '#DDA0DD',  # Plum
        '#FFDEAD',  # Navajo White
    ]
    
    # Define distinct markers
    markers = ['o', 'v', 'D', 'x', 's', '^', 'o', 'v', 'D', 'o', 'v', 'D', 'x', 's']
    
    # Plot each domain
    lines = []
    legend_labels = []
    
    for i, (domain, avg_pct) in enumerate(top_domains):
        domain_data = df[df['domain'] == domain]
        
        # Create a complete dataset with all buckets
        complete_data = []
        for bucket in bucket_labels:
            bucket_data = domain_data[domain_data['rank_bucket'] == bucket]
            if len(bucket_data) > 0:
                percentage = bucket_data['percentage'].values[0]
            else:
                percentage = 0
            complete_data.append({'rank_bucket': bucket, 'percentage': percentage})
            
        complete_df = pd.DataFrame(complete_data)
        
        # Plot with black-bordered markers and ULTRA-THICK lines
        line, = plt.plot(
            complete_df['rank_bucket'], 
            complete_df['percentage'],
            color=colors[i % len(colors)],
            marker=markers[i % len(markers)],
            markersize=8,                # Larger markers
            markeredgecolor='black',     # Black border on markers
            markeredgewidth=1.5,         # Thicker marker border
            linestyle='-',               # All solid lines
            linewidth=5.0,               # ULTRA-THICK lines (was 3.5)
            label=f"{domain} ({avg_pct:.1f}%)"
        )
        
        lines.append(line)
        legend_labels.append(f"{domain}")
    
    # Create a box around the plot area
    plt.box(True)
    
    # Format y-axis as percentages
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x)}%'))
    
    # Set y-axis range from 10% to 100% as requested
    plt.ylim(10, 100)
    
    # Add horizontal grid lines
    plt.grid(axis='y', color='lightgray', linestyle='-', linewidth=0.5, alpha=0.7)
    
    # Set axis labels
    plt.xlabel("Alexa Rank", fontsize=14)
    plt.ylabel("% of pages including 3rd party domain", fontsize=12)
    
    # Create legend with more rows and less width
    legend = plt.legend(
        lines, 
        legend_labels,
        loc='upper center',
        bbox_to_anchor=(0.5, 1.15),  # Moved down slightly
        ncol=3,  # Reduced number of columns to create more rows
        frameon=True,  # Show frame
        fontsize=10,
        handlelength=3,  # Longer legend lines
        borderpad=1.0,   # More padding inside the legend
        labelspacing=0.5,
        columnspacing=1.0
    )
    
    # Add black border to legend
    frame = legend.get_frame()
    frame.set_edgecolor('black')
    frame.set_linewidth(1.0)
    
    plt.tight_layout()
    plt.subplots_adjust(top=0.75)  # Keep the increased top margin
    
    # Adjust title position - lowering the y value
    plt.suptitle(f"Third-Party Domain Prevalence ({profile})", 
                fontsize=16, 
                y=0.90)
    
    # Save figure
    output_file = os.path.join(output_dir, f'domain_prevalence_{profile}.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Generated domain prevalence visualization: {output_file}")

if __name__ == "__main__":
    # Base directory for crawler data
    json_dir = "data/crawler_data"
    output_dir = "data/analysis/domain_prevalence_analysis"
    
    # Analyze data - try different profiles
    analyze_data(json_dir, output_dir, profile="no_extensions") 