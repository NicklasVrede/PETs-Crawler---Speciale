import os
import sys
import json
from collections import defaultdict
from tqdm import tqdm
import matplotlib.pyplot as plt
from matplotlib.colors import rgb2hex

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS
from analysis.third_party.third_party_domain_prevalence import get_third_party_domains, load_tranco_ranks, get_successful_domains

# Define rank buckets (same as in other analysis)
RANK_BUCKETS = [
    (1, 5000),           # [1-5k]
    (5001, 10000),       # [5k-10k]
    (10001, 50000),      # [10k-50k]
    (50001, 250000),     # [50k-250k]
    (250001, 500000),    # [250k-500k]
    (500001, 1000000),   # [500k-1M]
]

# Get colors from the tab20 colormap
colors = [rgb2hex(plt.cm.tab20(i)) for i in range(20)]

# Define specific markers and colors for each profile using tab20 colors, sorted by category
profile_styles = {
    # Base profile
    'no_extensions': {'marker': 'o', 'color': 'black'},            # Black (Baseline)
    
    # Ad blockers
    'adblock': {'marker': '^', 'color': colors[2]},                # tab20 green
    'adblock_plus': {'marker': '^', 'color': colors[4]},          # tab20 red
    'disconnect': {'marker': 's', 'color': colors[13]},             # New style for Disconnect
    'privacy_badger': {'marker': '*', 'color': colors[1]},         # tab20 light blue
    'ublock': {'marker': '+', 'color': colors[7]},                # tab20 light purple
    'ublock_origin_lite': {'marker': 'x', 'color': colors[15]},    # New style for uBlock Origin Lite
    'adguard': {'marker': 'D', 'color': colors[6]},               # tab20 purple
    'ghostery_tracker_&_ad_blocker': {'marker': 'o', 'color': colors[14]},  # tab20 olive
    
    # Cookie/consent managers
    'accept_all_cookies': {'marker': 'o', 'color': colors[0]},      # tab20 blue
    'consent_o_matic_opt_in': {'marker': 'v', 'color': colors[8]},  # tab20 brown
    'consent_o_matic_opt_out': {'marker': 'v', 'color': colors[10]}, # tab20 pink
    'ghostery_tracker_&_ad_blocker_only_never_consent': {'marker': 'o', 'color': colors[16]},  # tab20 cyan
    'i_dont_care_about_cookies': {'marker': 'o', 'color': colors[18]},  # tab20 lime
    'super_agent_opt_in': {'marker': 'o', 'color': colors[3]},     # tab20 light green
    'super_agent_opt_out': {'marker': 'o', 'color': colors[5]},    # tab20 light red
    
    # Other
    'decentraleyes': {'marker': '>', 'color': colors[12]},          # tab20 gray
}

def get_domain_prevalence(successful_domains):
    """
    Calculate the total prevalence of each third-party domain across all sites in the baseline profile.
    Returns a dictionary of domain -> number of sites it appears on.
    """
    baseline_profile = "no_extensions"
    domain_inclusions = defaultdict(set)  # third_party -> set of websites that include it
    
    for domain in tqdm(successful_domains, desc="Calculating domain prevalence"):
        json_path = os.path.join("data/crawler_data", baseline_profile, f"{domain}.json")
        if os.path.exists(json_path):
            third_party_domains = get_third_party_domains(json_path)
            for tp_domain in third_party_domains:
                domain_inclusions[tp_domain].add(domain)
    
    # Convert sets to counts
    return {domain: len(sites) for domain, sites in domain_inclusions.items()}

def group_domains_by_prevalence(domain_prevalence):
    """Group domains based on their prevalence ranking."""
    # Sort domains by prevalence (highest to lowest)
    sorted_domains = sorted(domain_prevalence.items(), key=lambda x: x[1], reverse=True)
    
    # Group by rank (skip the first most prevalent domain)
    groups = {
        "2-20": set(domain for domain, _ in sorted_domains[1:20]),  # 2nd to 20th most prevalent
        "20-200": set(domain for domain, _ in sorted_domains[20:200]),  # 21st to 200th
        "200-10000": set(domain for domain, _ in sorted_domains[200:10000])  # 201st to 10000th
    }
    
    # Print statistics about the groups
    print("\nOverall third-party domain groups:")
    for group_name, domains in groups.items():
        print(f"{group_name} prevalence rank: {len(domains)} domains")
        if domains:
            sample = list(domains)[:3]
            counts = [domain_prevalence[d] for d in sample]
            print(f"Sample domains and their inclusion counts: {list(zip(sample, counts))}")
    
    return groups

