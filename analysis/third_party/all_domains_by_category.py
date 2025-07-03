import os
import sys
import json
from collections import defaultdict
from tqdm import tqdm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.patheffects as path_effects

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from analysis.third_party.third_party_domain_prevalence import get_successful_domains
from analysis.display_names import DISPLAY_NAMES, PROFILE_GROUPS

def analyze_unique_domains(profile, successful_domains=None):
    """Analyze unique third-party domains by category for a specific profile."""
    json_dir = os.path.join("data/crawler_data", profile)
    category_domains = defaultdict(set)  # Changed to set to track unique domains
    
    # Find all JSON files for successful domains only
    json_files = []
    for root, _, files in os.walk(json_dir):
        for file in files:
            if file.endswith('.json'):
                domain = os.path.splitext(os.path.basename(file))[0]
                if successful_domains is None or domain in successful_domains:
                    json_files.append(os.path.join(root, file))
    
    print(f"Analyzing {len(json_files)} successful domains for profile {profile}")
    
    # Process each JSON file
    for json_file in tqdm(json_files, desc=f"Analyzing {profile}", leave=False):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if 'domain_analysis' in data and 'domains' in data['domain_analysis']:
                    first_party_domain = os.path.splitext(os.path.basename(json_file))[0]
                    for domain in data['domain_analysis']['domains']:
                        domain_name = domain.get('domain', '')
                        # Skip first-party domains
                        if domain_name == first_party_domain:
                            continue
                            
                        categories = domain.get('categories', ['Uncategorized'])
                        if not categories:
                            categories = ['Uncategorized']
                        
                        # Add domain to each category's set
                        for category in categories:
                            category_domains[category].add(domain_name)
                            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    # Convert sets to counts
    return {category: len(domains) for category, domains in category_domains.items()}

