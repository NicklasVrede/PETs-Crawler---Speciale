import os
import sys
import json
from collections import defaultdict
from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.third_party.third_party_domain_prevalence import (
    get_successful_domains,
    load_tranco_ranks
)

def get_third_party_domains_with_categories(json_file):
    """Get list of third-party domains and their categories from a JSON file."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
            if 'domain_analysis' in data and 'domains' in data['domain_analysis']:
                domains_with_categories = []
                for domain in data['domain_analysis']['domains']:
                    if not domain.get('is_first_party_domain', True):
                        # Get the first category if it exists, otherwise use "Unknown"
                        categories = domain.get('categories', [])
                        category = categories[0] if categories else "Unknown"
                        domains_with_categories.append((domain['domain'], category))
                return domains_with_categories
    except Exception as e:
        print(f"Error processing {json_file}: {str(e)}")
    return []

def analyze_categories():
    """Analyze categories for domains in different frequency bands."""
    successful_domains = get_successful_domains()
    baseline_profile = "no_extensions"
    tranco_ranks = load_tranco_ranks()
    
    print(f"\nTotal successful domains: {len(successful_domains)}")
    
    # Calculate domain prevalence and track categories and ranks
    print("Calculating domain prevalence and categories...")
    domain_inclusions = defaultdict(set)
    domain_categories = {}
    domain_ranks = defaultdict(set)
    
    # Debug counter for third-party domains
    total_third_party = set()
    
    for domain in tqdm(successful_domains):
        json_path = os.path.join("data/crawler_data", baseline_profile, f"{domain}.json")
        if os.path.exists(json_path):
            rank = tranco_ranks.get(domain)
            if rank:
                domains_with_categories = get_third_party_domains_with_categories(json_path)
                for tp_domain, category in domains_with_categories:
                    domain_inclusions[tp_domain].add(domain)
                    domain_ranks[tp_domain].add(rank)
                    total_third_party.add(tp_domain)
                    if tp_domain not in domain_categories:
                        domain_categories[tp_domain] = category
    
    print(f"\nTotal unique third-party domains found: {len(total_third_party)}")
    
    # Convert to frequency counts and sort
    domain_frequencies = {domain: len(sites) for domain, sites in domain_inclusions.items()}
    
    # Print frequency distribution
    print("\nFrequency distribution of third-party domains:")
    freq_counts = defaultdict(int)
    for domain, freq in domain_frequencies.items():
        freq_counts[freq] += 1
    
    for freq in sorted(freq_counts.keys()):
        print(f"Appears on {freq} sites: {freq_counts[freq]} domains")
    
    # Group domains by frequency bands
    freq_bands = {
        "High (20+ sites)": [],
        "Medium (6-20 sites)": [],
        "Low (2-5 sites)": []
    }
    
    for domain, freq in domain_frequencies.items():
        if freq > 20:
            freq_bands["High (20+ sites)"].append(domain)
        elif 6 <= freq <= 20:
            freq_bands["Medium (6-20 sites)"].append(domain)
        elif 2 <= freq <= 5:
            freq_bands["Low (2-5 sites)"].append(domain)
    
    # Print domains that appear only once
    single_occurrence = sum(1 for freq in domain_frequencies.values() if freq == 1)
    print(f"\nDomains that appear only once: {single_occurrence}")
    
    # Count categories in each band
    category_counts = {band: defaultdict(int) for band in freq_bands}
    for band, domains in freq_bands.items():
        for domain in domains:
            category = domain_categories.get(domain, "Unknown")
            category_counts[band][category] += 1
            
    return category_counts, freq_bands, domain_categories, domain_ranks, domain_inclusions

def plot_category_distribution(category_counts, freq_bands):
    """Create a stacked bar chart showing category distribution for each frequency band."""
    # Get all unique categories and sort them by total count
    all_categories = set()
    category_totals = defaultdict(int)
    for band_counts in category_counts.values():
        for category, count in band_counts.items():
            all_categories.add(category)
            category_totals[category] += count
    
    all_categories = sorted(list(all_categories), 
                          key=lambda x: category_totals[x], 
                          reverse=True)
    
    # Prepare data for plotting - reorder bands from lowest to highest
    bands = ["Low (2-5 sites)", "Medium (6-20 sites)", "High (20+ sites)"]  # Reordered
    data = np.zeros((len(all_categories), len(bands)))
    
    for i, category in enumerate(all_categories):
        for j, band in enumerate(bands):
            data[i, j] = category_counts[band][category]
    
    # Calculate percentages
    data_percentages = data / data.sum(axis=0) * 100
    
    # Create plot
    plt.figure(figsize=(15, 10))
    
    # Create color map
    colors = plt.cm.tab20(np.linspace(0, 1, len(all_categories)))
    
    # Create stacked bar chart
    bottom = np.zeros(len(bands))
    bars = []
    for i, category in enumerate(all_categories):
        bar = plt.bar(bands, data_percentages[i], bottom=bottom, 
                     label=category, color=colors[i])
        bottom += data_percentages[i]
        bars.append(bar)
    
    # Customize plot
    plt.ylabel('Percentage of Domains', size=12)
    
    # Add value labels on the bars
    for i in range(len(bands)):
        bottom = 0
        for j in range(len(all_categories)):
            if data_percentages[j, i] > 2:  # Only label if > 2%
                height = data_percentages[j, i]
                plt.text(i, bottom + height/2, 
                        f'{data_percentages[j, i]:.1f}%',
                        ha='center', va='center')
                bottom += height
    
    # Add total domain counts to x-axis labels
    x_ticks = plt.gca().get_xticks()
    x_labels = [f"{band}\n({len(freq_bands[band])} domains)" for band in bands]
    plt.xticks(x_ticks, x_labels)
    
    # Add legend
    plt.legend(title='Categories', bbox_to_anchor=(1.05, 1), 
              loc='upper left', borderaxespad=0.)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save plot
    output_dir = "analysis/graphs/frequency_bands"
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'category_frequency_distribution.png'), 
                bbox_inches='tight', dpi=300)
    plt.close()

def print_summary(category_counts, freq_bands):
    """Print detailed summary of the analysis."""
    print("\nCategory distribution by frequency band:")
    # Reorder bands from lowest to highest
    for band in ["Low (2-5 sites)", "Medium (6-20 sites)", "High (20+ sites)"]:
        print(f"\n{band} ({len(freq_bands[band])} total domains):")
        counts = category_counts[band]
        total = sum(counts.values())
        
        # Sort categories by count
        sorted_categories = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        
        for category, count in sorted_categories:
            percentage = (count / total) * 100
            print(f"  {category}: {count} domains ({percentage:.1f}%)")

def save_domain_lists(freq_bands, domain_categories, domain_inclusions):
    """Save detailed information about domains in each frequency band to a text file."""
    output_dir = "analysis/graphs/frequency_bands"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "domain_frequency_bands.txt")
    
    with open(output_path, 'w') as f:
        f.write("THIRD-PARTY DOMAIN ANALYSIS BY FREQUENCY BAND\n")
        f.write("=" * 50 + "\n\n")
        
        # Process each band in order from low to high
        for band in ["Low (2-5 sites)", "Medium (6-20 sites)", "High (20+ sites)"]:
            domains = freq_bands[band]
            f.write(f"{band} ({len(domains)} domains)\n")
            f.write("-" * 50 + "\n\n")
            
            # Group domains by category
            categories = defaultdict(list)
            for domain in domains:
                category = domain_categories.get(domain, "Unknown")
                inclusion_count = len(domain_inclusions[domain])
                categories[category].append((domain, inclusion_count))
            
            # Sort categories by number of domains
            sorted_categories = sorted(categories.items(), 
                                    key=lambda x: len(x[1]), 
                                    reverse=True)
            
            # Write each category and its domains
            for category, domain_list in sorted_categories:
                f.write(f"{category} ({len(domain_list)} domains):\n")
                
                # Sort domains by inclusion count
                sorted_domains = sorted(domain_list, 
                                     key=lambda x: x[1], 
                                     reverse=True)
                
                for domain, count in sorted_domains:
                    f.write(f"    {domain:<50} {count} sites\n")
                f.write("\n")
            f.write("\n")
    
    print(f"\nDomain lists saved to {output_path}")

def main():
    print("Analyzing third-party domain categories by frequency...")
    category_counts, freq_bands, domain_categories, domain_ranks, domain_inclusions = analyze_categories()
    
    print("\nCreating visualization...")
    plot_category_distribution(category_counts, freq_bands)
    
    print_summary(category_counts, freq_bands)
    
    # Save domain lists
    save_domain_lists(freq_bands, domain_categories, domain_inclusions)
    
    print("\nAnalysis complete! Visualization saved as 'category_frequency_distribution.png'")

if __name__ == "__main__":
    main() 