def analyze_inclusions_per_bucket(successful_domains, bucket_start, bucket_end):
    """
    Analyze third-party domain inclusions for a specific rank bucket.
    Groups domains based on their prevalence within this bucket only.
    """
    baseline_profile = "no_extensions"
    tranco_ranks = load_tranco_ranks()
    
    # Get domains in this bucket
    bucket_domains = [d for d in successful_domains 
                     if bucket_start <= tranco_ranks.get(d, float('inf')) <= bucket_end]
    
    print(f"\nBucket {bucket_start}-{bucket_end}:")
    print(f"Number of first-party domains in bucket: {len(bucket_domains)}")
    
    # Calculate domain prevalence within this bucket
    domain_inclusions = defaultdict(set)
    for domain in bucket_domains:
        json_path = os.path.join("data/crawler_data", baseline_profile, f"{domain}.json")
        if os.path.exists(json_path):
            third_party_domains = get_third_party_domains(json_path)
            for tp_domain in third_party_domains:
                domain_inclusions[tp_domain].add(domain)
    
    print(f"Total unique third-party domains in bucket: {len(domain_inclusions)}")
    
    # Group domains based on scaled prevalence thresholds
    groups = {  
        "2-5": set(domain for domain, sites in domain_inclusions.items() 
                if 2 <= len(sites) <= 5),  # Low prevalence
        "6-20": set(domain for domain, sites in domain_inclusions.items() 
                  if 5 < len(sites) <= 20),  # Medium prevalence
        "20+": set(domain for domain, sites in domain_inclusions.items() 
                     if 20 < len(sites))  # High prevalence
    }
    
    for group_name, domains in groups.items():
        print(f"{group_name}: {len(domains)} domains")
        if domains:
            sample = list(domains)[:3]
            counts = [len(domain_inclusions[d]) for d in sample]
            print(f"Sample domains and their inclusion counts: {list(zip(sample, counts))}")
    
    return groups, bucket_domains

def analyze_blocking_effectiveness(inclusion_groups, bucket_domains, profiles):
    """Analyze how effectively each profile blocks the domains in each inclusion group."""
    baseline_profile = "no_extensions"
    results = defaultdict(lambda: defaultdict(float))
    
    print("Analyzing blocking effectiveness...")
    for profile in tqdm(profiles, desc="Analyzing profiles"):
        if profile == baseline_profile:
            continue
            
        # Count occurrences of each third-party domain for this profile
        domain_counts = defaultdict(int)
        for website in tqdm(bucket_domains, desc=f"Counting domains for {profile}", leave=False):
            profile_path = os.path.join("data/crawler_data", profile, f"{website}.json")
            if os.path.exists(profile_path):
                third_party_domains = get_third_party_domains(profile_path)
                for domain in third_party_domains:
                    domain_counts[domain] += 1
        
        # Now check each group against the counts
        for group_name, group_domains in inclusion_groups.items():
            if not group_domains:
                continue
            
            threshold = 1
            
            # Count domains that meet the threshold
            domains_still_present = sum(1 for domain in group_domains 
                                     if domain_counts[domain] >= threshold)
            
            if group_domains:
                percentage = (domains_still_present / len(group_domains)) * 100
                results[group_name][profile] = percentage
    
    return results

