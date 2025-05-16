import os
import json
from collections import defaultdict
from tqdm import tqdm
import matplotlib.pyplot as plt
import pandas as pd
from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS
import csv

def load_site_rankings(csv_path='data/db+ref/study-sites.csv'):
    """Load site rankings from CSV file"""
    rankings = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rankings[row['domain'].lower()] = int(row['rank'])
        return rankings
    except Exception as e:
        print(f"Warning: Could not load site rankings from {csv_path}: {e}")
        return {}

def get_third_party_domains(json_file, site_rankings):
    """Extract third-party domains from a JSON file"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Get site domain and rank
        site_domain = data.get('domain', '')
        if not site_domain:
            filename = os.path.basename(json_file)
            site_domain = filename[:-5]  # Remove '.json'
        
        site_domain_lower = site_domain.lower()
        site_rank = site_rankings.get(site_domain_lower)
        
        # Skip if no rank or page didn't load
        if not site_rank:
            return None, None

        # Check if page loaded successfully
        page_loaded = False
        banner_analysis = data.get('banner_analysis', {})
        for visit_key in ['visit0', 'visit1', '0', '1']:
            if visit_key in banner_analysis:
                visit_data = banner_analysis[visit_key]
                if visit_data.get('page_status') == 'loaded':
                    page_loaded = True
                    break
        
        if not page_loaded:
            return None, None

        # Get domain analysis
        domain_analysis = data.get('domain_analysis', {})
        if not domain_analysis or 'domains' not in domain_analysis:
            return None, None

        # Extract third-party domains
        third_party_domains = set()
        for domain_data in domain_analysis['domains']:
            if not domain_data.get('is_first_party_domain', False):
                domain = domain_data.get('domain', '')
                if domain:
                    third_party_domains.add(domain)

        return site_rank, third_party_domains

    except Exception as e:
        print(f"Error processing {json_file}: {e}")
        return None, None

def analyze_profile(profile_dir, site_rankings):
    """Analyze all sites in a profile directory"""
    # Store domains by prevalence tier
    domains_by_tier = {
        '2-20': set(),
        '20-200': set(),
        '200-10000': set()
    }
    
    # Track domain prevalence
    domain_prevalence = defaultdict(int)
    sites_by_tier = defaultdict(set)
    
    # Process all JSON files
    json_files = [f for f in os.listdir(profile_dir) if f.endswith('.json')]
    
    for json_file in tqdm(json_files, desc=f"Processing {os.path.basename(profile_dir)}"):
        site_rank, third_party_domains = get_third_party_domains(
            os.path.join(profile_dir, json_file),
            site_rankings
        )
        
        if site_rank and third_party_domains:
            # Determine tier
            if 1 <= site_rank <= 20:
                tier = '2-20'
            elif 21 <= site_rank <= 200:
                tier = '20-200'
            elif 201 <= site_rank <= 10000:
                tier = '200-10000'
            else:
                continue
            
            # Add domains to the appropriate tier
            domains_by_tier[tier].update(third_party_domains)
            sites_by_tier[tier].add(site_rank)
            
            # Update domain prevalence
            for domain in third_party_domains:
                domain_prevalence[domain] += 1

    return domains_by_tier, domain_prevalence, sites_by_tier

def create_comparison_plot(profiles_data, tier):
    """Create comparison plot for a specific tier"""
    baseline_domains = len(profiles_data['no_extensions'][tier])
    
    # Calculate relative percentages
    percentages = {}
    for profile, data in profiles_data.items():
        if baseline_domains > 0:
            percentages[profile] = (len(data[tier]) / baseline_domains) * 100
    
    # Create the plot
    plt.figure(figsize=(10, 6))
    
    # Plot bars
    profiles = list(percentages.keys())
    values = [percentages[p] for p in profiles]
    display_names = [DISPLAY_NAMES.get(p, p) for p in profiles]
    
    plt.bar(display_names, values)
    plt.axhline(y=100, color='black', linestyle='--', alpha=0.5)
    
    plt.title(f'Third-Party Domains Relative to Baseline - Tier {tier}')
    plt.ylabel('Relative Number of Third-Party Domains (%)')
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    return plt

def main():
    # Load site rankings
    site_rankings = load_site_rankings()
    
    # Base directory for crawler data
    json_dir = "data/crawler_data"
    
    # Process each profile
    profiles_data = {}
    for profile in ['no_extensions', 'disconnect', 'ghostery', 'privacy_badger', 'ublock_origin', 'adblock_plus']:
        profile_dir = os.path.join(json_dir, profile)
        if os.path.exists(profile_dir):
            domains_by_tier, domain_prevalence, sites_by_tier = analyze_profile(profile_dir, site_rankings)
            profiles_data[profile] = domains_by_tier
            
            # Print statistics
            print(f"\nProfile: {profile}")
            for tier in domains_by_tier:
                print(f"Tier {tier}:")
                print(f"  Unique third-party domains: {len(domains_by_tier[tier])}")
                print(f"  Sites analyzed: {len(sites_by_tier[tier])}")
    
    # Create plots for each tier
    for tier in ['2-20', '20-200', '200-10000']:
        plt = create_comparison_plot(profiles_data, tier)
        plt.savefig(f'third_party_domains_tier_{tier}.png')
        plt.close()

if __name__ == "__main__":
    main() 