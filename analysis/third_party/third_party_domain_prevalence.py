import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from tqdm import tqdm
import sys

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Define profile styles for plotting
profile_styles = {
    'chrome': {'marker': 'o', 'color': 'blue'},
    'firefox': {'marker': 's', 'color': 'orange'},
    'safari': {'marker': '^', 'color': 'green'},
    'edge': {'marker': 'D', 'color': 'red'},
    'brave': {'marker': 'X', 'color': 'purple'},
    'duckduckgo': {'marker': 'P', 'color': 'brown'},
    'tor': {'marker': '*', 'color': 'black'}
    # Add more profiles as needed
}

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
            start_label = f"{start//1000}k" if start >= 1000 else str(start)
            end_label = f"{end//1000}k" if end >= 1000 else str(end)
            return f"[{start_label}-{end_label}]"
    return "unknown"

def load_tranco_ranks():
    """Load domain ranks from Tranco CSV."""
    df = pd.read_csv('data/db+ref/Tranco_final_sample.csv')
    return dict(zip(df['domain'], df['rank']))

def get_third_party_domains_count(json_file):
    """Get count of unique third-party domains from a JSON file."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            if 'domain_analysis' in data and 'domains' in data['domain_analysis']:
                # Count unique third-party domains
                return sum(1 for domain in data['domain_analysis']['domains'] 
                         if not domain.get('is_first_party_domain', True))
    except Exception as e:
        print(f"Error processing {json_file}: {e}")
    return 0

def get_successful_domains(csv_path="data/csv/final_data2.csv"):
    """Get domains that loaded successfully across all profiles."""
    df = pd.read_csv(csv_path)
    df_loaded = df[df['page_status'] == 'loaded']
    all_profiles = df_loaded['profile'].unique()
    successful_domains = set()
    
    for domain in tqdm(df_loaded['domain'].unique(), desc="Finding successful domains"):
        if all(domain in df_loaded[df_loaded['profile'] == profile]['domain'].values 
               for profile in all_profiles):
            successful_domains.add(domain)
    
    return successful_domains

def get_third_party_domains(json_file):
    """Get list of third-party domains from a JSON file."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            if 'domain_analysis' in data and 'domains' in data['domain_analysis']:
                return [domain['domain'] for domain in data['domain_analysis']['domains'] 
                       if not domain.get('is_first_party_domain', True)]
    except Exception as e:
        print(f"Error processing {json_file}: {e}")
    return []

def analyze_third_party_prevalence(profiles, successful_domains):
    """Analyze which third-party domains are most prevalent."""
    tranco_ranks = load_tranco_ranks()
    baseline_profile = "no_extensions"
    profiles_to_process = [p for p in profiles if p != baseline_profile]
    
    # First get baseline domain frequencies across ALL ranks
    print("\nCollecting third-party domains from baseline profile...")
    baseline_domain_freq = defaultdict(int)
    
    for domain in tqdm(successful_domains, desc="Processing baseline profile"):
        json_path = os.path.join("data/crawler_data", baseline_profile, f"{domain}.json")
        if os.path.exists(json_path):
            third_party_domains = get_third_party_domains(json_path)
            for tp_domain in third_party_domains:
                baseline_domain_freq[tp_domain] += 1
    
    # Group domains by their frequency
    freq_groups = {
        "2-20": set(domain for domain, freq in baseline_domain_freq.items() if 2 <= freq <= 20),
        "20-200": set(domain for domain, freq in baseline_domain_freq.items() if 20 < freq <= 200),
        "200-10000": set(domain for domain, freq in baseline_domain_freq.items() if 200 < freq <= 10000)
    }
    
    results = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    
    # For each profile and rank bucket, check what percentage of the frequent domains appear
    for profile in tqdm(profiles_to_process, desc="Processing profiles"):
        for rank_start, rank_end in RANK_BUCKETS:
            # Get websites in this rank bucket
            bucket_websites = {d for d in successful_domains 
                             if rank_start <= tranco_ranks.get(d, float('inf')) <= rank_end}
            
            # For each frequency group
            for freq_group, frequent_domains in freq_groups.items():
                # Get all third-party domains that appear in this rank bucket for baseline
                baseline_bucket_domains = set()
                for website in bucket_websites:
                    json_path = os.path.join("data/crawler_data", baseline_profile, f"{website}.json")
                    if os.path.exists(json_path):
                        domains = set(get_third_party_domains(json_path))
                        baseline_bucket_domains.update(domains & frequent_domains)
                
                if not baseline_bucket_domains:
                    continue
                
                # Count how many of these domains still appear in the current profile
                domains_still_present = set()
                for website in bucket_websites:
                    json_path = os.path.join("data/crawler_data", profile, f"{website}.json")
                    if os.path.exists(json_path):
                        domains = set(get_third_party_domains(json_path))
                        domains_still_present.update(domains & baseline_bucket_domains)
                
                # Calculate percentage
                percentage = (len(domains_still_present) / len(baseline_bucket_domains)) * 100
                results[freq_group][profile][get_rank_bucket_label(rank_start)] = percentage
    
    return results