def plot_results(all_results):
    """Create and save visualization of the blocking effectiveness."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('')
    
    prevalence_groups = ["2-5", "6-20", "20+"]
    titles = ["Low Prevalence (2-5)", "Medium Prevalence (6-20)", "High Prevalence (20+)"]
    
    x_labels = ['1-5k', '5k-10k', '10k-50k', '50k-250k', '250k-500k', '500k-1M']
    x_positions = [0, 1, 2, 4, 6, 8]
    
    for ax, group, title in zip(axes, prevalence_groups, titles):
        profiles = set()
        for bucket in all_results:
            if group in all_results[bucket]:
                profiles.update(all_results[bucket][group].keys())
        
        for profile in profiles:
            if profile != "no_extensions":
                style = profile_styles.get(profile, {'marker': 'o', 'color': 'black'})
                y_values = [all_results[bucket][group][profile] 
                           for bucket in [f"{start}-{end}" for start, end in RANK_BUCKETS]]
                ax.plot(x_positions, y_values,
                       label=DISPLAY_NAMES.get(profile, profile),
                       marker=style['marker'],
                       color=style['color'],
                       markersize=8,
                       alpha=0.5,
                       markerfacecolor=style['color'],
                       markeredgecolor='black',
                       markeredgewidth=1.0,
                       linewidth=1.5)
        
        ax.set_title(title)
        ax.set_xlabel('')
        ax.set_ylabel('% Domains Still Present')
        ax.set_xticks(x_positions)
        ax.set_xticklabels(x_labels, rotation=45)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)

    # Add legend to the right of the subplots with sorted categories
    handles, labels = axes[-1].get_legend_handles_labels()
    
    # Create category groups
    categories = {
        "Base profile": ["Baseline Profile"],
        "Ad blockers": ["Adblock", "AdblockPlus", "Disconnect", "Privacy Badger", 
                       "uBlock", "uBlock Origin Lite", "AdGuard", "Ghostery"],
        "Cookie/consent managers": ["Accept All Cookies", "Cookie Cutter", 
                                  "Consent-O-Matic (Opt-in)", "Consent-O-Matic (Opt-out)",
                                  'Ghostery (Never Consent)', "I Don't Care About Cookies",
                                  'Super Agent ("Opt-in")', 'Super Agent ("Opt-out")'],
        "Other": ["Decentraleyes"]
    }
    
    # Sort handles and labels according to categories
    sorted_handles = []
    sorted_labels = []
    
    for category in categories.values():
        for cat_label in category:
            if cat_label in labels:
                idx = labels.index(cat_label)
                sorted_handles.append(handles[idx])
                sorted_labels.append(labels[idx])
    
    fig.legend(sorted_handles, sorted_labels, 
              loc='center right', 
              bbox_to_anchor=(1.15, 0.5))
    
    plt.tight_layout(rect=[0, 0, 0.92, 0.95])
    
    # Save the figure
    output_dir = "analysis/graphs"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'blocking_effectivenes2.png'), 
                bbox_inches='tight', dpi=300, pad_inches=0.1)
    plt.close()

def main():
    # Get domains that loaded successfully
    successful_domains = get_successful_domains()
    
    # Calculate overall domain prevalence and group domains
    domain_prevalence = get_domain_prevalence(successful_domains)
    prevalence_groups = group_domains_by_prevalence(domain_prevalence)
    
    # Get all profiles
    profiles = []
    for group_profiles in PROFILE_GROUPS.values():
        profiles.extend(group_profiles)
    
    # Analyze each rank bucket
    all_results = {}
    for bucket_start, bucket_end in RANK_BUCKETS:
        print(f"\nAnalyzing rank bucket {bucket_start}-{bucket_end}")
        inclusion_groups, bucket_domains = analyze_inclusions_per_bucket(
            successful_domains, bucket_start, bucket_end)
        results = analyze_blocking_effectiveness(
            inclusion_groups, bucket_domains, profiles)
        all_results[f"{bucket_start}-{bucket_end}"] = results
    
    # Print results
    print("\nBlocking effectiveness by rank bucket:")
    for bucket in all_results:
        print(f"\nRank bucket {bucket}:")
        for group in ["2-5", "6-20", "20+"]:
            print(f"\n  Domains with {group} inclusions:")
            for profile, percentage in all_results[bucket][group].items():
                print(f"    {DISPLAY_NAMES.get(profile, profile)}: {percentage:.1f}%")

    # After printing results, create and save the visualization
    plot_results(all_results)
    print("\nVisualization saved as 'blocking_effectiveness.png' in results/figures/")

if __name__ == "__main__":
    main() 