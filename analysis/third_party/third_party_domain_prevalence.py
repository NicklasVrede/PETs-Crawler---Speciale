import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from tqdm import tqdm
import sys
from matplotlib.colors import rgb2hex

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

# Get colors from the tab20 colormap
colors = [rgb2hex(plt.cm.tab20(i)) for i in range(20)]

# Define specific markers and colors for each profile using tab20 colors
profile_styles = {
    'accept_all_cookies': {'marker': 'o', 'color': colors[0]},      # tab20 blue
    'adblock': {'marker': '^', 'color': colors[2]},                # tab20 green
    'adblock_plus': {'marker': '^', 'color': colors[4]},          # tab20 red
    'adguard': {'marker': 'D', 'color': colors[6]},               # tab20 purple
    'consent_o_matic_opt_in': {'marker': 'v', 'color': colors[8]},  # tab20 brown
    'consent_o_matic_opt_out': {'marker': 'v', 'color': colors[10]}, # tab20 pink
    'decentraleyes': {'marker': '>', 'color': colors[12]},          # tab20 gray
    'disconnect': {'marker': 's', 'color': colors[13]},             # New style for Disconnect
    'ghostery_tracker_&_ad_blocker': {'marker': 'o', 'color': colors[14]},  # tab20 olive
    'ghostery_tracker_&_ad_blocker_only_never_consent': {'marker': 'o', 'color': colors[16]},  # tab20 cyan
    'i_dont_care_about_cookies': {'marker': 'o', 'color': colors[18]},  # tab20 lime
    'no_extensions': {'marker': 'o', 'color': 'black'},            # Black (Baseline)
    'privacy_badger': {'marker': '*', 'color': colors[1]},         # tab20 light blue
    'super_agent_opt_in': {'marker': 'o', 'color': colors[3]},     # tab20 light green
    'super_agent_opt_out': {'marker': 'o', 'color': colors[5]},    # tab20 light red
    'ublock': {'marker': '+', 'color': colors[7]},                # tab20 light purple
    'ublock_origin_lite': {'marker': 'x', 'color': colors[15]},    # New style for uBlock Origin Lite
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
    
    # Debug print
    print("\nTotal profiles to process:", len(profiles_to_process))
    print("Profiles:", sorted(profiles_to_process))
    
    print("\nAnalyzing baseline profile domains...")
    baseline_domain_freq = defaultdict(int)
    
    # Count appearances of each third-party domain in baseline
    for domain in tqdm(successful_domains, desc="Processing baseline profile"):
        json_path = os.path.join("data/crawler_data", baseline_profile, f"{domain}.json")
        if os.path.exists(json_path):
            third_party_domains = get_third_party_domains(json_path)
            for tp_domain in third_party_domains:
                baseline_domain_freq[tp_domain] += 1
    
    # Filter out domains that only appear once
    baseline_domain_freq = {domain: freq for domain, freq in baseline_domain_freq.items() if freq > 1}
    
    # Sort domains by frequency (most frequent first)
    sorted_domains = sorted(baseline_domain_freq.items(), key=lambda x: x[1], reverse=True)
    
    # Debug print for frequency information
    print("\nTop 10 most frequent domains and their appearances:")
    for domain, freq in sorted_domains[:10]:
        print(f"{domain}: {freq} appearances")
    
    print(f"\nTotal unique domains appearing more than once: {len(sorted_domains)}")
    
    # Group domains by their prevalence ranking (not frequency)
    freq_groups = {
        "2-6": set(domain for domain, _ in sorted_domains[1:6]),  # 2nd to 20th most prevalent
        "6-20": set(domain for domain, _ in sorted_domains[6:20]),  # 21st to 200th most prevalent
        "20-10000": set(domain for domain, _ in sorted_domains[20:10000])  # 201st to 10000th most prevalent
    }
    
    # Debug print
    print("\nDomain groups by prevalence ranking:")
    for group_name, domains in freq_groups.items():
        print(f"\n{group_name} most prevalent domains:")
        sample_domains = list(domains)[:5]
        for domain in sample_domains:
            print(f"  {domain}: {baseline_domain_freq[domain]} appearances")
    
    # Track missing domains specifically for decentraleyes
    print("\nAnalyzing domains missing in Decentraleyes...")
    decentraleyes_missing = defaultdict(set)
    target_profile = "decentraleyes"
    freq_group = "20-10000"
    
    # Use the already filtered baseline_domain_freq that only includes domains appearing more than once
    freq_domains = {domain for domain, freq in baseline_domain_freq.items() 
                   if domain in freq_groups[freq_group]}
    
    # Process all rank buckets with a progress bar
    for rank_start, rank_end in tqdm(RANK_BUCKETS, desc="Processing rank buckets"):
        bucket_label = get_rank_bucket_label(rank_start)
        bucket_websites = {d for d in successful_domains 
                         if rank_start <= tranco_ranks.get(d, float('inf')) <= rank_end}
        
        # Process all websites in this bucket at once
        baseline_domains = set()
        decentraleyes_domains = set()
        
        # Process baseline profile
        for website in bucket_websites:
            baseline_path = os.path.join("data/crawler_data", baseline_profile, f"{website}.json")
            decentraleyes_path = os.path.join("data/crawler_data", target_profile, f"{website}.json")
            
            if os.path.exists(baseline_path):
                third_party_domains = set(get_third_party_domains(baseline_path))
                # Only include domains that appear more than once
                baseline_domains.update(third_party_domains & freq_domains)
            
            if os.path.exists(decentraleyes_path):
                current_domains = set(get_third_party_domains(decentraleyes_path))
                decentraleyes_domains.update(current_domains & freq_domains)
        
        # Calculate missing domains for this bucket
        missing = baseline_domains - decentraleyes_domains
        if missing:
            decentraleyes_missing[bucket_label] = missing
    
    # Print summary report for Decentraleyes
    print("\nSummary of domains missing in Decentraleyes (200-10000 most prevalent domains, appearing more than once):")
    total_missing = 0
    for rank_bucket, domains in decentraleyes_missing.items():
        missing_count = len(domains)
        total_missing += missing_count
        print(f"\n{rank_bucket}: {missing_count} missing domains")
        if missing_count > 0:
            print("Sample missing domains and their frequencies:")
            for domain in sorted(list(domains))[:5]:  # Show only first 5 domains as sample
                print(f"  - {domain}: {baseline_domain_freq[domain]} appearances")
    
    print(f"\nTotal missing domains across all buckets: {total_missing}")
    
    # Process the results for other profiles
    print("\nProcessing other profiles...")
    results = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    
    for profile in tqdm(profiles_to_process, desc="Processing profiles"):
        for rank_start, rank_end in RANK_BUCKETS:
            bucket_websites = {d for d in successful_domains 
                             if rank_start <= tranco_ranks.get(d, float('inf')) <= rank_end}
            
            for freq_group, freq_domains in freq_groups.items():
                baseline_domains = set()
                for website in bucket_websites:
                    json_path = os.path.join("data/crawler_data", baseline_profile, f"{website}.json")
                    if os.path.exists(json_path):
                        third_party_domains = set(get_third_party_domains(json_path))
                        baseline_domains.update(third_party_domains & freq_domains)
                
                if not baseline_domains:
                    continue
                
                unblocked_domains = set()
                for website in bucket_websites:
                    json_path = os.path.join("data/crawler_data", profile, f"{website}.json")
                    if os.path.exists(json_path):
                        current_domains = set(get_third_party_domains(json_path))
                        unblocked_domains.update(current_domains & baseline_domains)
                
                if baseline_domains:
                    percentage = (len(unblocked_domains) / len(baseline_domains)) * 100
                    results[freq_group][profile][get_rank_bucket_label(rank_start)] = percentage
    
    return results

def plot_domain_prevalence_by_rank(results):
    """Create line plots showing percentage of domains still present across rank buckets."""
    print("Creating visualization...")
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    freq_groups = ["2-6", "6-20", "20-10000"]  # Updated to match the defined groups
    
    # Define custom x-axis positions
    x_positions = [0, 0.4, 0.8, 1.5, 2.3, 3.0]
    
    for idx, freq_group in enumerate(freq_groups):
        ax = axes[idx]
        print(f"Processing frequency group: {freq_group}")
        
        # Check if freq_group exists in results
        if freq_group not in results:
            print(f"Warning: No data for frequency group {freq_group}")
            continue
            
        for profile in results[freq_group]:
            style = profile_styles.get(profile, {'marker': 'o', 'color': 'black'})
            data = results[freq_group][profile]
            
            # Debug print the data
            print(f"Profile {profile} data: {data}")
            
            # Map rank buckets to custom x positions
            profile_x_positions = []
            profile_y_values = []
            
            for bucket in [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS]:
                if bucket in data:
                    pos_idx = [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS].index(bucket)
                    profile_x_positions.append(x_positions[pos_idx])
                    profile_y_values.append(data[bucket])
            
            if profile_x_positions and profile_y_values:  # Only plot if we have data
                ax.plot(profile_x_positions, profile_y_values,
                       marker=style['marker'],
                       color=style['color'],
                       label=DISPLAY_NAMES.get(profile, profile),
                       markersize=8,
                       alpha=0.5,
                       markerfacecolor=style['color'],
                       markeredgecolor='black',
                       markeredgewidth=1.0,
                       linewidth=1.5)
        
        ax.set_title(f'{freq_group} inclusions')
        ax.set_xlabel('')
        ax.set_ylabel('% of domains still present' if idx == 0 else '', fontsize=16)
        ax.set_yticks(fontsize=14)
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
        
        # Set custom x-ticks with adjusted positions
        ax.set_xticks(x_positions)
        x_labels = [rb.replace('Top ', '') for rb in [get_rank_bucket_label(b[0]) for b in RANK_BUCKETS]]
        ax.set_xticklabels(x_labels, rotation=45, fontsize=14)
        
        # Only show legend for the last subplot
        if idx == len(freq_groups) - 1:
            # Remove duplicate entries from legend
            handles, labels = ax.get_legend_handles_labels()
            unique_labels = []
            unique_handles = []
            for handle, label in zip(handles, labels):
                if label not in unique_labels:
                    unique_labels.append(label)
                    unique_handles.append(handle)
            ax.legend(unique_handles, unique_labels, bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout(
        rect=[0, 0, 0.92, 0.95],
        h_pad=0.2,
        w_pad=0.2
    )
    
    # Create output directory if it doesn't exist
    os.makedirs('analysis/graphs', exist_ok=True)
    
    print("Saving graph...")
    plt.savefig('analysis/graphs/third_party_blocking_effectiveness.png', 
                dpi=300, 
                bbox_inches='tight',
                pad_inches=0.1)
    plt.close()
    print("Graph saved successfully!")

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
    # Get domains that loaded successfully
    successful_domains = get_successful_domains()
    
    # Get all profile directories from crawler_data
    profile_dirs = [d for d in os.listdir("data/crawler_data") 
                   if os.path.isdir(os.path.join("data/crawler_data", d))
                   and d != "crawler_data_failed"]
    
    # Analyze prevalence
    results = analyze_third_party_prevalence(profile_dirs, successful_domains)
    
    # Create and save the plot
    plot_domain_prevalence_by_rank(results)

if __name__ == "__main__":
    main() 