def plot_domain_prevalence_by_rank(results):
    """Create line plots showing percentage of domains still present across rank buckets."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    freq_groups = ["2-20", "20-200", "200-10000"]
    
    for idx, freq_group in enumerate(freq_groups):
        ax = axes[idx]
        
        for profile in results[freq_group]:
            style = profile_styles.get(profile, {'marker': 'o', 'color': 'black'})
            data = results[freq_group][profile]
            x = list(range(len(data)))
            y = list(data.values())
            
            ax.plot(x, y, 
                   marker=style['marker'],
                   color=style['color'],
                   label=DISPLAY_NAMES.get(profile, profile),
                   linewidth=1.5)
        
        ax.set_title(f'Domains with {freq_group} inclusions')
        ax.set_xlabel('Rank Bucket')
        ax.set_ylabel('% of domains still present')
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
        
    plt.tight_layout()
    plt.savefig('analysis/graphs/third_party_blocking_effectiveness.png', 
                dpi=300, bbox_inches='tight')
    plt.show()

def analyze_and_print_domains(profiles, successful_domains):
    """Print domains and their third-party counts for each rank group."""
    tranco_ranks = load_tranco_ranks()
    rank_groups = [(2, 20), (20, 200), (200, 10000)]
    
    print("\nAnalyzing domains by rank group:")
    for start, end in rank_groups:
        print(f"\nRank {start}-{end}:")
        print("=" * 50)
        
        # Get domains in this rank group
        group_domains = {domain: rank for domain, rank in tranco_ranks.items() 
                        if start <= rank < end and domain in successful_domains}
        
        # Sort domains by rank
        sorted_domains = sorted(group_domains.items(), key=lambda x: x[1])
        
        for domain, rank in sorted_domains:
            print(f"\nDomain: {domain} (rank {rank})")
            print("-" * 30)
            
            # Get third-party counts for each profile
            for profile in profiles:
                json_path = os.path.join("data/crawler_data", profile, f"{domain}.json")
                if os.path.exists(json_path):
                    count = get_third_party_domains_count(json_path)
                    print(f"{DISPLAY_NAMES.get(profile, profile)}: {count} third-party domains")

def main():
    # Load Tranco ranks
    print("Loading Tranco ranks...")
    tranco_ranks = pd.read_csv('data/db+ref/Tranco_final_sample.csv')
    tranco_ranks = dict(zip(tranco_ranks['domain'], tranco_ranks['rank']))
    
    # Get domains that loaded successfully
    successful_domains = get_successful_domains()
    
    # Get profiles from PROFILE_GROUPS
    profiles = []
    for group_profiles in PROFILE_GROUPS.values():
        profiles.extend(group_profiles)
    
    # Analyze prevalence
    results = analyze_third_party_prevalence(profiles, successful_domains)
    
    # Create and save the plot
    plot_domain_prevalence_by_rank(results)

if __name__ == "__main__":
    main() 