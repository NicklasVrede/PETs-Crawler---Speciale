import os
import sys
import json
from collections import defaultdict
from tqdm import tqdm
import matplotlib.pyplot as plt

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

def analyze_inclusions_per_bucket(successful_domains, bucket_start, bucket_end):
    """
    Analyze third-party domain inclusions for a specific rank bucket.
    Returns domains grouped by their inclusion count (2-20, 20-200, 200-10000).
    """
    baseline_profile = "no_extensions"
    tranco_ranks = load_tranco_ranks()
    
    # Get domains in this rank bucket
    bucket_domains = [d for d in successful_domains 
                     if bucket_start <= tranco_ranks.get(d, float('inf')) <= bucket_end]
    
    # Count on how many sites each third-party domain appears
    domain_inclusions = defaultdict(set)  # third_party -> set of websites that include it
    
    for domain in tqdm(bucket_domains, desc=f"Analyzing rank bucket {bucket_start}-{bucket_end}"):
        json_path = os.path.join("data/crawler_data", baseline_profile, f"{domain}.json")
        if os.path.exists(json_path):
            third_party_domains = get_third_party_domains(json_path)
            for tp_domain in third_party_domains:
                domain_inclusions[tp_domain].add(domain)
    
    # Group domains by inclusion count
    inclusion_groups = {
        "2-20": set(d for d, sites in domain_inclusions.items() 
                   if 2 <= len(sites) <= 20),
        "20-200": set(d for d, sites in domain_inclusions.items() 
                     if 20 < len(sites) <= 200),
        "200-10000": set(d for d, sites in domain_inclusions.items() 
                        if 200 < len(sites) <= 10000)
    }
    
    # Print statistics
    print(f"\nThird-party domains in bucket {bucket_start}-{bucket_end}:")
    for group, domains in inclusion_groups.items():
        print(f"{group} inclusions: {len(domains)} domains")
        if domains:
            sample = list(domains)[:3]
            counts = [len(domain_inclusions[d]) for d in sample]
            print(f"Sample domains and their inclusion counts: {list(zip(sample, counts))}")
    
    return inclusion_groups, bucket_domains

def analyze_blocking_effectiveness(inclusion_groups, bucket_domains, profiles):
    """Analyze how effectively each profile blocks the domains in each inclusion group."""
    baseline_profile = "no_extensions"
    results = defaultdict(lambda: defaultdict(float))
    
    for profile in tqdm(profiles, desc="Analyzing profiles"):
        if profile == baseline_profile:
            continue
            
        for group_name, group_domains in inclusion_groups.items():
            if not group_domains:
                continue
                
            domains_seen = 0
            domains_blocked = 0
            
            for website in bucket_domains:
                # Get baseline third-party domains
                baseline_path = os.path.join("data/crawler_data", baseline_profile, f"{website}.json")
                if not os.path.exists(baseline_path):
                    continue
                    
                baseline_domains = set(get_third_party_domains(baseline_path)) & group_domains
                if not baseline_domains:
                    continue
                
                # Get current profile's third-party domains
                profile_path = os.path.join("data/crawler_data", profile, f"{website}.json")
                if not os.path.exists(profile_path):
                    continue
                    
                current_domains = set(get_third_party_domains(profile_path))
                
                # Count blocked domains
                domains_seen += len(baseline_domains)
                domains_blocked += len(baseline_domains - current_domains)
            
            if domains_seen > 0:
                blocking_percentage = (domains_blocked / domains_seen) * 100
                results[group_name][profile] = blocking_percentage
    
    return results

def main():
    # Get domains that loaded successfully
    successful_domains = get_successful_domains()
    
    # Get all profiles
    profiles = []
    for group_profiles in PROFILE_GROUPS.values():
        profiles.extend(group_profiles)
    
    # Analyze each rank bucket
    all_results = {}
    for bucket_start, bucket_end in RANK_BUCKETS:
        print(f"\nAnalyzing rank bucket {bucket_start}-{bucket_end}")
        inclusion_groups, bucket_domains = analyze_inclusions_per_bucket(successful_domains, bucket_start, bucket_end)
        results = analyze_blocking_effectiveness(inclusion_groups, bucket_domains, profiles)
        all_results[f"{bucket_start}-{bucket_end}"] = results
    
    # Print results
    print("\nBlocking effectiveness by rank bucket:")
    for bucket in all_results:
        print(f"\nRank bucket {bucket}:")
        for group in ["2-20", "20-200", "200-10000"]:
            print(f"\n  Domains with {group} inclusions:")
            for profile, percentage in all_results[bucket][group].items():
                print(f"    {DISPLAY_NAMES.get(profile, profile)}: {percentage:.1f}%")

if __name__ == "__main__":
    main() 