def plot_all_domains(profile_data):
    """Create a stacked bar chart of unique third-party domains by category."""
    # Get all unique categories across all profiles, excluding 'Uncategorized'
    all_categories = set()
    for profile_categories in profile_data.values():
        all_categories.update(cat for cat in profile_categories.keys() if cat != 'Uncategorized')
    
    # Define custom colors to match the reference image
    category_colors = {
        'Social Media': "#FF8C69",
        'Advertising': "#e36868",
        'Site Analytics': "#4DAF4A",
        'Consent Management': "#98FB98",
        'Hosting': "#377EB8",
        'Customer Interaction': "#80B1D3",
        'Audio/Video Player': "#984EA3",
        'Extensions': "#FFD700",
        'Adult Advertising': "#FF7F00",
        'Utilities': "#999999",
        'Misc': "#333333",
    }

    # Use the order from category_colors
    categories = list(category_colors.keys())
    
    # Add any categories that might exist in the data but not in our color mapping
    remaining_categories = sorted(cat for cat in all_categories if cat not in categories)
    categories.extend(remaining_categories)
    
    # Flatten and order profiles according to groups
    ordered_profiles = []
    for group_profiles in PROFILE_GROUPS.values():
        ordered_profiles.extend([p for p in group_profiles if p in profile_data])
    
    # Calculate the total domains for baseline profile to use as baseline (100%)
    # Excluding 'Uncategorized' from the total
    baseline_total = sum(
        count for category, count in profile_data['no_extensions'].items() 
        if category != 'Uncategorized'
    ) if 'no_extensions' in profile_data else 1

    # Prepare data for plotting (as percentages)
    category_data = {cat: [] for cat in categories}
    for profile in ordered_profiles:
        for category in categories:
            count = profile_data[profile].get(category, 0)
            percentage = (count / baseline_total) * 100
            category_data[category].append(percentage)
    
    # Create the stacked bar chart
    fig, ax = plt.subplots(figsize=(20, 8))
    
    # Calculate maximum height for y-axis limit
    bottom = np.zeros(len(ordered_profiles))
    for category in categories:
        bottom += category_data[category]
    
    # Adjust y-axis to make room below 0
    ax.set_ylim(-10, max(bottom) * 1.1)
    
    # Reset bottom for bar stacking
    bottom = np.zeros(len(ordered_profiles))
    
    bars = []
    for category in categories:
        bar = ax.bar(range(len(ordered_profiles)), 
                    category_data[category],
                    bottom=bottom,
                    label=category,
                    color=category_colors.get(category, '#808080'),
                    width=0.8)
        bars.append(bar)
        
        # Add percentage annotations
        for i, value in enumerate(category_data[category]):
            # Show all Site Analytics values, or other categories if >5%
            if category == 'Site Analytics' or value > 5:
                y_center = float(bottom[i] + value/2)
                text = ax.text(float(i), y_center,
                             f'{value:.0f}%',
                             ha='center', va='center',
                             color='black',
                             fontsize=11,
                             fontweight='bold')
                # Add thinner white outline
                text.set_path_effects([
                    path_effects.Stroke(linewidth=0.8, foreground='white'),
                    path_effects.Normal()
                ])
            
        bottom += category_data[category]
    
    # Add horizontal line at 100%
    plt.axhline(y=100, color='black', linestyle='--', alpha=0.5)
    
    # Add total counts at the bottom
    for i, profile in enumerate(ordered_profiles):
        total = sum(count for category, count in profile_data[profile].items() 
                   if category != 'Uncategorized')
        ax.text(i, -5, f'n={total}', 
                ha='center', va='center', 
                fontsize=11)
    
    plt.ylabel('Percentage of Unique Third-Party Domains\n(relative to Baseline Profile)', fontsize=16)
    
    # Use display names for x-tick labels
    plt.xticks(range(len(ordered_profiles)),
               [DISPLAY_NAMES.get(profile, profile) for profile in ordered_profiles],
               rotation=45, ha='right', fontsize=14)
    plt.yticks(fontsize=14)
    
    # Add group labels and separators
    y_max = max(bottom)
    current_position = 0
    for group_name, group_profiles in PROFILE_GROUPS.items():
        group_profiles_in_data = [p for p in group_profiles if p in profile_data]
        if group_profiles_in_data:
            group_start = current_position
            group_end = current_position + len(group_profiles_in_data) - 1
            
            # Place group label
            label_position = (group_start + group_end) / 2
            plt.text(label_position, y_max * 1.05,
                    group_name,
                    ha='center', va='bottom',
                    fontsize=14,
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=2))
            
            # Add separator line
            if current_position > 0:
                plt.axvline(x=current_position - 0.5,
                          color='black',
                          linestyle=':',
                          alpha=0.7)
            
            current_position += len(group_profiles_in_data)
    
    # Add legend with adjusted position
    plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=14)
    
    # Adjust layout
    plt.tight_layout()
    plt.subplots_adjust(top=0.88)  # Increased top margin to accommodate the subtitle
    
    # Save and show the plot
    plt.savefig('analysis/graphs/all_domains_by_category.png',
                dpi=300, bbox_inches='tight')
    plt.show()
    
    # Print summary statistics
    print("\nSummary of Unique Third-Party Domains by Profile:")
    for profile in ordered_profiles:
        total_domains = sum(profile_data[profile].values())
        print(f"\n{DISPLAY_NAMES.get(profile, profile)}:")
        print(f"  Total unique domains: {total_domains}")
        for category in sorted(profile_data[profile].keys()):
            count = profile_data[profile][category]
            percentage = (count / total_domains) * 100 if total_domains > 0 else 0
            print(f"  {category}: {count} ({percentage:.1f}%)")

def main():
    # Get successful domains first
    successful_domains = get_successful_domains()
    print(f"Found {len(successful_domains)} domains that loaded successfully across all profiles")
    
    # Get all profile directories
    crawler_data_dir = "data/crawler_data"
    profiles = [d for d in os.listdir(crawler_data_dir) 
               if os.path.isdir(os.path.join(crawler_data_dir, d))]
    
    print(f"Found {len(profiles)} profiles to analyze")
    
    # Analyze each profile
    profile_data = {}
    for profile in profiles:
        category_counts = analyze_unique_domains(profile, successful_domains)
        if category_counts:  # Only include profiles with data
            profile_data[profile] = category_counts
    
    # Create visualization
    if profile_data:
        plot_all_domains(profile_data)
    else:
        print("No domains found in any profile.")

if __name__ == "__main__":
    main() 